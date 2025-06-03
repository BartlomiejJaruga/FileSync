import time
from server.udp_discovery import start_udp_discovery_server
from server.tcp_server import start_tcp_server


def get_server_config():
    while True:
        port_input = input("Enter TCP server port (1025-65535): ").strip()
        if port_input.isdigit():
            port = int(port_input)
            if 1025 <= port <= 65535:
                break
        print("Invalid port. Please enter a number between 1025 and 65535.")

    while True:
        sync_input = input("Enter sync interval in seconds (positive integer): ").strip()
        if sync_input.isdigit() and int(sync_input) > 0:
            break
        print("Invalid interval. Please enter a positive integer.")

    return port, int(sync_input)


if __name__ == "__main__":
    TCP_PORT, SYNC_INTERVAL_SECONDS = get_server_config()

    start_udp_discovery_server(TCP_PORT)
    start_tcp_server(port=TCP_PORT, sync_interval_seconds=SYNC_INTERVAL_SECONDS)

    print("[SERVER] USP Server is running...")
    print(f"[SERVER] TCP Port: {TCP_PORT}")
    print(f"[SERVER] Sync Interval: {SYNC_INTERVAL_SECONDS} seconds")

    while True:
        time.sleep(1)
