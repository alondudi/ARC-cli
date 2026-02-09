from .base import BaseService
import os
import stat
import boto3


class EC2Service(BaseService):
    def __init__(self):
        super().__init__()
        self.ec2 = self.session.client('ec2')
        self.ssm = self.session.client('ssm')

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

        except Exception:
            return []

    def get_latest_ami(self, os_type):
        """שליפת ה-AMI העדכני ביותר דרך SSM Parameter Store"""
        ssm_paths = {
            'AL2023': '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64',
            'UBUNTU': '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id'
        }

        path = ssm_paths.get(os_type)
        if not path:
            return None

        try:
            response = self.ssm.get_parameter(Name=path)
            return response['Parameter']['Value']
        except Exception:
            return None

    def check_quota_status(self):
        """בדיקה מקדימה האם המשתמש חרג מהמכסה"""
        try:
            caller = self.sts.get_caller_identity()
            username = caller.get('Arn').split('/')[-1]
            quota_filters = [
                {'Name': 'tag:Tool', 'Values': ['ARC']},
                {'Name': 'tag:Owner', 'Values': [username]},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped', 'stopping']}
            ]

            existing = self.ec2.describe_instances(Filters=quota_filters)

            current_count = 0
            for reservation in existing['Reservations']:
                current_count += len(reservation['Instances'])

            if current_count >= 2:
                return False, f"Quota Exceeded: You have {current_count} active servers. The limit is 2."

            return True, "Quota OK"

        except Exception as e:
            return False, f"Error checking quota: {str(e)}"

    def create_instance(self, instance_name, os_type, instance_type, key_name, user_data=None):
        """create instance"""
        try:
            caller = self.sts.get_caller_identity()
            arn = caller.get('Arn')
            username = arn.split('/')[-1]
            ami_id = self.get_latest_ami(os_type)
            if not ami_id:
                return False, f"Could not find AMI for {os_type}"

            tags = [
                {'Key': 'Name', 'Value': instance_name},
                {'Key': 'Owner', 'Value': username},
                {'Key': 'Tool', 'Value': 'ARC'}
            ]

            response = self.ec2.run_instances(
                ImageId=ami_id,
                InstanceType=instance_type,
                KeyName=key_name,
                MinCount=1,
                MaxCount=1,
                UserData=user_data or '',
                TagSpecifications=[{
                    'ResourceType': 'instance',
                    'Tags': tags
                }]
            )

            instance_id = response['Instances'][0]['InstanceId']
            waiter = self.ec2.get_waiter('instance_running')
            waiter.wait(InstanceIds=[instance_id])

            return True, f"Server '{instance_name}' created successfully."

        except Exception as e:
            return False, str(e)

    def terminate_instance(self, name_or_id):
        """Delete instance"""
        try:
            instance_id = name_or_id

            if not name_or_id.startswith('i-'):
                instances = self.get_arc_instances()
                target = next((i for i in instances if i['name'] == name_or_id), None)

                if not target:
                    return False, f"Instance with name '{name_or_id}' not found in ARC."

                instance_id = target['id']

            self.ec2.terminate_instances(InstanceIds=[instance_id])
            return True, f"Termination request for {name_or_id} sent successfully."

        except Exception as e:
            return False, str(e)

    def manage_instance(self, name_or_id, action):
        """ec2 management stop or start """
        try:
            instances = self.get_arc_instances()
            target = next((i for i in instances if i['name'] == name_or_id or i['id'] == name_or_id), None)

            if not target:
                return False, f"Instance '{name_or_id}' not found in ARC."

            instance_id = target['id']
            current_status = target['status']

            if action == 'stop' and current_status == 'stopped':
                return False, f"Instance '{name_or_id}' is already stopped. No action taken."

            if action == 'start' and current_status == 'running':
                return False, f"Instance '{name_or_id}' is already running. No action taken."

            actions = {
                'start': self.ec2.start_instances,
                'stop': self.ec2.stop_instances,
            }

            actions[action](InstanceIds=[instance_id])
            return True, f"{action.capitalize()} request sent for {name_or_id}."

        except Exception as e:
            return False, str(e)

    def get_available_local_keys(self):
        """EC2 key pairs from local directory"""
        try:
            aws_response = self.ec2.describe_key_pairs()
            aws_keys = [k['KeyName'] for k in aws_response.get('KeyPairs', [])]

            if not self.KEYS_DIR.exists():
                return []

            local_files = os.listdir(self.KEYS_DIR)
            valid_keys = []

            for key in aws_keys:
                if f"{key}.pem" in local_files:
                    valid_keys.append(key)

            return valid_keys
        except Exception as e:
            print(f"Error listing keys: {e}")
            return []

    def create_new_key_pair(self, key_name):
        """create key pair"""
        try:
            response = self.ec2.create_key_pair(KeyName=key_name)
            key_material = response['KeyMaterial']
            file_path = self.KEYS_DIR / f"{key_name}.pem"
            file_path.write_text(key_material)

            try:
                os.chmod(file_path, stat.S_IRUSR)
            except:
                pass

            return True, str(file_path)

        except Exception as e:
            return False, str(e)