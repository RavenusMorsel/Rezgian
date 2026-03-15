from fastapi import APIRouter, Request, Form
from typing import List, Dict
import time

router = APIRouter()

# Temporary in-memory message store
MESSAGES: List[Dict] = []

@router.post("/api/chat/send")
async def send_message(username: str = Form(...), message: str = Form(...)):
    entry = {
        "username": username,
        "message": message,
        "timestamp": int(time.time())
    }
    MESSAGES.append(entry)
    return {"status": "ok"}

@router.get("/api/chat/fetch")
async def fetch_messages():
    return {"messages": MESSAGES[-50:]}  # last 50 messages
