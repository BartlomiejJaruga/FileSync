import socket
import json
import os
from common.protocol import MESSAGE_TYPES
from client.discovery import find_server
from client.archive_utils import send_file, get_local_file_index


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

                # Send file metadata
                file_info = get_local_file_index(archive_path)
                payload = {
                    "type": MESSAGE_TYPES["FILE_INFO"],
                    "client_id": client_id,
                    "files": file_info
                }
                sock.send((json.dumps(payload) + "\n").encode())
                print("[CLIENT] File metadata sent.")

                # Wait for either ARCHIVE_TASKS or NEXT_SYNC
                response = sock.recv(4096)
                msg = json.loads(response.decode())

                if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
                    print("[CLIENT] No files to synchronize. Sync complete.")
                    return

                elif msg.get("type") == MESSAGE_TYPES["ARCHIVE_TASKS"]:
                    upload_list = msg.get("upload", [])
                    if not upload_list:
                        print("[CLIENT] No files need to be uploaded.")
                    else:
                        print("[CLIENT] Files to upload:")
                        for file in upload_list:
                            print(" -", file["path"])
                            match = next((f for f in file_info if f["path"] == file["path"]), None)
                            if match:
                                send_file(sock, archive_path, match)

                # Wait for NEXT_SYNC after sending files
                while True:
                    next_msg = sock.recv(1024)
                    msg = json.loads(next_msg.decode())
                    if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
                        print("[CLIENT] Sync completed. Server responded with NEXT_SYNC.")
                        return

        except Exception as e:
            print(f"[CLIENT] Connection error: {e}. Reconnecting...")

