import os
import json
from datetime import datetime
from common.protocol import MESSAGE_TYPES


def get_local_file_index(base_path):
    # Collects metadata for all files in the given directory (recursively)
    files = []
    for root, _, filenames in os.walk(base_path):
        for filename in filenames:
            try:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, base_path).replace("\\", "/")
                mod_time = os.path.getmtime(full_path)  # May raise FileNotFoundError
                files.append({
                    "filename": filename,
                    "path": rel_path,
                    "mod_time": mod_time
                })
            except (OSError, FileNotFoundError) as e:
                # Skips files that cannot be accessed
                print(f"[ARCHIVE UTILS] Skipping file '{filename}' due to error: {e}")
    return files


def send_file(sock, archive_path, file_info):
    # Sends a file over the socket connection along with its metadata
    try:
        rel_path = file_info["path"]
        full_path = os.path.join(archive_path, rel_path)

        size = os.path.getsize(full_path)  # May raise OSError
        mod_time = os.path.getmtime(full_path)  # May raise OSError
        iso_time = datetime.utcfromtimestamp(mod_time).isoformat()

        header = {
            "type": MESSAGE_TYPES["FILE_TRANSFER"],
            "path": rel_path,
            "modified": iso_time,
            "mod_time": mod_time,
            "size": size
        }

        # Send JSON header
        sock.send((json.dumps(header) + "\n").encode())

        # Send file contents in chunks
        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                sock.sendall(chunk)  # May raise socket.error
        print(f"[ARCHIVE UTILS] Sent file '{rel_path}' ({size} bytes)")

    except (OSError, FileNotFoundError) as e:
        # Handle errors related to file access
        print(f"[ARCHIVE UTILS] Failed to read or send file '{file_info.get('path')}': {e}")
    except Exception as e:
        # Catch-all for socket or encoding-related issues
        print(f"[ARCHIVE UTILS] Unexpected error while sending file: {e}")
