import socket
import threading
import queue
import json
from common.protocol import MESSAGE_TYPES

active_client_lock = threading.Lock()
active_client = None
client_queue = queue.Queue()


def handle_client(conn, addr):
    global active_client

    print(f"[TCP SERVER] Connected with client {addr}")

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                print(f"[TCP SERVER] Client {addr} disconnected.")
                break

            try:
                msg = json.loads(data.decode())
                print(f"[TCP SERVER] Received from {addr}:")
                print(json.dumps(msg, indent=2))
            except json.JSONDecodeError:
                print(f"[TCP SERVER] Invalid JSON from {addr}")
    except Exception as e:
        print(f"[TCP SERVER] Error with {addr}: {e}")
    finally:
        conn.close()
        with active_client_lock:
            active_client = None
        print(f"[TCP SERVER] Session with {addr} ended.")
        start_next_client()


def start_next_client():
    global active_client

    with active_client_lock:
        if not client_queue.empty():
            conn, addr = client_queue.get()
            try:
                conn.send(json.dumps({"type": MESSAGE_TYPES["READY"]}).encode())
                print(f"[TCP SERVER] Sent READY to {addr}")
                active_client = conn
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[TCP SERVER] Failed to resume client {addr}: {e}")
                conn.close()
                active_client = None
                start_next_client()


def start_tcp_server(host='0.0.0.0', port=6001):
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
                        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
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
