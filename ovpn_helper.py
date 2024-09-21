import os
import subprocess
import uuid
import requests

username = os.getenv('USER') or os.getenv('USERNAME')
ca_cert_path = f'/home/{username}/easy-rsa/pki/ca.crt'
ta_key_path = f'/home/{username}/easy-rsa/ta.key'

def create_openvpn_config():
    config_content = """##############################################
# Sample client-side OpenVPN 2.0 config file #
# for connecting to multi-client server.     #
#                                            #
# This configuration can be used by multiple #
# clients, however each client should have   #
# its own cert and key files.                #
#                                            #
# On Windows, you might want to rename this  #
# file so it has a .ovpn extension           #
##############################################

# Specify that we are a client and that we
# will be pulling certain config file directives
# from the server.
client

# Use the same setting as you are using on
# the server.
# On most systems, the VPN will not function
# unless you partially or fully disable
# the firewall for the TUN/TAP interface.
;dev tap
dev tun

# Windows needs the TAP-Win32 adapter name
# from the Network Connections panel
# if you have more than one.  On XP SP2,
# you may need to disable the firewall
# for the TAP adapter.
;dev-node MyTap

# Are we connecting to a TCP or
# UDP server?  Use the same setting as
# on the server.
;proto tcp
proto udp

# The hostname/IP and port of the server.
# You can have multiple remote entries
# to load balance between the servers.
remote 13.212.96.98 1194
;remote my-server-2 1194

# Choose a random host from the remote
# list for load-balancing.  Otherwise
# try hosts in the order specified.
;remote-random

# Keep trying indefinitely to resolve the
# host name of the OpenVPN server.  Very useful
# on machines which are not permanently connected
# to the internet such as laptops.
resolv-retry infinite

# Most clients don't need to bind to
# a specific local port number.
nobind

# Downgrade privileges after initialization (non-Windows only)
user nobody
group nobody

# Try to preserve some state across restarts.
persist-key
persist-tun

# If you are connecting through an
# HTTP proxy to reach the actual OpenVPN
# server, put the proxy server/IP and
# port number here.  See the man page
# if your proxy server requires
# authentication.
;http-proxy-retry # retry on connection failures
;http-proxy [proxy server] [proxy port #]

# Wireless networks often produce a lot
# of duplicate packets.  Set this flag
# to silence duplicate packet warnings.
;mute-replay-warnings

# SSL/TLS parms.
# See the server config file for more
# description.  It's best to use
# a separate .crt/.key file pair
# for each client.  A single ca
# file can be used for all clients.
;ca ca.crt
;cert client.crt
;key client.key

# Verify server certificate by checking that the
# certificate has the correct key usage set.
# This is an important precaution to protect against
# a potential attack discussed here:
#  http://openvpn.net/howto.html#mitm
#
# To use this feature, you will need to generate
# your server certificates with the keyUsage set to
#   digitalSignature, keyEncipherment
# and the extendedKeyUsage to
#   serverAuth
# EasyRSA can do this for you.
remote-cert-tls server

# If a tls-auth key is used on the server
# then every client must also have the key.
;tls-auth ta.key 1

# Select a cryptographic cipher.
# If the cipher option is used on the server
# then you must also specify it here.
# Note that v2.4 client/server will automatically
# negotiate AES-256-GCM in TLS mode.
# See also the data-ciphers option in the manpage
;cipher AES-256-CBC
cipher AES-256-GCM
auth SHA256

# Enable compression on the VPN link.
# Don't enable this unless it is also
# enabled in the server config file.
#comp-lzo

key-direction 1


;script-security 2
;up /etc/openvpn/update-resolv-conf
;down /etc/openvpn/update-resolv-conf


;script-security 2
;up /etc/openvpn/update-systemd-resolved
;down /etc/openvpn/update-systemd-resolved
;down-pre
;dhcp-option DOMAIN-ROUTE .


# Set log file verbosity.
verb 3

# Silence repeating messages
;mute 20
"""

    with open('base.conf', 'w') as config_file:
        config_file.write(config_content)

class genrate_client():
    def __init__(self):
        self.username = os.getenv('USER') or os.getenv('USERNAME')
        self.ca_cert_path = f'/home/{username}/easy-rsa/pki/ca.crt'
        self.ta_key_path = f'/home/{username}/easy-rsa/ta.key'
        self.public_ip = self.get_external_ip_aws()
        create_openvpn_config()

    def get_external_ip_aws(self):
        response = requests.get('http://checkip.amazonaws.com')
        return response.text.strip()
        
    def generate_csr(self, client_name):
        username = os.getenv('USER') or os.getenv('USERNAME')
        command = ['./easyrsa', 'gen-req', client_name, 'nopass']
        cwd = f'/home/{username}/easy-rsa'
        process = subprocess.Popen(command, cwd=cwd,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, text=True)
        try:
            inputs = f"{client_name}\n"  
            inputs += ".\n" * 6 
            stdout, stderr = process.communicate(input=inputs, timeout=60)
            if process.returncode != 0:
                return None
            key_path = os.path.join(cwd, 'pki/private', f'{client_name}.key')
            req_path = os.path.join(cwd, 'pki/reqs', f'{client_name}.req')
            if os.path.exists(key_path) and os.path.exists(req_path):
                return [key_path, req_path]
            else:
                return None
        
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return None
        except Exception as e:
            return None
    
    def sign_request(self, client_name, password = None):
        try:
            command = ['./easyrsa', 'sign-req', 'client', client_name]
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=f'/home/{username}/easy-rsa' 
            )
            if password is None:
                inputs = f"yes\n"
            else:      
                inputs = f"yes\n{password}\n"
            stdout, stderr = process.communicate(inputs)
    
            if process.returncode != 0:
                print(f"Error signing request: {stderr.strip()}")
                return None
    
            cert_path = os.path.join(f'/home/{username}/easy-rsa/pki/issued', f'{client_name}.crt')
            if os.path.exists(cert_path):
                return cert_path
            else:
                print(f"Certificate not found at {cert_path}")
                return None
                
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            print(f"Process timed out: {stderr.strip()}")
            return None
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return None
    
    def modify_base_ip(self, output_file_path, new_ip):
        input_file_path = 'base.conf'
        with open(input_file_path, 'r') as file:
            lines = file.readlines()
    
        if len(lines) >= 42:
            lines[41] = lines[41].replace('{base_ip}', new_ip)
    
        with open(output_file_path, 'w') as file:
            file.writelines(lines)
    
    def create_ovpn(self, client_id):
        output_file = f"{client_id}.ovpn"
    
        with open(output_file, 'w') as ovpn_file:
            with open('modified_base.conf', 'r') as base_file:
                ovpn_file.write(base_file.read())
            
            ovpn_file.write('\n<ca>\n')
            with open(ca_cert_path, 'r') as ca_file:
                ovpn_file.write(ca_file.read())
            ovpn_file.write('\n</ca>\n')
    
            ovpn_file.write('\n<cert>\n')
            with open(f"/home/{username}/easy-rsa/pki/issued/{client_id}.crt", 'r') as cert_file:
                ovpn_file.write(cert_file.read())
            ovpn_file.write('\n</cert>\n')
    
            ovpn_file.write('\n<key>\n')
            with open(f"/home/{username}/easy-rsa/pki/private/{client_id}.key", 'r') as key_file:
                ovpn_file.write(key_file.read())
            ovpn_file.write('\n</key>\n')
    
            ovpn_file.write('\n<tls-crypt>\n')
            with open(ta_key_path, 'r') as ta_file:
                ovpn_file.write(ta_file.read())
            ovpn_file.write('\n</tls-crypt>\n')
    
        return output_file

    def registor_client(self):
        paths = []
        clientID = str(uuid.uuid4())
        password = ''
        output_file_path = 'modified_base.conf'

        result = self.generate_csr(clientID)
        
        if result is None :
            return None
        paths.extend(result)

        result = self.sign_request(clientID)

        if result is None :
            for i in paths:
                os.remove(i)
            return None
        paths.append(result)

        self.modify_base_ip(output_file_path, self.public_ip)

        result = self.create_ovpn(clientID)

        if result is None :
            for i in paths:
                os.remove(i)
            return None
            
        paths.append(result)

        with open(result, 'r') as file:
            contents = file.read()
            
        for i in paths:
            os.remove(i)
            
        return contents