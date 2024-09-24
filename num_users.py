import socket
import time

def get_connected_clients(management_host='127.0.0.1', management_port=7505):
    try:
        with socket.create_connection((management_host, management_port), timeout=5) as sock:
            sock.sendall(b'status 2\n')  
            response = sock.recv(4096).decode('utf-8')  
        client_lines = [line for line in response.splitlines() if line.startswith('CLIENT_LIST')]
        return len(client_lines)

    except Exception as e:
        print(f"Error: {e}")
        return 0

if __name__ == "__main__":
    num_clients = get_connected_clients()
    print(f"Number of connected clients: {num_clients}")


import socket

def get_total_connections(management_host='127.0.0.1', management_port=7505):
    try:
        with socket.create_connection((management_host, management_port), timeout=5) as sock:
            sock.sendall(b'status 2\n')  
            response = sock.recv(4096).decode('utf-8')  

        # Count total connections from the CLIENT_LIST lines
        connection_lines = [line for line in response.splitlines() if line.startswith('CLIENT_LIST')]
        total_connections = len(connection_lines)  # Each line corresponds to a connection
        return total_connections

    except Exception as e:
        print(f"Error: {e}")
        return 0

if __name__ == "__main__":
    total_connections = get_total_connections()
    print(f"Total connections: {total_connections}")

