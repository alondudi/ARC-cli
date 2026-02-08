import time
from .base import BaseService


class Route53Service(BaseService):
    def __init__(self):
        super().__init__()
        self.r53 = self.session.client('route53')

    def list_hosted_zones(self):
        """מחזיר רשימה של Hosted Zones שנוצרו על ידי ARC בלבד"""
        try:
            response = self.r53.list_hosted_zones()
            arc_zones = []

            for z in response.get('HostedZones', []):
                zone_id = z['Id'].split('/')[-1]

                # בדיקה האם הזון נוצר על ידי הכלי שלנו
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
            # במקרה של שגיאה (למשל אין הרשאות), נחזיר רשימה ריקה
            return []

    def get_zone_id_by_name(self, domain_name):
        """פונקציית עזר: מוצאת ID לפי שם (מתעלמת מנקודות)"""
        # 1. ניקוי הקלט
        clean_input = domain_name.lower().rstrip('.')

        # 2. שליפת הזונים של ARC בלבד
        zones = self.list_hosted_zones()

        # 3. חיפוש
        for z in zones:
            clean_zone_name = z['name'].lower().rstrip('.')
            if clean_input == clean_zone_name:
                return z['id']

        return None

    def create_hosted_zone(self, domain_name):
        """יוצר Hosted Zone חדש"""
        try:
            caller_ref = str(time.time())  # מונע כפילויות בבקשות

            response = self.r53.create_hosted_zone(
                Name=domain_name,
                CallerReference=caller_ref,
                HostedZoneConfig={
                    'Comment': f'Created by ARC CLI for {domain_name}',
                    'PrivateZone': False
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

    def delete_hosted_zone(self, name_or_id):
        """מוחק Hosted Zone (רק אם הוא של ARC)"""
        try:
            zone_id = name_or_id

            # אם קיבלנו שם, נחפש את ה-ID
            if not name_or_id.startswith('Z'):
                found_id = self.get_zone_id_by_name(name_or_id)
                if not found_id:
                    return False, f"Hosted Zone '{name_or_id}' not found inside ARC managed zones."
                zone_id = found_id

            # מחיקה
            self.r53.delete_hosted_zone(Id=zone_id)
            return True, f"Hosted Zone {zone_id} ({name_or_id}) deleted successfully."
        except Exception as e:
            if "HostedZoneNotEmpty" in str(e):
                return False, "Error: Zone is not empty. Delete all records first."
            return False, str(e)

    def manage_dns_record(self, zone_name, action, record_prefix, value):
        """
        ניהול רשומות: יצירה (UPSERT) או מחיקה (DELETE).
        בודק שהזון שייך ל-ARC לפני ביצוע הפעולה.
        """
        try:
            # 1. מציאת הזון ואימות שהוא שלנו
            zone_id = self.get_zone_id_by_name(zone_name)

            if not zone_id:
                return False, f"Access Denied: Zone '{zone_name}' is not managed by ARC."

            # 2. הבנת הדומיין המלא כדי לבנות את שם הרשומה
            zone_info = self.r53.get_hosted_zone(Id=zone_id)
            full_domain = zone_info['HostedZone']['Name'].rstrip('.')

            if record_prefix == '@' or record_prefix == '':
                final_name = f"{full_domain}."
            else:
                final_name = f"{record_prefix}.{full_domain}."

            # 3. ביצוע הפעולה
            self.r53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Comment': f'{action} by ARC CLI',
                    'Changes': [{
                        'Action': action,
                        'ResourceRecordSet': {
                            'Name': final_name,
                            'Type': 'A',  # כרגע תומך רק ב-A Record לפשטות
                            'TTL': 300,
                            'ResourceRecords': [{'Value': value}]
                        }
                    }]
                }
            )

            verb = "Linked" if action == 'UPSERT' else "Deleted"
            return True, f"{verb}: {final_name} -> {value}"

        except Exception as e:
            if "InvalidChangeBatch" in str(e):
                return False, "Error: To delete, the IP must match exactly what is in AWS."
            return False, str(e)