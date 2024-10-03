import requests
import psycopg2
import socket
import time
import os
import tempfile
from datetime import datetime, timedelta

import requests

def create_vpn_instance(region):
    url = f"https://ec2-44-208-52-100.compute-1.amazonaws.com/connect_vpn/{region}"
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()  
        return response.json() 
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")

def clear_server_location_and_region(db_params, instance_id):
    update_query = """
    UPDATE servers
    SET region = '', location = ''
    WHERE instance_id = %s;
    """

    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        cur.execute(update_query, (instance_id,))
        conn.commit()

        if cur.rowcount > 0:
            print("Instance region and location cleared successfully.")
            return True
        else:
            print("No matching instance found to update.")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

instance_location = None

db_params = {
    'dbname': os.environ.get('DBNAME'),
    'user': os.environ.get('DBUSER'),
    'password': os.environ.get('DBPASSWORD'),
    'host': os.environ.get('DBHOST'),
    'port': os.environ.get('DBPORT')
}

LocAMI = {
    "America": {
        "us-east-1": {
            "city": "North Virginia"
        },
        "us-east-2": {
            "city": "Ohio"
        },
        "us-west-1": {
            "city": "Northern California"
        },
        "us-west-2": {
            "city": "Oregon"
        }
    },
    "Japan": {
        "ap-northeast-1": {
            "city": "Tokyo"
        },
        "ap-northeast-3": {
            "city": "Osaka"
        }
    },
    "Germany": {
        "eu-central-1": {
            "city": "Frankfurt"
        }
    },
    "Sweden": {
        "eu-north-1": {
            "city": "Stockholm"
        }
    },
    "France": {
        "eu-west-3": {
            "city": "Paris"
        }
    },
    "England": {
        "eu-west-2": {
            "city": "London"
        }
    },
    "Ireland": {
        "eu-west-1": {
            "city": "Ireland"
        }
    },
    "India": {
        "ap-south-1": {
            "city": "Mumbai"
        }
    },
    "South Korea": {
        "ap-northeast-2": {
            "city": "Seoul"
        }
    },
    "UAE": {
        "me-central-1": {
            "city": "UAE"
        }
    },
    "Canada": {
        "ca-central-1": {
            "city": "Canada"
        }
    },
    "Brazil": {
        "sa-east-1": {
            "city": "Sao Paulo"
        }
    },
    "Singapore": {
        "ap-southeast-1": {
            "city": "Singapore"
        }
    },
    "Australia": {
        "ap-southeast-2": {
            "city": "Sydney"
        }
    }
}

upload_limit = 2
download_limit = 2

def create_and_run_script(upload_limit, download_limit):

    upload_limit = str(upload_limit)
    download_limit = str(download_limit)
    
    script_content = f"""#!/bin/bash

    # Set your desired upload and download limits
    UPLOAD_LIMIT="{upload_limit}mbit"   # Change this to your desired upload limit (e.g., 512kbit, 2mbit)
    DOWNLOAD_LIMIT="{download_limit}mbit" # Change this to your desired download limit
    
    # Automatically get the OpenVPN tun interface
    VPN_INTERFACE=$(ip addr show | grep -o 'tun[0-9]*' | head -n 1)
    
    if [ -z "$VPN_INTERFACE" ]; then
        echo "No OpenVPN tun interface found. Please check your OpenVPN configuration."
        exit 1
    fi
    
    # Check if a qdisc already exists and delete it if it does
    if tc qdisc show dev $VPN_INTERFACE > /dev/null 2>&1; then
        tc qdisc del dev $VPN_INTERFACE root
    fi
    
    # Add a new root qdisc
    tc qdisc add dev $VPN_INTERFACE root handle 1: htb default 12
    
    # Create a class for the upload limit
    tc class add dev $VPN_INTERFACE parent 1: classid 1:1 htb rate $UPLOAD_LIMIT
    
    # Create a class for the download limit
    tc class add dev $VPN_INTERFACE parent 1: classid 1:2 htb rate $DOWNLOAD_LIMIT
    
    # Create a default class for other traffic
    tc class add dev $VPN_INTERFACE parent 1: classid 1:12 htb rate 10mbit
    
    # Add filters to match all packets for upload and download limits
    tc filter add dev $VPN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dst 0.0.0.0/0 flowid 1:2
    tc filter add dev $VPN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip src 0.0.0.0/0 flowid 1:1
    
    echo "Bandwidth limits set: Upload = $UPLOAD_LIMIT, Download = $DOWNLOAD_LIMIT on $VPN_INTERFACE."
    """

    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as script_file:
        script_file.write(script_content.encode())
        script_file_path = script_file.name
    os.system(f'sudo chmod +x {script_file_path}')
    os.system(f'sudo {script_file_path}')
    os.remove(script_file_path)

def get_location(region):
    for location, config in LocAMI.items():
        for edge_location in list(config.keys()):
            if  edge_location == region:
                return location
    return None

def update_connected_users(db_params, instance_id, total_connections):
    update_query = """
    UPDATE servers
    SET connected_users = %s
    WHERE instance_id = %s;
    """
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        cur.execute(update_query, (total_connections, instance_id))
        conn.commit()

        if cur.rowcount == 0:
            instance_info = get_instance_info()

            if instance_info:
                try:
                    insert_server(db_params, instance_info)
                    conn = psycopg2.connect(**db_params)
                    cur = conn.cursor()
                    cur.execute(update_query, (total_connections, instance_id))
                    conn.commit()

                    return True
                except:
                    return False
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def delete_server(db_params, instance_id: str) -> bool:
    global instance_location
    clear_server_location_and_region(db_params, instance_id)
    if instance_location is None:
        instance_location = get_instance_info()['location']
    create_vpn_instance(instance_location)

    if instance_id is None:
        return False

    delete_query = """
    DELETE FROM servers WHERE instance_id = %s;
    """

    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        cur.execute(delete_query, (instance_id,))
        conn.commit()
        
        if cur.rowcount == 0:
            return False

        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

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

def get_total_connections(management_host='127.0.0.1', management_port=7505):
    try:
        with socket.create_connection((management_host, management_port), timeout=5) as sock:
            sock.sendall(b'status 2\n')  
            response = sock.recv(4096).decode('utf-8')  

        connection_lines = [line for line in response.splitlines() if line.startswith('CLIENT_LIST')]
        total_connections = len(connection_lines)  
        return total_connections

    except Exception as e:
        print(f"Error: {e}")
        return 0

def get_token():
    url = "http://169.254.169.254/latest/api/token"
    response = requests.put(url, headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"})
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to get token: {response.status_code} {response.text}")
        return None

def get_instance_metadata(token, path):
    url = f"http://169.254.169.254/latest/meta-data/{path}"
    response = requests.get(url, headers={"X-aws-ec2-metadata-token": token})
    if response.status_code == 200:
        return response.text
    else:
        token = get_token()

def get_instance_info():
    token = get_token()
    if token is None:
        return None

    instance_id = get_instance_metadata(token, "instance-id")
    instance_type = get_instance_metadata(token, "instance-type")
    region = get_instance_metadata(token, "placement/region")
    public_ip = get_instance_metadata(token, "public-ipv4")
    lifecycle = get_instance_metadata(token, "instance-life-cycle") or "on-demand"  
    location = get_location(region)

    return {
        "instance_id": instance_id,
        "instance_type": instance_type,
        "region": region,
        "public_ip": public_ip,
        "location": location,
        "lifecycle": lifecycle
    }
 
def get_instance_id():
    token = get_token()
    while True:
        req = requests.get("http://169.254.169.254/latest/meta-data/instance-id", headers={"X-aws-ec2-metadata-token": token})
        if req.status_code == 401:
            token = get_token()
        else:
            break
    return req.text   
        
def check_interrupt(): # thread 1
    token = get_token()
    while True:
        req_1 = requests.get("http://169.254.169.254/latest/meta-data/spot/instance-action", headers={"X-aws-ec2-metadata-token": token})
        req_2 = requests.get("http://169.254.169.254/latest/meta-data/spot/termination-time", headers={"X-aws-ec2-metadata-token": token})

        if (req_1.status_code == 401) or (req_2.status_code == 401):
            token = get_token()
        if (req_1.status_code == 200) or (req_2.status_code == 200):
            #add create server
            instanceID = get_instance_id()
            for i in range(10):
                if delete_server(db_params, instanceID):
                    os.system("sudo shutdown now")
                    break

        time.sleep(5)
        
def monitor_connections(): # thread 2
    instance_id = get_instance_id()
    last_connection_count = None
    zero_users_since = None

    while True:
        total_connections = get_total_connections()

        if total_connections != last_connection_count:
            update_connected_users(db_params, instance_id, total_connections)
            last_connection_count = total_connections
            upload_limit = 2 * last_connection_count
            download_limit = 2 * last_connection_count
            create_and_run_script(upload_limit, download_limit)

        if total_connections == 0:
            if zero_users_since is None:
                zero_users_since = datetime.now()
            elif datetime.now() - zero_users_since > timedelta(minutes=10):
                if delete_server(db_params, instance_id):
                    os.system("sudo shutdown now")
                    break
        else:
            zero_users_since = None  
            
        time.sleep(5)

import threading
if __name__ == "__main__":
    threads = []
    threads.append(threading.Thread(target=check_interrupt, daemon=True))
    threads[-1].start()
    threads.append(threading.Thread(target=monitor_connections, daemon=True))
    threads[-1].start()

    try:
        while True:
            time.sleep(1)  
    except KeyboardInterrupt:
        print("Exiting program...")
