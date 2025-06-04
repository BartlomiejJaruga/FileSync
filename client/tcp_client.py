import socket
import json
import time
from datetime import datetime, timedelta
from common.protocol import MESSAGE_TYPES
from client.discovery import find_server, pause_event
from client.archive_utils import send_file, get_local_file_index


def start_tcp_client(archive_path, client_id):
    while True:
        try:
            server_host, server_port = find_server()
            print(f"[CLIENT] Connecting to {server_host}:{server_port}...")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((server_host, server_port))
                sock.settimeout(None)

                pause_event.set()

                initial_msg = sock.recv(1024)
                msg = json.loads(initial_msg.decode())

                if msg.get("type") == MESSAGE_TYPES["BUSY"]:
                    print("[CLIENT] Server is busy. Waiting for READY...")
                    while True:
                        wait_msg = sock.recv(1024)
                        ready_msg = json.loads(wait_msg.decode())
                        if ready_msg.get("type") == MESSAGE_TYPES["READY"]:
                            print("[CLIENT] Received READY. Proceeding.")
                            break
                elif msg.get("type") == MESSAGE_TYPES["READY"]:
                    print("[CLIENT] Server is ready. Proceeding.")

                file_info = get_local_file_index(archive_path)
                payload = {
                    "type": MESSAGE_TYPES["FILE_INFO"],
                    "client_id": client_id,
                    "files": file_info
                }
                sock.send((json.dumps(payload) + "\n").encode())
                print("[CLIENT] Sent file metadata.")

                response = sock.recv(4096)
                msg = json.loads(response.decode())

                if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
                    wait_time = int(msg.get("time_in_seconds", "60"))
                    wake_time = datetime.now() + timedelta(seconds=wait_time)
                    print(f"[CLIENT] No files to sync. Sleeping for {wait_time} seconds.")
                    print(f"[CLIENT] Will wake and retry at: {wake_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    time.sleep(wait_time)
                    continue

                elif msg.get("type") == MESSAGE_TYPES["ARCHIVE_TASKS"]:
                    upload_list = msg.get("upload", [])
                    if not upload_list:
                        print("[CLIENT] No files need to be uploaded.")
                    else:
                        print("[CLIENT] Files to upload:")
                        for file in upload_list:
                            print(f" - {file['path']}")
                            match = next((f for f in file_info if f["path"] == file["path"]), None)
                            if match:
                                send_file(sock, archive_path, match)

                    next_msg = sock.recv(1024)
                    msg = json.loads(next_msg.decode())
                    if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
                        wait_time = int(msg.get("time_in_seconds", "60"))
                        wake_time = datetime.now() + timedelta(seconds=wait_time)
                        print(f"[CLIENT] Sync complete. Sleeping for {wait_time} seconds.")
                        print(f"[CLIENT] Will wake and retry at: {wake_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        time.sleep(wait_time)
                        continue

        except Exception as e:
            print(f"[CLIENT] Connection error: {e}. Retrying in 5 seconds...")
            pause_event.clear()
            time.sleep(5)
