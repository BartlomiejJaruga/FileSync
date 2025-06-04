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

active_client_lock = threading.Lock()
active_client = None
client_queue = queue.Queue()


def recv_json_message(conn):
    buffer = b""
    while True:
        chunk = conn.recv(1)
        if not chunk:
            break
        if chunk == b"\n":
            break
        buffer += chunk
    try:
        return json.loads(buffer.decode())
    except json.JSONDecodeError:
        return None


def handle_client(conn, addr, sync_interval_seconds):
    global active_client

    print(f"[TCP SERVER] Connected with client {addr}")
    client_id = None
    expected_files = {}

    try:
        while True:
            msg = recv_json_message(conn)
            if not msg:
                print(f"[TCP SERVER] Client {addr} disconnected.")
                break

            msg_type = msg.get("type")

            if msg_type == MESSAGE_TYPES.get("FILE_INFO"):
                client_id = msg["client_id"]
                ensure_client_archive_dir(client_id)

                client_files = msg["files"]
                server_index = get_server_file_index(client_id)
                client_index = {f["path"]: f["mod_time"] for f in client_files}

                to_upload, to_delete = compare_file_indexes(server_index, client_index)
                expected_files = {f["path"]: f for f in client_files if f["path"] in to_upload}

                # Delete files not present on client anymore
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
                    conn.send(json.dumps(make_next_sync_message(str(sync_interval_seconds))).encode())
                    print(f"[TCP SERVER] No files to upload. Sent NEXT_SYNC to {addr}")
                    break
                else:
                    archive_tasks = {
                        "type": MESSAGE_TYPES["ARCHIVE_TASKS"],
                        "upload": [{"path": path} for path in expected_files]
                    }
                    conn.send(json.dumps(archive_tasks).encode())
                    print(f"[TCP SERVER] Sent ARCHIVE_TASKS to {addr}")

            elif msg_type == MESSAGE_TYPES.get("FILE_TRANSFER"):
                path = msg["path"]
                size = msg["size"]
                mod_time = msg["mod_time"]

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
                    conn.send(json.dumps(make_next_sync_message(str(sync_interval_seconds))).encode())
                    print(f"[TCP SERVER] Sent NEXT_SYNC to {addr}")
                    break

            else:
                print(f"[TCP SERVER] Unknown message type: {msg_type}")

    except Exception as e:
        print(f"[TCP SERVER] Error with {addr}: {e}")

    finally:
        conn.close()
        with active_client_lock:
            active_client = None
        print(f"[TCP SERVER] Session with {addr} ended.")
        start_next_client(sync_interval_seconds)


def start_next_client(sync_interval_seconds):
    global active_client

    with active_client_lock:
        if not client_queue.empty():
            conn, addr = client_queue.get()
            try:
                conn.send(json.dumps({"type": MESSAGE_TYPES["READY"]}).encode())
                print(f"[TCP SERVER] Sent READY to {addr}")
                active_client = conn
                threading.Thread(target=handle_client, args=(conn, addr, sync_interval_seconds), daemon=True).start()
            except Exception as e:
                print(f"[TCP SERVER] Failed to resume client {addr}: {e}")
                conn.close()
                active_client = None
                start_next_client(sync_interval_seconds)


def start_tcp_server(host='0.0.0.0', port=6001, sync_interval_seconds=60):
    global active_client

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[TCP SERVER] Listening for TCP connections on port {port}")

    def listener():
        global active_client

        while True:
            try:
                conn, addr = server_socket.accept()
                print(f"[TCP SERVER] Incoming connection from {addr}")

                with active_client_lock:
                    if active_client is None:
                        conn.send(json.dumps({"type": MESSAGE_TYPES["READY"]}).encode())
                        active_client = conn
                        threading.Thread(target=handle_client, args=(conn, addr, sync_interval_seconds), daemon=True).start()
                    else:
                        print(f"[TCP SERVER] Server is busy. Queuing {addr}")
                        try:
                            conn.send(json.dumps({"type": MESSAGE_TYPES["BUSY"]}).encode())
                            client_queue.put((conn, addr))
                        except Exception as e:
                            print(f"[TCP SERVER] Failed to queue {addr}: {e}")
                            conn.close()
            except Exception as e:
                print(f"[TCP SERVER] Listener error: {e}")

    threading.Thread(target=listener, daemon=True).start()
