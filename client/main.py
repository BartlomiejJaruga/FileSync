import os
import sys
from client.discovery import start_discovery_thread, stop_event
from client.tcp_client import start_tcp_client


def get_client_config():
    # Prompt the user to enter a client ID
    client_id = input("Enter CLIENT_ID: ").strip()

    # Ensure client ID is not empty
    while not client_id:
        print("CLIENT_ID cannot be empty.")
        client_id = input("Enter CLIENT_ID: ").strip()

    # Prompt the user to enter the archive directory path
    archive_path = input("Enter path to archive directory: ").strip()

    # Ensure the path exists and is a directory
    while not os.path.isdir(archive_path):
        print(f"The path '{archive_path}' does not exist or is not a directory.")
        archive_path = input("Enter a valid path to archive directory: ").strip()

    return client_id, archive_path


if __name__ == "__main__":
    try:
        # Get user configuration (client ID and archive path)
        CLIENT_ID, ARCHIVE_PATH = get_client_config()

        # Start background discovery thread
        start_discovery_thread()

        # Start TCP file sync client
        start_tcp_client(ARCHIVE_PATH, CLIENT_ID)

    except KeyboardInterrupt:
        # Handle Ctrl+C interrupt for graceful shutdown
        print("\n[CLIENT] Shutdown requested by user.")

        # Signal the discovery thread to stop
        stop_event.set()

        # Exit the program
        sys.exit(0)

    except Exception as e:
        # Catch all unexpected errors
        print(f"[CLIENT] Unexpected error: {e}")

        # Make sure discovery thread is also terminated
        stop_event.set()

        # Exit with failure code
        sys.exit(1)
