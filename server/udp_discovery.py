import socket
import struct
import threading
import json
from common.protocol import make_offer_message, MESSAGE_TYPES
from common.utils import MULTICAST_GROUP, MULTICAST_PORT


def start_udp_discovery_server(tcp_port):
    # Start a UDP server in a background thread to listen for DISCOVER messages
    def server_thread():
        try:
            # Create a UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to all interfaces on the multicast port
            sock.bind(('', MULTICAST_PORT))

            # Join the multicast group
            mreq = struct.pack('4sL', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            print(f"[UDP SERVER] Listening for DISCOVER on {MULTICAST_GROUP}:{MULTICAST_PORT}")
        except Exception as e:
            print(f"[UDP SERVER] Failed to initialize UDP socket: {e}")
            return  # Stop thread if socket setup fails

        while True:
            try:
                # Wait for incoming data
                data, addr = sock.recvfrom(1024)

                # Parse the message and check its type
                try:
                    msg = json.loads(data.decode())
                    if msg.get("type") == MESSAGE_TYPES["DISCOVER"]:
                        print(f"[UDP SERVER] Received DISCOVER from {addr}")

                        offer_msg = make_offer_message(tcp_port)
                        sock.sendto(json.dumps(offer_msg).encode(), addr)
                        print(f"[UDP SERVER] Sent OFFER to {addr}")
                except json.JSONDecodeError:
                    print(f"[UDP SERVER] Received invalid JSON from {addr}")
                except Exception as e:
                    print(f"[UDP SERVER] Error handling DISCOVER message: {e}")

            except Exception as e:
                print(f"[UDP SERVER] Error receiving packet: {e}")

    # Start the discovery server in a daemon thread
    thread = threading.Thread(target=server_thread, daemon=True)
    thread.start()
