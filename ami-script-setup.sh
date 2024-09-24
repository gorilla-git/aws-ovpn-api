#!/bin/bash

start_time=$(date +%s)

sudo sysctl -p
default_interface=$(ip route list default | awk '{print $5}')

RULES=$(cat <<EOF1
*nat
:POSTROUTING ACCEPT [0:0]
-A POSTROUTING -s 10.8.0.0/8 -o $default_interface -j MASQUERADE
COMMIT
EOF1
)

UFW_RULES_FILE="/etc/ufw/before.rules"

if ! grep -q "START OPENVPN RULES" "$UFW_RULES_FILE"; then
    sudo cp "$UFW_RULES_FILE" "$UFW_RULES_FILE.bak" 
    sudo echo "$RULES" | sudo cat - "$UFW_RULES_FILE" > /tmp/ufw_rules_temp && sudo mv /tmp/ufw_rules_temp "$UFW_RULES_FILE"
    echo "OpenVPN rules added to the top of $UFW_RULES_FILE"
else
    echo "OpenVPN rules already exist in $UFW_RULES_FILE"
fi

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

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Script execution completed in $elapsed_time seconds."

#chmod +x /tmp/script.sh
#sudo -u ubuntu /tmp/script.sh
#sudo rm /tmp/script.sh

#sudo chown -R ubuntu:ubuntu ~/easy-rsa
#sudo chown -R ubuntu:ubuntu /etc/openvpn

