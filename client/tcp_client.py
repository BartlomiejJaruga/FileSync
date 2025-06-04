import socket
import json
import time
from datetime import datetime, timedelta
from common.protocol import MESSAGE_TYPES
from client.discovery import find_server, pause_event
from client.archive_utils import send_file, get_local_file_index


def connect_to_server():
    # Attempt to discover the server's IP and port via multicast
    print("===== LOOKING FOR NEW CONNECTION... =====")
    server_host, server_port = find_server()
    print(f"[CLIENT] Connecting to {server_host}:{server_port}...")

    # Create a new TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)  # Set a timeout for the connection attempt
    sock.connect((server_host, server_port))  # Connect to the server
    sock.settimeout(None)  # Remove timeout after successful connection
    return sock, server_host, server_port


def handle_initial_server_message(sock):
    # Receive the initial message from the server (READY or BUSY)
    initial_msg = sock.recv(1024)
    try:
        msg = json.loads(initial_msg.decode())
    except json.JSONDecodeError:
        raise Exception("Invalid response from server.")

    # If server is busy, wait until it sends READY
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
        raise Exception(f"Unexpected server message: {msg}")


def send_file_info(sock, archive_path, client_id):
    # Generate file metadata from the local archive
    file_info = get_local_file_index(archive_path)

    # Send metadata and client ID to the server
    payload = {
        "type": MESSAGE_TYPES["FILE_INFO"],
        "client_id": client_id,
        "files": file_info
    }
    sock.send((json.dumps(payload) + "\n").encode())
    print("[CLIENT] Sent file metadata.")
    return file_info


def wait_for_next_sync(msg):
    # Wait for the time specified by the server before syncing again
    wait_time = int(msg.get("time_in_seconds", 60))
    wake_time = datetime.now() + timedelta(seconds=wait_time)
    print(f"[CLIENT] Sleeping for {wait_time} seconds. Will wake at {wake_time.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(wait_time)


def upload_files(sock, archive_path, file_info, upload_list):
    # If there are no files to upload, skip this step
    if not upload_list:
        print("[CLIENT] No files need to be uploaded.")
        return

    # Loop through each file in the upload list
    print("[CLIENT] Files to upload:")
    for file in upload_list:
        print(f" - {file['path']}")
        # Find the file metadata in the local index
        match = next((f for f in file_info if f["path"] == file["path"]), None)
        if match:
            try:
                # Send the file over the socket
                send_file(sock, archive_path, match)
            except Exception as e:
                print(f"[CLIENT] Failed to send file {match['path']}: {e}")


def handle_sync_response(sock, archive_path, client_id, file_info):
    # Wait for a response from the server after sending metadata
    response = sock.recv(4096)
    try:
        msg = json.loads(response.decode())
    except json.JSONDecodeError:
        raise Exception("Failed to parse server response.")

    # If no files need syncing, sleep until the next scheduled sync
    if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
        print("[CLIENT] No files require sync...")
        wait_for_next_sync(msg)
        return

    # If files need to be uploaded
    elif msg.get("type") == MESSAGE_TYPES["ARCHIVE_TASKS"]:
        upload_list = msg.get("upload", [])
        upload_files(sock, archive_path, file_info, upload_list)

        # Expect a NEXT_SYNC message after file uploads
        next_msg = sock.recv(1024)
        try:
            msg = json.loads(next_msg.decode())
        except json.JSONDecodeError:
            raise Exception("Failed to parse NEXT_SYNC message after upload.")

        if msg.get("type") == MESSAGE_TYPES["NEXT_SYNC"]:
            wait_for_next_sync(msg)
            return
        else:
            raise Exception(f"Unexpected message after upload: {msg.get('type')}")

    else:
        raise Exception(f"Unexpected response type: {msg.get('type')}")


def start_tcp_client(archive_path, client_id):
    # Main synchronization loop
    while True:
        try:
            # Try to connect to the server
            sock, host, port = connect_to_server()
            with sock:
                # Once connected, pause discovery to avoid duplicate connections
                pause_event.set()

                # Handle the server's initial response (READY or BUSY)
                handle_initial_server_message(sock)

                # Send file metadata to the server
                file_info = send_file_info(sock, archive_path, client_id)

                # Handle the server's response to the metadata (e.g. files to upload)
                handle_sync_response(sock, archive_path, client_id, file_info)

        except (socket.error, ConnectionError) as e:
            # Connection-related error: print and retry after short pause
            print(f"[CLIENT] Connection error: {e}. Retrying in 5 seconds...")
            pause_event.clear()  # Allow discovery to resume
            time.sleep(5)

        except Exception as e:
            # Other unexpected errors: log and retry
            print(f"[CLIENT] Unexpected error: {e}. Retrying in 5 seconds...")
            pause_event.clear()
            time.sleep(5)
