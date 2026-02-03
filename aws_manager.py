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
            self.ec2 = self.session.client('ec2')

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

############GET##############
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

    def get_arc_instances(self):
        try:
            filters = [
                {'Name': 'tag:Tool', 'Values': ['ARC']},
                {'Name': 'instance-state-name',
                 'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']}
            ]

            response = self.ec2.describe_instances(Filters=filters)
            instances_list = []

            for reservation in response.get('Reservations', []):
                for ins in reservation.get('Instances', []):
                    name = next((tag['Value'] for tag in ins.get('Tags', []) if tag['Key'] == 'Name'), "Unnamed")

                    instances_list.append({
                        'id': ins['InstanceId'],
                        'status': ins['State']['Name'],
                        'name': name,
                        'type': ins['InstanceType'],
                        'public_ip': ins.get('PublicIpAddress', 'N/A'),
                        'private_ip': ins.get('PrivateIpAddress', 'N/A')
                    })
            return instances_list
        except Exception as e:
            print(f"Error fetching ARC instances: {e}")
            return []

    import json

    def create_bucket(self, bucket_name, is_public=False):
        try:
            arc_buckets = self.get_arc_buckets()
            if len(arc_buckets) >= 2:
                return False, f"Quota exceeded: You already have 2 ARC buckets: {', '.join(arc_buckets)}. Limit is 2."
            identity = self.sts.get_caller_identity()
            user_name = identity.get('Arn', '').split('/')[-1]
            if self.region == 'us-east-1':
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            if is_public:
                # א. פתיחת החסימה הציבורית
                self.s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False, 'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False, 'RestrictPublicBuckets': False
                    }
                )
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

    def create_instance(self, instance_name, os_type, instance_type, user_data=None):
        try:
            # בדיקת מכסה: סופרים רק אינסטנסים של ARC שהם בסטטוס running
            all_arc_instances = self.get_arc_instances()
            running_instances = [i for i in all_arc_instances if i['status'] == 'running']

            if len(running_instances) >= 2:
                instance_ids = ", ".join([i['id'] for i in running_instances])
                return False, f"Quota exceeded: 2 ARC instances are already running ({instance_ids})."

            ami_map = {
                'AL2023': 'ami-0532be01f26a3de55',
                'UBUNTU': 'ami-0b6c6ebed2801a5cb'
            }

            selected_ami = ami_map.get(os_type.upper())

            launch_params = {
                'ImageId': selected_ami,
                'InstanceType': instance_type.lower(),  # t3.micro או t3.small
                'MinCount': 1,
                'MaxCount': 1,
                'TagSpecifications': [{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': instance_name},
                        {'Key': 'Tool', 'Value': 'ARC'}
                    ]
                }]
            }

            if user_data:
                launch_params['UserData'] = user_data

            response = self.ec2.run_instances(**launch_params)
            new_id = response['Instances'][0]['InstanceId']

            return True, f"Launched {os_type} ({instance_type}) instance {new_id}. Running: {len(running_instances) + 1}/2"

        except Exception as e:
            return False, str(e)

    def delete_bucket(self, bucket_name):
        try:
            arc_buckets = self.get_arc_buckets()
            if bucket_name not in arc_buckets:
                return False, f"Permission Denied: Bucket '{bucket_name}' is not managed by ARC."

            # הערה: S3 מאפשר למחוק באקט רק אם הוא ריק מקבצים
            self.s3.delete_bucket(Bucket=bucket_name)
            return True, f"Bucket '{bucket_name}' deleted successfully."
        except Exception as e:
            return False, str(e)

    def upload_to_s3(self, file_path, bucket_name):
        """Upload files only if the bucket is managed by ARC."""
        try:
            arc_buckets = self.get_arc_buckets()
            if bucket_name not in arc_buckets:
                return False, f"Access Denied: Bucket '{bucket_name}' is not an ARC bucket."

            import os
            file_name = os.path.basename(file_path)
            self.s3.upload_file(file_path, bucket_name, file_name)
            return True, f"File '{file_name}' uploaded successfully to '{bucket_name}'."
        except Exception as e:
            return False, str(e)