import os

# Root directory where all client archives are stored
ARCHIVES_ROOT = "archives"


def ensure_archives_dir_exists():
    # Ensure the root directory for archives exists; create it if necessary
    try:
        if not os.path.exists(ARCHIVES_ROOT):
            os.makedirs(ARCHIVES_ROOT)
            print(f"[ARCHIVE HANDLER] Created root archive directory: {ARCHIVES_ROOT}")
    except Exception as e:
        print(f"[ARCHIVE HANDLER] Failed to create root archive directory: {e}")


def ensure_client_archive_dir(client_id):
    # Ensure the archive directory for a specific client exists
    ensure_archives_dir_exists()

    client_dir = os.path.join(ARCHIVES_ROOT, client_id)
    try:
        if not os.path.exists(client_dir):
            os.makedirs(client_dir)
            print(f"[ARCHIVE HANDLER] Created archive directory for client: {client_id}")
    except Exception as e:
        print(f"[ARCHIVE HANDLER] Failed to create client archive directory '{client_id}': {e}")

    return client_dir


def get_server_file_index(client_id):
    # Generate an index of all files stored on the server for a given client
    index = []
    try:
        client_dir = ensure_client_archive_dir(client_id)

        for root, _, files in os.walk(client_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, client_dir).replace("\\", "/")
                try:
                    mod_time = os.path.getmtime(full_path)
                    index.append({"path": rel_path, "mod_time": mod_time})
                except Exception as e:
                    print(f"[ARCHIVE HANDLER] Failed to read modification time for '{rel_path}': {e}")
    except Exception as e:
        print(f"[ARCHIVE HANDLER] Failed to build server file index for '{client_id}': {e}")

    return index


def compare_file_indexes(server_index, client_index):
    # Compare server and client file indexes to determine which files to upload and delete
    to_upload = []
    to_delete = []

    try:
        server_dict = {f["path"]: f["mod_time"] for f in server_index}
        client_paths = set(client_index.keys())

        for path, client_mod in client_index.items():
            server_mod = server_dict.get(path)
            if server_mod is None or client_mod > server_mod + 1:
                to_upload.append(path)

        to_delete = [path for path in server_dict if path not in client_paths]
    except Exception as e:
        print(f"[ARCHIVE HANDLER] Failed to compare file indexes: {e}")

    return to_upload, to_delete


def save_file_stream(client_id, path, data, mod_time=None):
    # Save incoming file data to disk under the client's archive path
    try:
        client_dir = ensure_client_archive_dir(client_id)
        full_path = os.path.join(client_dir, path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(data)

        # Optionally restore the file's modification time
        if mod_time is not None:
            try:
                os.utime(full_path, (mod_time, mod_time))
                # print(f"[ARCHIVE HANDLER] Restored mtime for '{path}': {time.ctime(mod_time)}")
            except Exception as e:
                print(f"[ARCHIVE HANDLER] Failed to set mtime for '{path}': {e}")
    except Exception as e:
        print(f"[ARCHIVE HANDLER] Failed to save file stream for '{path}': {e}")
