import socket
import time
import json
import threading
from common.protocol import make_discover_message, MESSAGE_TYPES
from common.utils import MULTICAST_GROUP, MULTICAST_PORT

# Timeout for receiving OFFER response
WAIT_FOR_OFFER_TIMEOUT = 5

# Time between retries when no OFFER is received
RETRY_INTERVAL = 10

# Thread control events
pause_event = threading.Event()
stop_event = threading.Event()

# Dictionary to hold the discovered server's host and port
discovered_server = {}


def discovery_loop():
    # Main discovery loop that sends DISCOVER messages over multicast and waits for OFFER
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(WAIT_FOR_OFFER_TIMEOUT)

        discover_msg = json.dumps(make_discover_message()).encode()

        while not stop_event.is_set():
            if pause_event.is_set():
                # Paused due to successful discovery; sleep briefly
                time.sleep(1)
                continue

            try:
                print("[DISCOVERY] Sending DISCOVER message...")
                sock.sendto(discover_msg, (MULTICAST_GROUP, MULTICAST_PORT))

                data, server = sock.recvfrom(1024)
                msg = json.loads(data.decode())

                if msg.get("type") == MESSAGE_TYPES["OFFER"]:
                    # Server responded with an OFFER message
                    discovered_server["host"] = server[0]
                    discovered_server["port"] = msg["port"]
                    print(f"[DISCOVERY] Received OFFER from {server[0]}:{msg['port']}")
                    pause_event.set()

            except socket.timeout:
                # No OFFER response received within timeout
                print(f"[DISCOVERY] No OFFER received. Retrying in {RETRY_INTERVAL} seconds...")
                time.sleep(RETRY_INTERVAL)

            except (socket.error, json.JSONDecodeError) as e:
                # Handle socket or JSON decoding errors
                print(f"[DISCOVERY] Communication error: {e}")
                time.sleep(RETRY_INTERVAL)

            except Exception as e:
                # Catch-all for unexpected errors
                print(f"[DISCOVERY] Unexpected error: {e}")
                time.sleep(RETRY_INTERVAL)

    except Exception as e:
        # Handle initialization failure (e.g., socket creation)
        print(f"[DISCOVERY] Failed to initialize discovery socket: {e}")


def start_discovery_thread():
    # Starts the discovery loop in a background thread
    try:
        thread = threading.Thread(target=discovery_loop, daemon=True)
        thread.start()
    except Exception as e:
        print(f"[DISCOVERY] Failed to start discovery thread: {e}")


def find_server():
    # Blocks until a server is discovered and returns its host and port
    while "host" not in discovered_server or "port" not in discovered_server:
        time.sleep(0.5)
    return discovered_server["host"], discovered_server["port"]
