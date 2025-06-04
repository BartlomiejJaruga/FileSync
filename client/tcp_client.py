import socket
import json
import time
from datetime import datetime, timedelta
from common.protocol import MESSAGE_TYPES
from client.discovery import find_server, pause_event
from client.archive_utils import send_file, get_local_file_index


def start_tcp_client(archive_path, client_id):
    # Main loop: constantly try to connect to the server and sync files
    while True:
        try:
            # Discover server address and port
            server_host, server_port = find_server()
            print(f"[CLIENT] Connecting to {server_host}:{server_port}...")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)  # Set initial timeout for connect phase
                sock.connect((server_host, server_port))
                sock.settimeout(None)  # Remove timeout after successful connection

                pause_event.set()  # Pause further discovery attempts

                # Receive initial message (READY or BUSY)
                initial_msg = sock.recv(1024)
                try:
                    msg = json.loads(initial_msg.decode())
                except json.JSONDecodeError:
                    print("[CLIENT] Invalid response from server.")
                    continue

                # Handle BUSY server
                if msg.get("type") == MESSAGE_TYPES["BUSY"]:
                    print("[CLIENT] Server is busy. Waiting for READY...")
                    while True:
                        wait_msg = sock.recv(1024)
                        try:
                            ready_msg = json.loads(wait_msg.decode())
                        except json.JSONDecodeError:
                            print("[CLIENT] Invalid message while waiting for READY.")
                            continue
                        if ready_msg.get("type") == MESSAGE_TYPES["READY"]:
                            print("[CLIENT] Received READY. Proceeding.")
                            break

                elif msg.get("type") == MESSAGE_TYPES["READY"]:
                    print("[CLIENT] Server is ready. Proceeding.")
                else:
                    print(f"[CLIENT] Unexpected server message: {msg}")
                    continue

                # Generate and send local file index
                file_info = get_local_file_index(archive_path)
                payload = {
                    "type": MESSAGE_TYPES["FILE_INFO"],
                    "client_id": client_id,
                    "files": file_info
                }
                sock.send((json.dumps(payload) + "\n").encode())
                print("[CLIENT] Sent file metadata.")

                # Receive ARCHIVE_TASKS or NEXT_SYNC
                response = sock.recv(4096)
                try:
                    msg = json.loads(response.decode())
                except json.JSONDecodeError:
                    print("[CLIENT] Failed to parse server response.")
                    continue

                if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
                    # No files need to be uploaded
                    wait_time = int(msg.get("time_in_seconds", "60"))
                    wake_time = datetime.now() + timedelta(seconds=wait_time)
                    print(f"[CLIENT] No files to sync. Sleeping for {wait_time} seconds.")
                    print(f"[CLIENT] Will wake and retry at: {wake_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    time.sleep(wait_time)
                    continue

                elif msg.get("type") == MESSAGE_TYPES["ARCHIVE_TASKS"]:
                    # Upload files listed in the task
                    upload_list = msg.get("upload", [])
                    if not upload_list:
                        print("[CLIENT] No files need to be uploaded.")
                    else:
                        print("[CLIENT] Files to upload:")
                        for file in upload_list:
                            print(f" - {file['path']}")
                            # Match the file info from local index
                            match = next((f for f in file_info if f["path"] == file["path"]), None)
                            if match:
                                try:
                                    send_file(sock, archive_path, match)
                                except Exception as e:
                                    print(f"[CLIENT] Failed to send file {match['path']}: {e}")

                    # Expect NEXT_SYNC after uploads
                    next_msg = sock.recv(1024)
                    try:
                        msg = json.loads(next_msg.decode())
                    except json.JSONDecodeError:
                        print("[CLIENT] Failed to parse NEXT_SYNC message.")
                        continue

                    if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
                        wait_time = int(msg.get("time_in_seconds", "60"))
                        wake_time = datetime.now() + timedelta(seconds=wait_time)
                        print(f"[CLIENT] Sync complete. Sleeping for {wait_time} seconds.")
                        print(f"[CLIENT] Will wake and retry at: {wake_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        time.sleep(wait_time)
                        continue

                else:
                    print(f"[CLIENT] Unexpected response type: {msg.get('type')}")

        except (socket.error, ConnectionError) as e:
            # Handle connection-related exceptions
            print(f"[CLIENT] Connection error: {e}. Retrying in 5 seconds...")
            pause_event.clear()
            time.sleep(5)

        except Exception as e:
            # Catch-all for other unexpected exceptions
            print(f"[CLIENT] Unexpected error: {e}. Retrying in 5 seconds...")
            pause_event.clear()
            time.sleep(5)
