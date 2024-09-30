import boto3
import time
from botocore.exceptions import ClientError

import requests
import psycopg2
import socket
import time
import os
import tempfile
from datetime import datetime, timedelta

def launch_ec2_spot_instance(region, max_spot_price, ami_id, user_data, block_device_mappings, instance_types, security_group_ids):
    ec2_client = boto3.client('ec2', region_name=region)

    instance = None
    max_price_tries = 10
    decrement = max_spot_price / 4 / (max_price_tries - 1) 
    
    for instance_type in instance_types:
        for i in range(max_price_tries):
            price = max_spot_price - (decrement * (max_price_tries - 1 - i))
            try:
                print(f"Attempting to launch spot instance at ${price} in {region} with instance type {instance_type}")
                response = ec2_client.run_instances(
                    BlockDeviceMappings=block_device_mappings,
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    MaxCount=1,
                    MinCount=1,
                    Monitoring={'Enabled': True},
                    Placement={'Tenancy': 'default'},
                    UserData=user_data,
                    InstanceInitiatedShutdownBehavior='terminate',
                    InstanceMarketOptions={
                        'MarketType': 'spot',
                        'SpotOptions': {
                            'MaxPrice': str(price),
                            'SpotInstanceType': 'one-time',
                            'InstanceInterruptionBehavior': 'terminate'
                        }
                    },
                    TagSpecifications=[
                        {
                            'ResourceType': 'instance',
                            'Tags': [{'Key': 'Name', 'Value': 'OpenVPN-Server'}, {'Key': 'api-test-key', 'Value': 'true-test'}]
                        }
                    ],
                    SecurityGroupIds=security_group_ids 
                )
                instance = response['Instances'][0]
                print(f"Launched Spot EC2 Instance with ID: {instance['InstanceId']} and type: {instance_type}")

                waiter = ec2_client.get_waiter('instance_running')
                waiter.wait(InstanceIds=[instance['InstanceId']])
                
                instance_info = ec2_client.describe_instances(InstanceIds=[instance['InstanceId']])
                public_ip = instance_info['Reservations'][0]['Instances'][0].get('PublicIpAddress')

                return {
                    'InstanceId': instance['InstanceId'],
                    'InstanceType': instance_type,
                    'PublicIpAddress': public_ip
                }

            except ClientError as e:
                print(f"Spot instance launch failed at ${price} with instance type {instance_type} due to: {e}")
                if 'InsufficientInstanceCapacity' in str(e) or 'Unsupported' in str(e):
                    continue 
                elif 'MaxSpotInstanceCountExceeded' in str(e):
                    continue
                else:
                    raise e
        
    return None 

def launch_ec2_od_instance(region, ami_id, user_data, block_device_mappings, instance_types, security_group_ids):
    ec2_client = boto3.client('ec2', region_name=region)

    instance = None
    
    for instance_type in instance_types:
            try:
                response = ec2_client.run_instances(
                    BlockDeviceMappings=block_device_mappings,
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    MaxCount=1,
                    MinCount=1,
                    Monitoring={'Enabled': True},
                    Placement={'Tenancy': 'default'},
                    UserData=user_data,
                    InstanceInitiatedShutdownBehavior='terminate',
                    TagSpecifications=[
                        {
                            'ResourceType': 'instance',
                            'Tags': [{'Key': 'Name', 'Value': 'OpenVPN-Server'}, {'Key': 'api-test-key', 'Value': 'true-test'}]
                        }
                    ],
                    SecurityGroupIds=security_group_ids  
                )
                instance = response['Instances'][0]
                print(f"Launched On-Demand EC2 Instance with ID: {instance['InstanceId']} and type: {instance_type}")
                waiter = ec2_client.get_waiter('instance_running')
                waiter.wait(InstanceIds=[instance['InstanceId']])
                
                instance_info = ec2_client.describe_instances(InstanceIds=[instance['InstanceId']])
                public_ip = instance_info['Reservations'][0]['Instances'][0].get('PublicIpAddress')

                return {
                    'InstanceId': instance['InstanceId'],
                    'InstanceType': instance_type,
                    'PublicIpAddress': public_ip
                }

            except ClientError as e:
                print(f"On-demand instance launch failed with instance type {instance_type} due to: {e}")
                continue
                
            return None

block_device_mappings = [
    {
        'DeviceName': '/dev/sda1',
        'Ebs': {
            'DeleteOnTermination': True,
            'VolumeSize': 8,
            'VolumeType': 'gp2'
        }
    }
]

user_data_script = '''#!/bin/bash

curl -o ami-script-setup.sh "https://raw.githubusercontent.com/gorilla-git/aws-ovpn-api/main/ami-script-setup.sh"

chmod +x ami-script-setup.sh 

sudo -u ubuntu ./ami-script-setup.sh 

sudo rm ami-script-setup.sh 

sudo chown -R ubuntu:ubuntu /home/ubuntu/easy-rsa
sudo chown -R ubuntu:ubuntu /etc/openvpn

sudo chmod -R 700 /home/ubuntu/easy-rsa
sudo chmod -R 700 /etc/openvpn

export DBNAME='dbvpn'
export DBUSER='postgres'
export DBPASSWORD='4b95dfe8-4644-46ce-a4fe-648d6d4860a4'
export DBHOST='44.208.52.100'
export DBPORT='5432'

source /home/ubuntu/env/bin/activate
pip install psycopg2-binary

curl -L -o /home/ubuntu/main.py https://raw.githubusercontent.com/gorilla-git/aws-ovpn-api/main/OepnVPN-server-main.py

chmod +x /home/ubuntu/main.py
sudo chown -R ubuntu:ubuntu /home/ubuntu/main.py
sudo chmod -R 700 /home/ubuntu/main.py

nohup python3 /home/ubuntu/main.py &
echo "@reboot ubuntu /usr/bin/python3 /home/ubuntu/main.py" | sudo tee -a /etc/crontab
'''

def insert_server(db_params, instance_info):
    insert_query = """
    INSERT INTO servers (instance_id, instance_type, region, public_ip_address, location, lifecycle)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (instance_id) DO NOTHING;
    """

    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        cur.execute(insert_query, (
            instance_info["instance_id"], 
            instance_info["instance_type"], 
            instance_info["region"], 
            instance_info["public_ip"], 
            instance_info["location"], 
            instance_info["lifecycle"]
        ))
        conn.commit()

        if cur.rowcount > 0:
            print("Instance info inserted successfully.")
            return True
        else:
            print("Instance info already exists in the database.")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def create_instance_save_db(db_params, LocAMI, instance_types, region_name):
    region_configs = LocAMI.get(region_name, {})
    for region, config in region_configs.items():
        for instance_info in instance_types:
            ami_id = config['ami']
            security_group_id = config['sg_id']
            instance_type = instance_info['instance_name']
            max_price = instance_info['cost']

            try:
                spot_instance_info = launch_ec2_spot_instance(
                    region=region,
                    max_spot_price=max_price,
                    ami_id=ami_id,
                    user_data=user_data_script,
                    block_device_mappings=block_device_mappings,
                    instance_types=[instance_type],
                    security_group_ids=[security_group_id]
                )
                if spot_instance_info:
                    instance_info = {
                        "instance_id": spot_instance_info['InstanceId'],
                        "instance_type": spot_instance_info['InstanceType'],
                        "region": region,
                        "public_ip": spot_instance_info['PublicIpAddress'],
                        "location": region,
                        "lifecycle": "spot"
                    }
                    insert_server(db_params, instance_info)
                    return instance_info
            except:
                continue 
                
    for region, config in region_configs.items():
        for instance_info in instance_types:
            ami_id = config['ami']
            security_group_id = config['sg_id']
            instance_type = instance_info['instance_name']
            try:
                od_instance_info = launch_ec2_od_instance(
                    region=region,
                    ami_id=ami_id,
                    user_data=user_data_script,
                    block_device_mappings=block_device_mappings,
                    instance_types=[instance_type],
                    security_group_ids=[security_group_id]
                )
                if od_instance_info:
                    instance_info = {
                        "instance_id": od_instance_info['InstanceId'],
                        "instance_type": od_instance_info['InstanceType'],
                        "region": region,
                        "public_ip": od_instance_info['PublicIpAddress'],
                        "location": region,
                        "lifecycle": "on-demand"
                    }
                    insert_server(db_params, instance_info)
                    return instance_info
            except:
                continue
    return None