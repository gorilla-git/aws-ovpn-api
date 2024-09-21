#!/bin/bash

sudo apt update
sudo apt install -y openvpn easy-rsa

mkdir /home/ubuntu/easy-rsa 
ln -s /usr/share/easy-rsa/* /home/ubuntu/easy-rsa/

cd /home/ubuntu/easy-rsa 
./easyrsa init-pki

cd /home/ubuntu/easy-rsa || { echo "Directory not found"; exit 1; }

cat <<EOF2 > vars
set_var EASYRSA_REQ_COUNTRY    "US"
set_var EASYRSA_REQ_PROVINCE   "NewYork"
set_var EASYRSA_REQ_CITY       "New York City"
set_var EASYRSA_REQ_ORG        "DigitalOcean"
set_var EASYRSA_REQ_EMAIL      "admin@example.com"
set_var EASYRSA_REQ_OU         "Community"
set_var EASYRSA_ALGO           "ec"
set_var EASYRSA_DIGEST         "sha512"
EOF2

echo "vars file has been updated successfully."

cd /home/ubuntu/easy-rsa && printf '\n' | ./easyrsa build-ca nopass
cd /home/ubuntu/easy-rsa && printf '\n' | ./easyrsa gen-req server nopass

printf 'yes\n' | ./easyrsa sign-req server server

openvpn --genkey secret ta.key

sudo cp /home/ubuntu/easy-rsa/ta.key /etc/openvpn/server/
sudo cp /home/ubuntu/easy-rsa/pki/ca.crt /etc/openvpn/server/
sudo cp /home/ubuntu/easy-rsa/pki/issued/server.crt /etc/openvpn/server/
sudo cp /home/ubuntu/easy-rsa/pki/private/server.key /etc/openvpn/server/

sudo rm -f /etc/openvpn/server/server.conf
cat <<EOF3 | sudo tee /etc/openvpn/server/server.conf > /dev/null
port 1194
proto udp
dev tun

ca ca.crt
cert server.crt
key server.key  
dh none

server 10.8.0.0 255.255.255.0
ifconfig-pool-persist /var/log/openvpn/ipp.txt

push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 208.67.222.222"
push "dhcp-option DNS 208.67.220.220"
keepalive 10 120
tls-crypt ta.key

cipher AES-256-GCM
auth SHA256

user nobody
group nobody

persist-key
persist-tun

status /var/log/openvpn/openvpn-status.log

verb 3

explicit-exit-notify 1
EOF3

echo "OpenVPN configuration file has been created successfully."

sudo rm /etc/sysctl.conf
echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.conf > /dev/null

sudo sysctl -p

#default_interface=$(ip route list default | awk '{print $5}')

# Get the default interface dynamically
default_interface=$(ip route list default | awk '{print $5}')

# Define the rules with the dynamic interface
RULES=$(cat <<EOF
*nat
:POSTROUTING ACCEPT [0:0]
-A POSTROUTING -s 10.8.0.0/8 -o $default_interface -j MASQUERADE
COMMIT
EOF
)

UFW_RULES_FILE="/etc/ufw/before.rules"

if ! grep -q "START OPENVPN RULES" "$UFW_RULES_FILE"; then
    sudo cp "$UFW_RULES_FILE" "$UFW_RULES_FILE.bak" 
    sudo echo "$RULES" | sudo cat - "$UFW_RULES_FILE" > /tmp/ufw_rules_temp && sudo mv /tmp/ufw_rules_temp "$UFW_RULES_FILE"
    echo "OpenVPN rules added to the top of $UFW_RULES_FILE"
else
    echo "OpenVPN rules already exist in $UFW_RULES_FILE"
fi

#sudo sed -i "/-A POSTROUTING/s/-o [^ ]*/-o \$default_interface/" /etc/ufw/before.rules

sudo sed -i 's/^DEFAULT_FORWARD_POLICY=".*"/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw

if ! getent group nobody > /dev/null; then
    sudo groupadd nobody
fi

sudo ufw enable
sudo ufw allow OpenSSH
sudo ufw allow 1194/udp
sudo ufw allow 8000

sudo ufw disable
sudo ufw enable

sudo systemctl -f enable openvpn-server@server.service
sudo systemctl start openvpn-server@server.service

cd /home/ubuntu/
git clone https://github.com/gorilla-git/aws-ovpn-api.git
cd aws-ovpn-api

sudo apt install -y python3 python3-venv
python3 -m venv env
source env/bin/activate
pip install fastapi uvicorn boto3 jupyterlab

jupyter lab --ip='0.0.0.0' --port=8000 --NotebookApp.token='' --NotebookApp.password='' --no-browser
