"""Utility helpers for loading room JSON definitions."""

import json
from pathlib import Path

ROOMS_DIR = Path(__file__).resolve().parent.parent / "rooms"


def load_room(room_id: str) -> dict:
    """Load and parse a room definition by room id."""
    room_path = ROOMS_DIR / f"{room_id}.json"
    if not room_path.exists():
        raise FileNotFoundError(f"Room '{room_id}' not found.")

    with open(room_path, "r", encoding="utf-8") as file:
        return json.load(file)
