import boto3
import json
import os
from pathlib import Path


class AWSClient:
    CONFIG_PATH = Path.home() / ".arc_config.json"

    def __init__(self, access_key=None, secret_key=None, region=None):
        if not access_key:
            config = self._load_config()
            access_key = config.get("access_key")
            secret_key = config.get("secret_key")
            region = config.get("region", "us-east-1")

        self.region = region or "us-east-1"

        try:
            self.session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=self.region
            )
            self.sts = self.session.client('sts')
            self.s3 = self.session.client('s3')
        except Exception as e:
            print(f"Connection Error: {e}")

    def _load_config(self):
        """Reading the config file from disk."""
        if self.CONFIG_PATH.exists():
            try:
                return json.loads(self.CONFIG_PATH.read_text())
            except:
                return {}
        return {}

    def save_config(self, access_key, secret_key, region):
        """Saving the credentials to a JSON file."""
        data = {
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region
        }
        self.CONFIG_PATH.write_text(json.dumps(data, indent=4))

    def validate_connection(self):
        """Testing the connection with STS."""
        try:
            identity = self.sts.get_caller_identity()
            return True, identity.get('Arn')
        except Exception as e:
            return False, str(e)

    def get_arc_buckets(self):
        """Returns only buckets that were created by ARC (based on tags)."""
        arc_buckets = []
        try:
            all_buckets = self.s3.list_buckets().get('Buckets', [])

            for bucket in all_buckets:
                name = bucket['Name']
                try:
                    tagging = self.s3.get_bucket_tagging(Bucket=name)
                    tags = {tag['Key']: tag['Value'] for tag in tagging.get('TagSet', [])}
                    if tags.get('Tool') == 'ARC':
                        arc_buckets.append(name)
                except:
                    continue

            return arc_buckets
        except Exception as e:
            print(f"Error filtering buckets: {e}")
            return []

    import json

    def create_bucket(self, bucket_name, is_public=False):
        try:
            arc_buckets = self.get_arc_buckets()
            if len(arc_buckets) >= 2:
                return False, f"Quota exceeded: You already have 2 ARC buckets: {', '.join(arc_buckets)}. Limit is 2."
            identity = self.sts.get_caller_identity()
            user_name = identity.get('Arn', '').split('/')[-1]

            # 2. יצירה בסיסית (בלי ACL בכלל!)
            if self.region == 'us-east-1':
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )

            # 3. אם ביקשו ציבורי - משתמשים ב-Policy במקום ב-ACL
            if is_public:
                # א. פתיחת החסימה הציבורית
                self.s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False, 'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False, 'RestrictPublicBuckets': False
                    }
                )

                # ב. הוספת Policy שמאפשר לכולם לקרוא (Read-Only)
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*"
                    }]
                }
                self.s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(bucket_policy))

            # 4. הוספת תגים
            tags = {'TagSet': [{'Key': 'CreatedBy', 'Value': user_name}, {'Key': 'Tool', 'Value': 'ARC'}]}
            self.s3.put_bucket_tagging(Bucket=bucket_name, Tagging=tags)

            return True, f"Bucket created successfully (Public: {is_public})"

        except Exception as e:
            return False, str(e)

    def delete_bucket(self, bucket_name):
        try:
            # שלב א': בדיקה שהבאקט שייך ל-ARC
            arc_buckets = self.get_arc_buckets()
            if bucket_name not in arc_buckets:
                return False, f"Permission Denied: Bucket '{bucket_name}' is not managed by ARC."

            # שלב ב': מחיקת הבאקט
            # הערה: S3 מאפשר למחוק באקט רק אם הוא ריק מקבצים
            self.s3.delete_bucket(Bucket=bucket_name)
            return True, f"Bucket '{bucket_name}' deleted successfully."

        except Exception as e:
            return False, str(e)