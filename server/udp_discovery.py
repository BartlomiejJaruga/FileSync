import socket
import struct
import threading
from common.protocol import make_offer_message, MESSAGE_TYPES
import json

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007


def start_udp_discovery_server(tcp_port):
    def server_thread():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', MULTICAST_PORT))

        mreq = struct.pack('4sL', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        print(f"[UDP SERVER] Listening for DISCOVER on {MULTICAST_GROUP}:{MULTICAST_PORT}")

        while True:
            data, addr = sock.recvfrom(1024)
            try:
                msg = json.loads(data.decode())
                if msg.get("type") == MESSAGE_TYPES["DISCOVER"]:
                    print(f"[UDP SERVER] Received DISCOVER from {addr}")
                    offer_msg = make_offer_message(tcp_port)
                    sock.sendto(json.dumps(offer_msg).encode(), addr)
                    print(f"[UDP SERVER] Sent OFFER to {addr}")
            except Exception as e:
                print(f"[UDP SERVER] Error handling packet: {e}")

    thread = threading.Thread(target=server_thread, daemon=True)
    thread.start()
