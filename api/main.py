from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from typing import List
import os

import uuid
from src.user_cert import genrate_client
from src.user_cert import insert_user_cert
from src.user_cert import search_servers_by_region
from src.loc import get_available_locations

from src.user_cert import db_params
from src.loc import LocAMI
from src.inst_info import instance_types
from src.instance import block_device_mappings
from src.instance import user_data_script
from src.instance import create_instance_save_db

def generate_response(response_message , response_status ,uuid_code , metadata):

    response_dict = {
                "response_message" : response_message,
                "response_status" : response_status,
                "data" :{
                    "UUID" : uuid_code,
                    "metadata" : metadata
                }
            }

    return response_dict

def gen_user_certs(clientID):
    user_cert = genrate_client()
    paths = user_cert.registor_client(clientID)

    if paths is None:
        return None

    key_path = paths[0]
    cert_path = paths[2]  

    with open(key_path, 'r') as key_file:
        key_content = key_file.read()

    with open(cert_path, 'r') as cert_file:
        cert_content = cert_file.read()

    if insert_user_cert(db_params, clientID, key_content, cert_content, True):
        for i in paths:
            os.remove(i)
        os.remove('base.conf')
        os.remove('modified_base.conf')
        return True
    return False

db_params = {
    'dbname': 'dbvpn',
    'user': 'postgres',
    'password': '4b95dfe8-4644-46ce-a4fe-648d6d4860a4',
    'host': '44.208.52.100',
    'port': '5432'
}

app = FastAPI()

@app.post("/register_user")
def register_user():
    clientID = str(uuid.uuid4())
    stat = gen_user_certs(clientID)
    if stat:
        return generate_response("User Registered Successfully" , "True" ,clientID , [])
    return generate_response("User Registered Un-Successful" , "False" ,'' , [])

@app.get("/available_regions")
def available_regions():
    regions = get_available_locations()
    return generate_response("All Regions" , "True" ,'' , regions)

@app.get("/connect_vpn/{region}")
def connect_vpn(region: str):
    regions = get_available_locations()
    if region not in regions:
        return generate_response("Enter Valid Region" , "False" ,'' , [])

    edge_loc = LocAMI[region]
    least_connected_server = None

    for i in edge_loc:
        servers = search_servers_by_region(db_params, i)
        if servers:
            least_connected_server = min(servers, key=lambda x: x[5])  
            break

    if least_connected_server:
        return generate_response("IP for server", "True", "", [least_connected_server[2]])

    resp = create_instance_save_db(db_params, LocAMI, instance_types, region)
    if resp is not None:
        return generate_response("IP for server", "True", "", [resp['public_ip']])
    return generate_response("Error Connecting To Server", "False", "", [])
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)