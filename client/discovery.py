import socket
import time
import json
import threading
from common.protocol import make_discover_message, MESSAGE_TYPES
from common.utils import MULTICAST_GROUP, MULTICAST_PORT

WAIT_FOR_OFFER_TIMEOUT = 5
RETRY_INTERVAL = 10

pause_event = threading.Event()
stop_event = threading.Event()
discovered_server = {}


def discovery_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(WAIT_FOR_OFFER_TIMEOUT)
    discover_msg = json.dumps(make_discover_message()).encode()

    while not stop_event.is_set():
        if pause_event.is_set():
            time.sleep(1)
            continue

        try:
            print("[DISCOVERY] Sending DISCOVER message...")
            sock.sendto(discover_msg, (MULTICAST_GROUP, MULTICAST_PORT))
            data, server = sock.recvfrom(1024)
            msg = json.loads(data.decode())

            if msg.get("type") == MESSAGE_TYPES["OFFER"]:
                discovered_server["host"] = server[0]
                discovered_server["port"] = msg["port"]
                print(f"[DISCOVERY] Received OFFER from {server[0]}:{msg['port']}")
                pause_event.set()

        except socket.timeout:
            print(f"[DISCOVERY] No OFFER received. Retrying in {RETRY_INTERVAL} seconds...")
            time.sleep(RETRY_INTERVAL)
        except Exception as e:
            print(f"[DISCOVERY] Error: {e}")
            time.sleep(RETRY_INTERVAL)


def start_discovery_thread():
    thread = threading.Thread(target=discovery_loop, daemon=True)
    thread.start()


def find_server():
    while "host" not in discovered_server or "port" not in discovered_server:
        time.sleep(0.5)
    return discovered_server["host"], discovered_server["port"]
