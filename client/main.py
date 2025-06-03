from client.discovery import find_server
from client.tcp_client import start_tcp_client

if __name__ == "__main__":
    ARCHIVE_PATH = "client/archive"
    CLIENT_ID = "client_001"

    server_ip, server_port = find_server()

    print(f"[CLIENT] USP server found at {server_ip}:{server_port}")
    start_tcp_client(ARCHIVE_PATH, CLIENT_ID, server_ip, server_port)
