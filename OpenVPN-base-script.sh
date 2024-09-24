#!/bin/bash

curl -o create-ami-user-data-script.sh "https://raw.githubusercontent.com/gorilla-git/aws-ovpn-api/main/create-ami-user-data-script.sh"

chmod +x create-ami-user-data-script.sh
sudo -u ubuntu ./create-ami-user-data-script.sh

sudo mkdir -p /home/ubuntu/easy-rsa
sudo mkdir -p /etc/openvpn

sudo chown -R ubuntu:ubuntu /home/ubuntu/easy-rsa
sudo chown -R ubuntu:ubuntu /etc/openvpn

sudo chmod -R 700 /home/ubuntu/easy-rsa
sudo chmod -R 700 /etc/openvpn

sudo rm create-ami-user-data-script.sh
