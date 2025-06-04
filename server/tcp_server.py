import socket
import threading
import queue
import json
import os

from common.protocol import MESSAGE_TYPES, make_next_sync_message
from server.archive_handler import (
    ensure_client_archive_dir,
    get_server_file_index,
    compare_file_indexes,
    save_file_stream
)

# Lock to safely manage access to the active client
active_client_lock = threading.Lock()

# Reference to the currently active client connection
active_client = None

# Queue for clients waiting to be served
client_queue = queue.Queue()


def recv_json_message(conn):
    # Receives a JSON message terminated by a newline character '\n'
    buffer = b""
    try:
        while True:
            chunk = conn.recv(1)
            if not chunk:
                break
            if chunk == b"\n":
                break
            buffer += chunk
        return json.loads(buffer.decode())
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"[TCP SERVER] Error receiving JSON message: {e}")
        return None


def handle_client(conn, addr, sync_interval_seconds):
    # Top-level handler for a client connection
    global active_client
    print(f"[TCP SERVER] Connected with client {addr}")

    try:
        process_client_session(conn, addr, sync_interval_seconds)
    except Exception as e:
        print(f"[TCP SERVER] Error with {addr}: {e}")
    finally:
        cleanup_connection(conn, addr)
        start_next_client(sync_interval_seconds)


def process_client_session(conn, addr, sync_interval_seconds):
    # Processes the client's session by handling messages and file transfers
    client_id = None
    expected_files = {}

    while True:
        msg = recv_json_message(conn)
        if not msg:
            print(f"[TCP SERVER] Client {addr} disconnected or sent invalid message.")
            break

        msg_type = msg.get("type")
        if msg_type == MESSAGE_TYPES.get("FILE_INFO"):
            client_id, expected_files = handle_file_info(conn, msg, sync_interval_seconds, addr)
            if not expected_files:
                break
        elif msg_type == MESSAGE_TYPES.get("FILE_TRANSFER"):
            handle_file_transfer(conn, msg, client_id, expected_files, sync_interval_seconds, addr)
            if not expected_files:
                break
        else:
            print(f"[TCP SERVER] Unknown message type from {addr}: {msg_type}")

    return client_id, expected_files


def handle_file_info(conn, msg, sync_interval_seconds, addr):
    # Handles FILE_INFO message: determines which files need to be uploaded or deleted
    client_id = msg["client_id"]
    ensure_client_archive_dir(client_id)

    client_files = msg["files"]
    server_index = get_server_file_index(client_id)
    client_index = {f["path"]: f["mod_time"] for f in client_files}

    to_upload, to_delete = compare_file_indexes(server_index, client_index)
    expected_files = {f["path"]: f for f in client_files if f["path"] in to_upload}
    client_dir = os.path.join("archives", client_id)

    for path in to_delete:
        try:
            full_path = os.path.join(client_dir, path)
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[TCP SERVER] Deleted file '{path}' no longer present on client")
        except Exception as e:
            print(f"[TCP SERVER] Failed to delete '{path}': {e}")

    if not expected_files:
        conn.send((json.dumps(make_next_sync_message(str(sync_interval_seconds))) + "\n").encode())
        print(f"[TCP SERVER] No files to upload. Sent NEXT_SYNC to {addr}")
    else:
        archive_tasks = {
            "type": MESSAGE_TYPES["ARCHIVE_TASKS"],
            "upload": [{"path": path} for path in expected_files]
        }
        conn.send((json.dumps(archive_tasks) + "\n").encode())
        print(f"[TCP SERVER] Sent ARCHIVE_TASKS to {addr}")

    return client_id, expected_files


def handle_file_transfer(conn, msg, client_id, expected_files, sync_interval_seconds, addr):
    # Handles FILE_TRANSFER message: receives and saves a file
    path = msg.get("path")
    size = msg.get("size")
    mod_time = msg.get("mod_time")

    if not path or size is None or mod_time is None:
        print(f"[TCP SERVER] Incomplete FILE_TRANSFER metadata from {addr}")
        return

    print(f"[TCP SERVER] Receiving file '{path}' ({size} bytes) from {addr}")
    received_data = b""

    while len(received_data) < size:
        chunk = conn.recv(min(4096, size - len(received_data)))
        if not chunk:
            raise Exception("Connection lost during file transfer.")
        received_data += chunk

    save_file_stream(client_id, path, received_data, mod_time)
    print(f"[TCP SERVER] Saved file '{path}'")
    expected_files.pop(path, None)

    if not expected_files:
        conn.send((json.dumps(make_next_sync_message(str(sync_interval_seconds))) + "\n").encode())
        print(f"[TCP SERVER] Sent NEXT_SYNC to {addr}")


def cleanup_connection(conn, addr):
    # Closes the connection and resets active client
    try:
        conn.close()
    except Exception:
        pass
    with active_client_lock:
        global active_client
        active_client = None
    print(f"[TCP SERVER] Session with {addr} ended.")


def start_next_client(sync_interval_seconds):
    # Starts the next client in the queue, if any
    global active_client

    with active_client_lock:
        if not client_queue.empty():
            conn, addr = client_queue.get()
            try:
                conn.send((json.dumps({"type": MESSAGE_TYPES["READY"]}) + "\n").encode())
                print(f"[TCP SERVER] Sent READY to {addr}")
                active_client = conn
                threading.Thread(target=handle_client, args=(conn, addr, sync_interval_seconds), daemon=True).start()
            except Exception as e:
                print(f"[TCP SERVER] Failed to resume client {addr}: {e}")
                try:
                    conn.close()
                except Exception:
                    pass
                active_client = None
                start_next_client(sync_interval_seconds)


def start_tcp_server(host='0.0.0.0', port=6001, sync_interval_seconds=60):
    # Starts the TCP server, listens for clients, and manages the active session queue
    global active_client

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"[TCP SERVER] Listening for TCP connections on port {port}")
    except Exception as e:
        print(f"[TCP SERVER] Failed to bind TCP socket: {e}")
        return

    def listener():
        # Accepts new connections and routes them based on server availability
        global active_client

        while True:
            try:
                conn, addr = server_socket.accept()
                print("===== NEW CLIENT TRYING TO CONNECT... =====")
                print(f"[TCP SERVER] Incoming connection from {addr}")

                with active_client_lock:
                    if active_client is None:
                        conn.send((json.dumps({"type": MESSAGE_TYPES["READY"]}) + "\n").encode())
                        active_client = conn
                        threading.Thread(target=handle_client, args=(conn, addr, sync_interval_seconds), daemon=True).start()
                    else:
                        print(f"[TCP SERVER] Server is busy. Queuing {addr}")
                        try:
                            conn.send((json.dumps({"type": MESSAGE_TYPES["BUSY"]}) + "\n").encode())
                            client_queue.put((conn, addr))
                        except Exception as e:
                            print(f"[TCP SERVER] Failed to queue {addr}: {e}")
                            try:
                                conn.close()
                            except Exception:
                                pass
            except Exception as e:
                print(f"[TCP SERVER] Listener error: {e}")

    # Start listener in a background thread
    threading.Thread(target=listener, daemon=True).start()
