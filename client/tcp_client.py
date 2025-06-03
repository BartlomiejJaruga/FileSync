import socket
import json
import os
from common.protocol import MESSAGE_TYPES
from client.discovery import find_server


def get_file_metadata(archive_path):
    metadata = []
    for root, _, files in os.walk(archive_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, archive_path)
            mod_time = os.path.getmtime(full_path)
            metadata.append({
                "filename": file,
                "path": rel_path,
                "mod_time": mod_time
            })
    return metadata


def start_tcp_client(archive_path, client_id, server_host=None, server_port=None):
    if not server_host or not server_port:
        server_host, server_port = find_server()

    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                print(f"[CLIENT] Connecting to {server_host}:{server_port}...")
                sock.settimeout(5)
                sock.connect((server_host, server_port))
                sock.settimeout(None)

                initial_msg = sock.recv(1024)
                msg = json.loads(initial_msg.decode())

                if msg.get("type") == MESSAGE_TYPES["BUSY"]:
                    print("[CLIENT] Server is busy. Waiting for READY...")
                    while True:
                        wait_msg = sock.recv(1024)
                        ready_msg = json.loads(wait_msg.decode())
                        if ready_msg.get("type") == MESSAGE_TYPES["READY"]:
                            print("[CLIENT] Received READY. Proceeding with replication.")
                            break
                elif msg.get("type") == MESSAGE_TYPES["READY"]:
                    print("[CLIENT] Server is ready. Proceeding.")

                file_info = get_file_metadata(archive_path)
                payload = {
                    "type": "FILE_INFO",
                    "client_id": client_id,
                    "files": file_info
                }
                sock.send(json.dumps(payload).encode())
                print("[CLIENT] File metadata sent.")

                break
        except Exception as e:
            print(f"[CLIENT] Connection error: {e}. Reconnecting...")
