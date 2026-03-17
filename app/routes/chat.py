from fastapi import APIRouter, Request, Form
from typing import List, Dict
import time
from pydantic import BaseModel

router = APIRouter()

# Store messages per room
room_messages = {}

class ChatMessage(BaseModel):
    room_id: str
    username: str
    message: str

@router.post("/send")
def send_message(msg: ChatMessage):
    # Create room list if it doesn't exist
    if msg.room_id not in room_messages:
        room_messages[msg.room_id] = []

    room_messages[msg.room_id].append({
        "username": msg.username,
        "message": msg.message
    })

    return {"status": "ok"}

@router.get("/fetch/{room_id}")
def fetch_messages(room_id: str):
    # Return empty list if room has no messages yet
    return {"messages": room_messages.get(room_id, [])}
