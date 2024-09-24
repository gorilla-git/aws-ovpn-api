#!/bin/bash

sudo apt update
sudo apt install -y openvpn easy-rsa

cd /home/ubuntu/
sudo apt install -y python3 python3-venv
python3 -m venv env
source env/bin/activate
pip install fastapi uvicorn boto3 psycopg2-binary jupyterlab

mkdir /home/ubuntu/easy-rsa 
ln -s /usr/share/easy-rsa/* /home/ubuntu/easy-rsa/

cd /home/ubuntu/easy-rsa 
./easyrsa init-pki

cd /home/ubuntu/easy-rsa || { echo "Directory not found"; exit 1; }

cat <<EOF1 > vars
set_var EASYRSA_REQ_COUNTRY    "US"
set_var EASYRSA_REQ_PROVINCE   "NewYork"
set_var EASYRSA_REQ_CITY       "New York City"
set_var EASYRSA_REQ_ORG        "QuantumGrove"
set_var EASYRSA_REQ_EMAIL      "info@quantumgrove.tech"
set_var EASYRSA_REQ_OU         "Community"
set_var EASYRSA_ALGO           "ec"
set_var EASYRSA_DIGEST         "sha512"
EOF1

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
cat <<EOF2 | sudo tee /etc/openvpn/server/server.conf > /dev/null
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
EOF2

echo "OpenVPN configuration file has been created successfully."

sudo rm /etc/sysctl.conf
echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.conf > /dev/null

sudo sysctl -p
