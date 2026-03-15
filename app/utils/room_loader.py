import json
from pathlib import Path

ROOMS_DIR = Path(__file__).resolve().parent.parent / "rooms"

def load_room(room_id: str):
    room_file = ROOMS_DIR / f"{room_id}.json"
    if not room_file.exists():
        raise FileNotFoundError(f"Room '{room_id}' not found.")
    with open(room_file, "r") as f:
        return json.load(f)
