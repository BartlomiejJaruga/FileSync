import os
import json
import time

ARCHIVES_ROOT = "archives"


def ensure_archives_dir_exists():
    if not os.path.exists(ARCHIVES_ROOT):
        os.makedirs(ARCHIVES_ROOT)
        print(f"[ARCHIVE HANDLER] Created root archive directory: {ARCHIVES_ROOT}")
    else:
        print(f"[ARCHIVE HANDLER] Root archive directory already exists.")


def ensure_client_archive_dir(client_id):
    ensure_archives_dir_exists()

    client_dir = os.path.join(ARCHIVES_ROOT, client_id)
    if not os.path.exists(client_dir):
        os.makedirs(client_dir)
        print(f"[ARCHIVE HANDLER] Created archive directory for client: {client_id}")
    else:
        print(f"[ARCHIVE HANDLER] Archive directory already exists for client: {client_id}")

    return client_dir


def get_server_file_index(client_id):
    client_dir = ensure_client_archive_dir(client_id)
    index = []
    for root, _, files in os.walk(client_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, client_dir).replace("\\", "/")
            mod_time = os.path.getmtime(full_path)
            index.append({"path": rel_path, "mod_time": mod_time})
    return index


def compare_file_indexes(server_index, client_index):
    server_dict = {f["path"]: f["mod_time"] for f in server_index}
    client_paths = set(client_index.keys())

    to_upload = []
    for path, client_mod in client_index.items():
        server_mod = server_dict.get(path)
        if server_mod is None or client_mod > server_mod + 1:
            to_upload.append(path)

    to_delete = [path for path in server_dict if path not in client_paths]

    return to_upload, to_delete


def save_file_stream(client_id, path, data):
    client_dir = ensure_client_archive_dir(client_id)
    full_path = os.path.join(client_dir, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)