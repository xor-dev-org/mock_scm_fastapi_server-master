import json
import os
import tempfile
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
_WRITE_LOCK = threading.Lock()

def read_json(file_name):
    path = BASE_DIR / "data" / file_name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(file_name, data):
    write_json_atomic(file_name, data)


def write_json_atomic(file_name, data):
    path = BASE_DIR / "data" / file_name
    path.parent.mkdir(parents=True, exist_ok=True)

    with _WRITE_LOCK:
        fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(data, temp_file, indent=2)
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise