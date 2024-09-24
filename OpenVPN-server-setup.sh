#!/bin/bash

curl -o ami-script-setup.sh "https://raw.githubusercontent.com/gorilla-git/aws-ovpn-api/main/ami-script-setup.sh"

chmod +x ami-script-setup.sh 

sudo -u ubuntu ./ami-script-setup.sh 

sudo rm ami-script-setup.sh 

sudo chown -R ubuntu:ubuntu /home/ubuntu/easy-rsa
sudo chown -R ubuntu:ubuntu /etc/openvpn

sudo chmod -R 700 /home/ubuntu/easy-rsa
sudo chmod -R 700 /etc/openvpn
