from server.udp_discovery import start_udp_discovery_server
from server.tcp_server import start_tcp_server
import time

if __name__ == "__main__":
    TCP_PORT = 6001  # or user input
    SYNC_INTERVAL_MINUTES = 10  # or user input

    start_udp_discovery_server(TCP_PORT)
    start_tcp_server(port=TCP_PORT)

    print("[SERVER] USP Server is running...")

    while True:
        time.sleep(1)
