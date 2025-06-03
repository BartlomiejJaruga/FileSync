import os
import time
import json
from datetime import datetime
from common.protocol import MESSAGE_TYPES


def get_local_file_index(base_path):
    files = []
    for root, _, filenames in os.walk(base_path):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, base_path).replace("\\", "/")
            mod_time = os.path.getmtime(full_path)
            files.append({
                "filename": filename,
                "path": rel_path,
                "mod_time": mod_time
            })
    return files


def send_file(sock, archive_path, file_info):
    rel_path = file_info["path"]
    full_path = os.path.join(archive_path, rel_path)
    size = os.path.getsize(full_path)
    mod_time = os.path.getmtime(full_path)
    iso_time = datetime.utcfromtimestamp(mod_time).isoformat()

    header = {
        "type": MESSAGE_TYPES["FILE_TRANSFER"],
        "path": rel_path,
        "modified": iso_time,
        "size": size
    }

    # Wyślij nagłówek JSON zakończony \n
    sock.send((json.dumps(header) + "\n").encode())

    # Krótkie opóźnienie, żeby nagłówek i dane nie zlały się
    time.sleep(0.05)

    # Wyślij dane pliku
    with open(full_path, "rb") as f:
        while chunk := f.read(4096):
            sock.sendall(chunk)
