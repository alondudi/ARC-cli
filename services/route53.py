import time
from .base import BaseService


class Route53Service(BaseService):
    def __init__(self):
        super().__init__()
        self.r53 = self.session.client('route53')

    def list_hosted_zones(self):
        """List ARC managed Hosted Zone"""
        try:
            response = self.r53.list_hosted_zones()
            arc_zones = []

            for z in response.get('HostedZones', []):
                zone_id = z['Id'].split('/')[-1]

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
            return []

    def get_zone_id_by_name(self, domain_name):
        """Get zone id by name"""
        clean_input = domain_name.lower().rstrip('.')
        zones = self.list_hosted_zones()

        for z in zones:
            clean_zone_name = z['name'].lower().rstrip('.')
            if clean_input == clean_zone_name:
                return z['id']

        return None

    def create_hosted_zone(self, domain_name):
        """Create Hosted Zone"""
        try:
            caller_ref = str(time.time())

            response = self.r53.create_hosted_zone(
                Name=domain_name,
                CallerReference=caller_ref,
                HostedZoneConfig={
                    'Comment': f'Created by ARC CLI for {domain_name}',
                    'PrivateZone': False
                }
            )
            zone_name = response['HostedZone']['Name'].rstrip('.')
            ns_records = response['DelegationSet']['NameServers']

            return True, {
                'name': zone_name,
                'name_servers': ns_records
            }
        except Exception as e:
            return False, str(e)

    def delete_hosted_zone(self, name_or_id, force=False):
        """Delete Hosted Zone"""
        try:
            zone_id = name_or_id

            if not name_or_id.startswith('Z'):
                found_id = self.get_zone_id_by_name(name_or_id)
                if not found_id:
                    return False, f"Zone '{name_or_id}' not found."
                zone_id = found_id

            if force:
                try:
                    records = self.r53.list_resource_record_sets(HostedZoneId=zone_id)['ResourceRecordSets']

                    changes = []
                    for record in records:
                        if record['Type'] in ['SOA', 'NS']:
                            continue

                        changes.append({
                            'Action': 'DELETE',
                            'ResourceRecordSet': record
                        })

                    if changes:
                        self.r53.change_resource_record_sets(
                            HostedZoneId=zone_id,
                            ChangeBatch={'Changes': changes}
                        )
                except Exception as e:
                    return False, f"Failed to clean records: {str(e)}"

            self.r53.delete_hosted_zone(Id=zone_id)
            return True, f"Zone {zone_id} deleted successfully."

        except Exception as e:
            if "HostedZoneNotEmpty" in str(e):
                return False, "Error: Zone contains records. Use --all (in CLI) or force delete."
            return False, str(e)

    def manage_dns_record(self, zone_name, action, record_prefix, value):
        """Create and delete DNS records"""
        try:
            zone_id = self.get_zone_id_by_name(zone_name)

            if not zone_id:
                return False, f"Access Denied: Zone '{zone_name}' is not managed by ARC."

            zone_info = self.r53.get_hosted_zone(Id=zone_id)
            full_domain = zone_info['HostedZone']['Name'].rstrip('.')

            if record_prefix == '@' or record_prefix == '':
                final_name = f"{full_domain}."
            else:
                final_name = f"{record_prefix}.{full_domain}."

            self.r53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Comment': f'{action} by ARC CLI',
                    'Changes': [{
                        'Action': action,
                        'ResourceRecordSet': {
                            'Name': final_name,
                            'Type': 'A',
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