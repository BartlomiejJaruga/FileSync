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
    # Receive a JSON message ending with newline '\n'
    buffer = b""
    try:
        while True:
            chunk = conn.recv(1)
            if not chunk:
                break  # Connection closed
            if chunk == b"\n":
                break  # End of message
            buffer += chunk
        return json.loads(buffer.decode())
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"[TCP SERVER] Error receiving JSON message: {e}")
        return None


def handle_client(conn, addr, sync_interval_seconds):
    # Handles a single client session: receives file list, determines sync actions, receives files
    global active_client

    print(f"[TCP SERVER] Connected with client {addr}")

    client_id = None
    expected_files = {}

    try:
        while True:
            # Receive a JSON command from client
            msg = recv_json_message(conn)
            if not msg:
                print(f"[TCP SERVER] Client {addr} disconnected or sent invalid message.")
                break

            msg_type = msg.get("type")

            # Handle FILE_INFO message from client
            if msg_type == MESSAGE_TYPES.get("FILE_INFO"):
                client_id = msg["client_id"]
                ensure_client_archive_dir(client_id)

                client_files = msg["files"]
                server_index = get_server_file_index(client_id)
                client_index = {f["path"]: f["mod_time"] for f in client_files}

                # Compare client files with server's version
                to_upload, to_delete = compare_file_indexes(server_index, client_index)
                expected_files = {f["path"]: f for f in client_files if f["path"] in to_upload}

                client_dir = os.path.join("archives", client_id)

                # Remove files on server that were deleted on client
                for path in to_delete:
                    try:
                        full_path = os.path.join(client_dir, path)
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            print(f"[TCP SERVER] Deleted file '{path}' no longer present on client")
                    except Exception as e:
                        print(f"[TCP SERVER] Failed to delete '{path}': {e}")

                # If no files to upload, send NEXT_SYNC and end
                if not expected_files:
                    conn.send((json.dumps(make_next_sync_message(str(sync_interval_seconds))) + "\n").encode())
                    print(f"[TCP SERVER] No files to upload. Sent NEXT_SYNC to {addr}")
                    break
                else:
                    # Send ARCHIVE_TASKS message with upload instructions
                    archive_tasks = {
                        "type": MESSAGE_TYPES["ARCHIVE_TASKS"],
                        "upload": [{"path": path} for path in expected_files]
                    }
                    conn.send((json.dumps(archive_tasks) + "\n").encode())
                    print(f"[TCP SERVER] Sent ARCHIVE_TASKS to {addr}")

            # Handle FILE_TRANSFER message with actual file data
            elif msg_type == MESSAGE_TYPES.get("FILE_TRANSFER"):
                path = msg.get("path")
                size = msg.get("size")
                mod_time = msg.get("mod_time")

                if not path or size is None or mod_time is None:
                    print(f"[TCP SERVER] Incomplete FILE_TRANSFER metadata from {addr}")
                    continue

                print(f"[TCP SERVER] Receiving file '{path}' ({size} bytes) from {addr}")
                received_data = b""

                # Receive binary file data in chunks
                while len(received_data) < size:
                    chunk = conn.recv(min(4096, size - len(received_data)))
                    if not chunk:
                        raise Exception("Connection lost during file transfer.")
                    received_data += chunk

                # Save the received file to the appropriate archive directory
                save_file_stream(client_id, path, received_data, mod_time)
                print(f"[TCP SERVER] Saved file '{path}'")

                expected_files.pop(path, None)

                # If all files received, send NEXT_SYNC and end
                if not expected_files:
                    conn.send((json.dumps(make_next_sync_message(str(sync_interval_seconds))) + "\n").encode())
                    print(f"[TCP SERVER] Sent NEXT_SYNC to {addr}")
                    break

            # Unknown or unsupported message type
            else:
                print(f"[TCP SERVER] Unknown message type from {addr}: {msg_type}")

    except Exception as e:
        # Catch-all for unexpected errors during client session
        print(f"[TCP SERVER] Error with {addr}: {e}")

    finally:
        # Ensure cleanup happens even on error or disconnection
        try:
            conn.close()
        except Exception:
            pass

        with active_client_lock:
            active_client = None

        print(f"[TCP SERVER] Session with {addr} ended.")
        start_next_client(sync_interval_seconds)


def start_next_client(sync_interval_seconds):
    # Picks the next client from the queue and starts a thread to handle them
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
    # Starts the TCP server, which accepts one client at a time and queues others
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
        # Background thread to accept and manage incoming client connections
        global active_client

        while True:
            try:
                conn, addr = server_socket.accept()
                print(f"[TCP SERVER] Incoming connection from {addr}")

                with active_client_lock:
                    if active_client is None:
                        # If no client is active, start handling immediately
                        conn.send((json.dumps({"type": MESSAGE_TYPES["READY"]}) + "\n").encode())
                        active_client = conn
                        threading.Thread(target=handle_client, args=(conn, addr, sync_interval_seconds), daemon=True).start()
                    else:
                        # Server is busy, notify client and add to queue
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

    # Start the listener thread as daemon
    threading.Thread(target=listener, daemon=True).start()
