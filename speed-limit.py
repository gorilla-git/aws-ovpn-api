import os
import tempfile

def create_and_run_script(upload_limit, download_limit):
    script_content = f"""#!/bin/bash

    # Set your desired upload and download limits
    UPLOAD_LIMIT="{upload_limit}"   # Change this to your desired upload limit (e.g., 512kbit, 2mbit)
    DOWNLOAD_LIMIT="{download_limit}" # Change this to your desired download limit
    
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

    # Create a temporary .sh file
    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as script_file:
        script_file.write(script_content.encode())
        script_file_path = script_file.name

    # Make the script executable
    os.system(f'sudo chmod +x {script_file_path}')
    
    # Run the script
    os.system(f'sudo {script_file_path}')
    
    # Remove the script file
    os.remove(script_file_path)

if __name__ == "__main__":
    # Ask user for upload and download limits
    upload_limit = input("Enter the desired upload limit (e.g., '100mbit', '512kbit'): ")
    download_limit = input("Enter the desired download limit (e.g., '100mbit', '512kbit'): ")
    
    create_and_run_script(upload_limit, download_limit)
