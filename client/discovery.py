import socket
import struct
import time
import json
from common.protocol import make_discover_message, MESSAGE_TYPES

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007
WAIT_FOR_OFFER_TIMEOUT = 5
RETRY_INTERVAL = 10


def find_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(WAIT_FOR_OFFER_TIMEOUT)

    discover_msg = json.dumps(make_discover_message()).encode()

    while True:
        try:
            print("[CLIENT] Sending DISCOVER message...")
            sock.sendto(discover_msg, (MULTICAST_GROUP, MULTICAST_PORT))
            data, server = sock.recvfrom(1024)
            msg = json.loads(data.decode())

            if msg.get("type") == MESSAGE_TYPES["OFFER"]:
                print(f"[CLIENT] Received OFFER: {server[0]}:{msg['port']}")
                return server[0], msg['port']

        except socket.timeout:
            print(f"[CLIENT] No OFFER received. Retrying in {RETRY_INTERVAL} seconds...")
            time.sleep(RETRY_INTERVAL)
        except Exception as e:
            print(f"[CLIENT] Error: {e}")
            time.sleep(RETRY_INTERVAL)
