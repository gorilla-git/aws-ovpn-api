import boto3
from botocore.exceptions import NoRegionError, ClientError

class InstanceInfo:

    def get_all_regions(self):
        ec2 = boto3.client('ec2', region_name='us-east-1')
        regions = ec2.describe_regions()['Regions']
        return [region['RegionName'] for region in regions]

    def get_active_ec2_instances(self, region):
        ec2 = boto3.client('ec2', region_name=region)
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                },
                {
                    'Name': 'tag:vpn_api_finder', 
                    'Values': ['true']
                }
            ]
        )
        
        active_instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                name = None
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']
                        break
                
                instance_info = {
                    'InstanceId': instance['InstanceId'],
                    'InstanceType': instance['InstanceType'],
                    'Region': region,
                    'PublicIpAddress': instance.get('PublicIpAddress'),
                    'State': instance['State']['Name'],
                    'CPU': instance['CpuOptions']['CoreCount'],
                    'Placement': instance['Placement']['AvailabilityZone'],
                    'LaunchTime': instance['LaunchTime'].isoformat(),
                    'Lifecycle': instance.get('InstanceLifecycle', 'on-demand'),
                    'Name': name
                }
                active_instances.append(instance_info)

        return active_instances

    def get_active_instances_across_regions(self):
        all_regions = self.get_all_regions() 
        all_active_instances = []
    
        for region in all_regions:
            instances = self.get_active_ec2_instances(region)
            if instances:
                all_active_instances.extend(instances)
    
        return all_active_instances

    def terminate_instances(self, instance_ids, region):
        if not instance_ids:
            print("No instances to terminate.")
            return
        if not region:
            print("No region provided.")
            return

        ec2 = boto3.client('ec2', region_name=region)  
        try:
            response = ec2.terminate_instances(InstanceIds=instance_ids)
            print(f"Termination response: {response}")
        except ClientError as e:
            print(f"Error terminating instances: {e}")

    def get_instance_info_by_id(self, instance_id, region):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            response = ec2.describe_instances(InstanceIds=[instance_id])
            instances = response['Reservations']
            if instances:
                instance = instances[0]['Instances'][0]
                return {
                    'InstanceId': instance['InstanceId'],
                    'InstanceType': instance['InstanceType'],
                    'Region': region,
                    'PublicIpAddress': instance.get('PublicIpAddress'),
                    'State': instance['State']['Name'],
                    'CPU': instance['CpuOptions']['CoreCount'],
                    'Placement': instance['Placement']['AvailabilityZone'],
                    'LaunchTime': instance['LaunchTime'].isoformat(),
                    'Lifecycle': instance.get('InstanceLifecycle', 'on-demand'),
                    'Tags': instance.get('Tags', [])
                }
        except ClientError as e:
            if e.response['Error']['Code'] != 'InvalidInstanceID.NotFound':
                print(f"Error retrieving instance info: {e}")

        return None  

instance_types =    [
                    {'instance_name': 't3a.nano', 'vCPUs': 2, 'RAM': '0.5 GiB', 'cost': 1.68},
                    {'instance_name': 't3.nano', 'vCPUs': 2, 'RAM': '0.5 GiB', 'cost': 1.9},
                    {'instance_name': 't3a.micro', 'vCPUs': 2, 'RAM': '1 GiB', 'cost': 3.43},
                    {'instance_name': 't3.micro', 'vCPUs': 2, 'RAM': '1 GiB', 'cost': 3.8}]