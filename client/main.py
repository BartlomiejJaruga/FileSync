import os
from client.discovery import start_discovery_thread
from client.tcp_client import start_tcp_client


def get_client_config():
    client_id = input("Enter CLIENT_ID: ").strip()
    while not client_id:
        print("CLIENT_ID cannot be empty.")
        client_id = input("Enter CLIENT_ID: ").strip()

    archive_path = input("Enter path to archive directory: ").strip()
    while not os.path.isdir(archive_path):
        print(f"The path '{archive_path}' does not exist or is not a directory.")
        archive_path = input("Enter a valid path to archive directory: ").strip()

    return client_id, archive_path


if __name__ == "__main__":
    CLIENT_ID, ARCHIVE_PATH = get_client_config()
    start_discovery_thread()  # uruchamiamy wątek discovery
    start_tcp_client(ARCHIVE_PATH, CLIENT_ID)
