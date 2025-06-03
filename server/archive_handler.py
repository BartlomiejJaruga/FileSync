import os


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
