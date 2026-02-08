import os
import json
from .base import BaseService


class S3Service(BaseService):
    def __init__(self):
        super().__init__()
        self.s3 = self.session.client('s3')
        self.sts = self.session.client('sts')
        self.region = self.session.region_name

    def get_arc_buckets(self):
        """מחזיר רשימה של באקטים שמנוהלים ע"י ARC"""
        arc_buckets = []
        try:
            response = self.s3.list_buckets()
            all_buckets = response.get('Buckets', [])

            for bucket in all_buckets:
                name = bucket['Name']
                try:
                    tagging = self.s3.get_bucket_tagging(Bucket=name)
                    tags = {tag['Key']: tag['Value'] for tag in tagging.get('TagSet', [])}

                    if tags.get('Tool') == 'ARC':
                        arc_buckets.append(name)
                except Exception:
                    continue
            return arc_buckets
        except Exception:
            return []

    def create_bucket(self, bucket_name, is_public=False):
        """יצירת באקט חדש"""
        try:
            current_buckets = self.get_arc_buckets()
            if len(current_buckets) >= 2:
                return False, "Quota exceeded: You already have 2 ARC buckets."

            if self.region == 'us-east-1':
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )

            if is_public:
                self.s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False,
                        'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False,
                        'RestrictPublicBuckets': False
                    }
                )
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*"
                    }]
                }
                self.s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

            identity = self.sts.get_caller_identity()
            user_name = identity.get('Arn', '').split('/')[-1]

            tags = {
                'TagSet': [
                    {'Key': 'CreatedBy', 'Value': user_name},
                    {'Key': 'Tool', 'Value': 'ARC'}
                ]
            }
            self.s3.put_bucket_tagging(Bucket=bucket_name, Tagging=tags)

            return True, f"Bucket '{bucket_name}' created successfully."
        except Exception as e:
            return False, str(e)

    def delete_bucket(self, bucket_name):
        """מחיקת באקט"""
        try:
            if bucket_name not in self.get_arc_buckets():
                return False, "Permission Denied: Not an ARC bucket."

            self.s3.delete_bucket(Bucket=bucket_name)
            return True, f"Bucket '{bucket_name}' deleted."
        except Exception as e:
            if "BucketNotEmpty" in str(e):
                return False, "Error: Bucket is not empty. Please empty it first."
            return False, str(e)

    def upload_to_s3(self, file_path, bucket_name):
        """העלאת קובץ"""
        try:
            if bucket_name not in self.get_arc_buckets():
                return False, "Access Denied: Not an ARC bucket."

            if not os.path.exists(file_path):
                return False, "File not found."

            file_name = os.path.basename(file_path)
            self.s3.upload_file(file_path, bucket_name, file_name)
            return True, f"File '{file_name}' uploaded successfully."
        except Exception as e:
            return False, str(e)