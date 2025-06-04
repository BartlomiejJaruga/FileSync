# JSON Message types
MESSAGE_TYPES = {
    "DISCOVER": "DISCOVER",
    "OFFER": "OFFER",
    "READY": "READY",
    "BUSY": "BUSY",
    "FILE_INFO": "FILE_INFO",
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


def make_next_sync_message(time_in_seconds_str: str):
    return {
        "type": MESSAGE_TYPES["NEXT_SYNC"],
        "time_in_seconds": time_in_seconds_str
    }
