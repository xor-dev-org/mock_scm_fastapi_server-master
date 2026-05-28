import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def read_json(file_name):
    path = BASE_DIR / "data" / file_name
    with open(path, "r") as f:
        return json.load(f)

def write_json(file_name, data):
    path = BASE_DIR / "data" / file_name
    with open(path, "w") as f:
        json.dump(data, f, indent=2)