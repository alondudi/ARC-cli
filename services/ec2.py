from .base import BaseService


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

    def create_instance(self, instance_name, os_type, instance_type, key_name, user_data=None):
        try:
            running = [i for i in self.get_arc_instances() if i['status'] == 'running']
            if len(running) >= 2:
                return False, "Quota exceeded: 2 ARC instances are already running."

            ssm_paths = {
                'AL2023': '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64',
                'UBUNTU': '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id'
            }
            path = ssm_paths.get(os_type.upper())
            if not path:
                return False, f"OS type '{os_type}' not supported."

            ssm_response = self.ssm.get_parameter(Name=path)
            ami_id = ssm_response['Parameter']['Value']

            launch_params = {
                'ImageId': ami_id,
                'InstanceType': instance_type.lower(),
                'KeyName': key_name,
                'MinCount': 1,
                'MaxCount': 1,
                'TagSpecifications': [{
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': instance_name}, {'Key': 'Tool', 'Value': 'ARC'}]
                }]
            }
            if user_data:
                launch_params['UserData'] = user_data

            response = self.ec2.run_instances(**launch_params)
            new_id = response['Instances'][0]['InstanceId']
            return True, f"Launched {instance_name} ({instance_type}) with key '{key_name}'. ID: {new_id}"
        except Exception as e:
            return False, str(e)

    def terminate_instance(self, name_or_id):
        """מחיקת שרת לפי שם או ID"""
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
        """
        ניהול חכם של מצב השרת (start, stop ).
        בודק את המצב הנוכחי כדי למנוע פעולות כפולות.
        """
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

            # 3. מיפוי הפקודות של Boto3
            actions = {
                'start': self.ec2.start_instances,
                'stop': self.ec2.stop_instances,
            }

            # 4. ביצוע הפעולה
            actions[action](InstanceIds=[instance_id])
            return True, f"{action.capitalize()} request sent for {name_or_id}."

        except Exception as e:
            return False, str(e)
