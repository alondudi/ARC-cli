import boto3
import json
import os
from pathlib import Path


class AWSClient:
    # ARC dir configuration
    ARC_HOME = Path.home() / ".arc"
    KEYS_DIR = ARC_HOME / "keys"
    CONFIG_PATH = KEYS_DIR / "config.json"

    def __init__(self, access_key=None, secret_key=None, region=None):
        self.ARC_HOME.mkdir(exist_ok=True)
        self.KEYS_DIR.mkdir(exist_ok=True)

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
            self.r53 = self.session.client('route53')
            self.ssm = self.session.client('ssm')

        except Exception as e:
            print(f"Connection Error: {e}")

    def _load_config(self):
        """טעינת הגדרות מהקובץ בתיקיית .arc"""
        if self.CONFIG_PATH.exists():
            try:
                return json.loads(self.CONFIG_PATH.read_text())
            except:
                return {}
        return {}

    def save_config(self, access_key, secret_key, region):
        """שמירת הגדרות לקובץ בתוך תיקיית .arc"""
        data = {
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region
        }
        self.CONFIG_PATH.write_text(json.dumps(data, indent=4))

    def validate_connection(self):
        try:
            identity = self.sts.get_caller_identity()
            return True, identity.get('Arn')
        except Exception as e:
            return False, str(e)

    # ---------- ניהול מפתחות (Keys) ----------

    def get_all_aws_keys(self):
        """שליפת שמות המפתחות שקיימים בחשבון ה-AWS"""
        try:
            response = self.ec2.describe_key_pairs()
            return [k['KeyName'] for k in response.get('KeyPairs', [])]
        except Exception:
            return []

    def get_available_local_keys(self):
        """הצלבה בין מפתחות בענן לקבצים פיזיים בתיקיית .arc/keys"""
        aws_keys = self.get_all_aws_keys()
        local_files = os.listdir(self.KEYS_DIR)

        valid_keys = []
        for key in aws_keys:
            if f"{key}.pem" in local_files or f"{key}.ppk" in local_files:
                valid_keys.append(key)
        return valid_keys

    # ---------- שליפת משאבים (GET) ----------

    def get_arc_buckets(self):
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
        except Exception:
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
        except Exception:
            return []

    def list_hosted_zones(self):
        """מחזיר רשימה של Hosted Zones שנוצרו על ידי ARC בלבד"""
        try:
            response = self.r53.list_hosted_zones()
            arc_zones = []

            for z in response.get('HostedZones', []):
                zone_id = z['Id'].split('/')[-1]

                # אנחנו בודקים אם ה-Comment מכיל את מילת המפתח שלנו
                # הערה: כדי להיות בטוחים ב-100%, אפשר גם למשוך את ה-Tags של ה-Zone
                config = z.get('Config', {})
                comment = config.get('Comment', '')

                if "Created by ARC" in comment:
                    arc_zones.append({
                        'id': zone_id,
                        'name': z['Name'],
                        'records': z.get('ResourceRecordSetCount', 0),
                        'comment': comment
                    })
            return arc_zones
        except Exception as e:
            print(f"Error listing zones: {e}")
            return []

    def list_hosted_zones(self):
        """מחזיר רשימה של Hosted Zones שנוצרו על ידי ARC בלבד"""
        try:
            response = self.r53.list_hosted_zones()
            arc_zones = []

            for z in response.get('HostedZones', []):
                zone_id = z['Id'].split('/')[-1]

                # אנחנו בודקים אם ה-Comment מכיל את מילת המפתח שלנו
                # הערה: כדי להיות בטוחים ב-100%, אפשר גם למשוך את ה-Tags של ה-Zone
                config = z.get('Config', {})
                comment = config.get('Comment', '')

                if "Created by ARC" in comment:
                    arc_zones.append({
                        'id': zone_id,
                        'name': z['Name'],
                        'records': z.get('ResourceRecordSetCount', 0),
                        'comment': comment
                    })
            return arc_zones
        except Exception as e:
            print(f"Error listing zones: {e}")
            return []

    def get_zone_id_by_name(self, domain_name):
        """מוצא ID בצורה חכמה (מתעלם מנקודות בסוף)"""
        # 1. ניקוי הקלט: אותיות קטנות + הסרת נקודה בסוף
        clean_input = domain_name.lower().rstrip('.')

        # 2. שליפת כל הזונים
        zones = self.list_hosted_zones()

        # 3. מעבר על הרשימה והשוואה "נקייה"
        for z in zones:
            # ניקוי השם שמגיע מ-AWS
            clean_zone_name = z['name'].lower().rstrip('.')

            if clean_input == clean_zone_name:
                return z['id']

        return None
    # ---------- יצירת משאבים (CREATE) ----------

    def create_bucket(self, bucket_name, is_public=False):
        try:
            if len(self.get_arc_buckets()) >= 2:
                return False, "Quota exceeded: You already have 2 ARC buckets."

            if self.region == 'us-east-1':
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': self.region})

            if is_public:
                self.s3.put_public_access_block(Bucket=bucket_name,
                                                PublicAccessBlockConfiguration={'BlockPublicAcls': False,
                                                                                'IgnorePublicAcls': False,
                                                                                'BlockPublicPolicy': False,
                                                                                'RestrictPublicBuckets': False})
                policy = {"Version": "2012-10-17", "Statement": [
                    {"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject",
                     "Resource": f"arn:aws:s3:::{bucket_name}/*"}]}
                self.s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

            identity = self.sts.get_caller_identity()
            user_name = identity.get('Arn', '').split('/')[-1]
            tags = {'TagSet': [{'Key': 'CreatedBy', 'Value': user_name}, {'Key': 'Tool', 'Value': 'ARC'}]}
            self.s3.put_bucket_tagging(Bucket=bucket_name, Tagging=tags)
            return True, f"Bucket '{bucket_name}' created successfully."
        except Exception as e:
            return False, str(e)

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

    def create_hosted_zone(self, domain_name):
        """יוצר Hosted Zone חדש ב-Route 53"""
        try:
            # יצירת מזהה ייחודי לבקשה (CallerReference) כדי למנוע כפילויות
            import time
            caller_ref = str(time.time())

            response = self.r53.create_hosted_zone(
                Name=domain_name,
                CallerReference=caller_ref,
                HostedZoneConfig={
                    'Comment': f'Created by ARC CLI for {domain_name}',
                    'PrivateZone': False  # נתחיל עם Public Zone (הכי נפוץ)
                }
            )

            zone_id = response['HostedZone']['Id'].split('/')[-1]
            ns_records = response['DelegationSet']['NameServers']

            return True, {
                'id': zone_id,
                'name_servers': ns_records
            }
        except Exception as e:
            return False, str(e)

    def create_dns_record(self, zone_name, record_name, record_type, value, ttl=300):
        """יוצר רשומה ב-Route 53 בצורה חכמה"""
        try:
            # 1. מציאת ה-ID של הזון
            zone_id = self.get_zone_id_by_name(zone_name)
            if not zone_id:
                return False, f"Zone '{zone_name}' not found."

            # 2. הבנת הדומיין המלא
            # אנו שואבים את השם האמיתי מ-AWS כדי למנוע טעויות
            zone_info = self.r53.get_hosted_zone(Id=zone_id)
            full_domain = zone_info['HostedZone']['Name'].rstrip('.')

            # 3. בניית שם הרשומה
            if record_name == '@' or record_name == '':
                final_name = full_domain
            else:
                final_name = f"{record_name}.{full_domain}"

            # 4. שליחת הבקשה ל-AWS
            change_batch = {
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': final_name,
                        'Type': record_type,
                        'TTL': int(ttl),
                        'ResourceRecords': [{'Value': value}]
                    }
                }]
            }

            self.r53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch=change_batch
            )

            return True, f"Created {record_type} record: {final_name} -> {value}"

        except Exception as e:
            return False, str(e)

    def manage_dns_record(self, zone_name, action, record_prefix, value):
        """
        פונקציה מרכזית לניהול רשומות (יצירה ומחיקה).
        Action: 'UPSERT' (ליצירה/עדכון) או 'DELETE' (למחיקה).
        """
        try:
            # 1. שלב האבטחה: האם הזון הזה קיים והאם הוא של ARC?
            # אנחנו משתמשים בפונקציה list_hosted_zones שכבר מסננת לפי ההערה
            arc_zones = self.list_hosted_zones()

            # חיפוש ה-ID ברשימה המורשית
            target_zone_id = None
            clean_input_name = zone_name.strip('.')  # ניקוי נקודות מהקלט

            for z in arc_zones:
                if z['name'].strip('.') == clean_input_name:
                    target_zone_id = z['id']
                    break

            if not target_zone_id:
                return False, f"Access Denied: Zone '{zone_name}' is not managed by ARC."

            # 2. סידור השם המלא (למשל www.alon.com)
            zone_info = self.r53.get_hosted_zone(Id=target_zone_id)
            full_domain = zone_info['HostedZone']['Name'].rstrip('.')

            if record_prefix == '@' or record_prefix == '':
                final_name = f"{full_domain}."
            else:
                final_name = f"{record_prefix}.{full_domain}."

            # 3. ביצוע הפעולה מול AWS
            self.r53.change_resource_record_sets(
                HostedZoneId=target_zone_id,
                ChangeBatch={
                    'Comment': f'{action} by ARC CLI',
                    'Changes': [{
                        'Action': action,  # כאן הקסם: או UPSERT או DELETE
                        'ResourceRecordSet': {
                            'Name': final_name,
                            'Type': 'A',  # שמרנו על פשטות (A Record בלבד)
                            'TTL': 300,
                            'ResourceRecords': [{'Value': value}]
                        }
                    }]
                }
            )

            verb = "Created/Updated" if action == 'UPSERT' else "Deleted"
            return True, f"{verb}: {final_name} -> {value}"

        except Exception as e:
            # שגיאה נפוצה במחיקה: הערך לא תואם
            if "InvalidChangeBatch" in str(e):
                return False, "Error: To delete a record, the IP must match exactly what's in AWS."
            return False, str(e)
    # ---------- פעולות (DELETE / UPLOAD) ----------

    def delete_bucket(self, bucket_name):
        try:
            if bucket_name not in self.get_arc_buckets():
                return False, "Permission Denied: Not an ARC bucket."
            self.s3.delete_bucket(Bucket=bucket_name)
            return True, f"Bucket '{bucket_name}' deleted."
        except Exception as e:
            return False, str(e)

    def terminate_instance(self, name_or_id):
        try:
            instance_id = name_or_id
            if not name_or_id.startswith('i-'):
                instances = self.get_arc_instances()
                target = next((i for i in instances if i['name'] == name_or_id), None)
                if not target:
                    return False, f"Instance with name '{name_or_id}' not found in ARC."
                instance_id = target['id']

            # ביצוע המחיקה
            self.ec2.terminate_instances(InstanceIds=[instance_id])
            return True, f"Termination request for {name_or_id} sent successfully."
        except Exception as e:
            return False, str(e)

        return target['id'] if target else None

    def delete_hosted_zone(self, name_or_id):
        """מוחק Zone לפי שם או ID"""
        try:
            zone_id = name_or_id

            # אם זה לא נראה כמו ID (לא מתחיל ב-Z), ננסה למצוא את ה-ID לפי השם
            if not name_or_id.startswith('Z'):
                found_id = self.get_zone_id_by_name(name_or_id)
                if not found_id:
                    return False, f"Hosted Zone '{name_or_id}' not found."
                zone_id = found_id

            # ביצוע המחיקה
            self.r53.delete_hosted_zone(Id=zone_id)
            return True, f"Hosted Zone {zone_id} ({name_or_id}) deleted successfully."
        except Exception as e:
            # שגיאה נפוצה: ה-Zone לא ריק
            if "HostedZoneNotEmpty" in str(e):
                return False, "Error: The zone is not empty. You must delete all records (except NS/SOA) first."
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

    def upload_to_s3(self, file_path, bucket_name):
        try:
            if bucket_name not in self.get_arc_buckets():
                return False, "Access Denied: Not an ARC bucket."
            file_name = os.path.basename(file_path)
            self.s3.upload_file(file_path, bucket_name, file_name)
            return True, f"File '{file_name}' uploaded successfully."
        except Exception as e:
            return False, str(e)