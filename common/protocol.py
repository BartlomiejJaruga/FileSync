# JSON Message types
MESSAGE_TYPES = {
    "DISCOVER": "DISCOVER",
    "OFFER": "OFFER",
    "READY": "READY",
    "BUSY": "BUSY",
    "ARCHIVE_LIST": "ARCHIVE_LIST",
    "ARCHIVE_TASKS": "ARCHIVE_TASKS",
    "FILE_TRANSFER": "FILE_TRANSFER",
    "NEXT_SYNC": "NEXT_SYNC"
}

# simple message functions


def make_discover_message():
    return {
        "type": MESSAGE_TYPES["DISCOVER"]
    }


def make_offer_message(port: int):
    return {
        "type": MESSAGE_TYPES["OFFER"],
        "port": port
    }


def make_busy_message():
    return {
        "type": MESSAGE_TYPES["BUSY"]
    }


def make_ready_message():
    return {
        "type": MESSAGE_TYPES["READY"]
    }


def make_archive_list(client_id: str, files: list):
    return {
        "type": MESSAGE_TYPES["ARCHIVE_LIST"],
        "client_id": client_id,
        "files": files
    }


def make_archive_tasks(upload_list: list):
    return {
        "type": MESSAGE_TYPES["ARCHIVE_TASKS"],
        "upload": upload_list
    }


def make_file_transfer_header(path: str, modified: str, size: int):
    return {
        "type": MESSAGE_TYPES["FILE_TRANSFER"],
        "path": path,
        "modified": modified,
        "size": size
    }


def make_next_sync_message(datetime_str: str):
    return {
        "type": MESSAGE_TYPES["NEXT_SYNC"],
        "next_time": datetime_str
    }
