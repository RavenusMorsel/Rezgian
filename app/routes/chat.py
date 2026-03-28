import hashlib

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import SessionLocal, get_db
from app.database.models import Character, ChatMessageDB
from app.routes.auth import get_current_character

router = APIRouter()


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self.rooms:
            try:
                self.rooms[room_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, room_id: str, payload: dict):
        if room_id not in self.rooms:
            return
        dead = []
        for ws in list(self.rooms[room_id]):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)


manager = ConnectionManager()


@router.websocket("/ws/{room_id}")
async def websocket_chat(
    room_id: str,
    ws: WebSocket,
    token: str = Query(...),
):
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    db = SessionLocal()
    try:
        character = db.query(Character).filter(Character.token_hash == token_hash).first()
    finally:
        db.close()

    if not character:
        await ws.close(code=4001)
        return

    character_name = character.name
    await manager.connect(room_id, ws)

    try:
        while True:
            text = await ws.receive_text()
            msg_text = text[:1000]

            db = SessionLocal()
            try:
                saved = ChatMessageDB(
                    room_id=room_id,
                    username=character_name,
                    message=msg_text,
                )
                db.add(saved)
                char = db.query(Character).filter(Character.token_hash == token_hash).first()
                if char:
                    char.last_room_id = room_id
                    char.message_count += 1
                    char.currency += 1
                db.commit()
            finally:
                db.close()

            await manager.broadcast(room_id, {
                "username": character_name,
                "message": msg_text,
            })
    except WebSocketDisconnect:
        manager.disconnect(room_id, ws)


# ---------------------------------------------------------------------------
# HTTP routes (kept for compatibility / fallback history loading)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)


@router.post("/send")
def send_message(
    msg: ChatMessage,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    saved_message = ChatMessageDB(
        room_id=msg.room_id,
        username=character.name,
        message=msg.message,
    )
    db.add(saved_message)
    character.last_room_id = msg.room_id
    character.message_count += 1
    character.currency += 1
    db.commit()
    return {"status": "ok"}


@router.get("/fetch/{room_id}")
def fetch_messages(room_id: str, db: Session = Depends(get_db)):
    messages = (
        db.query(ChatMessageDB)
        .filter(ChatMessageDB.room_id == room_id)
        .order_by(ChatMessageDB.id.asc())
        .limit(250)
        .all()
    )
    return {
        "messages": [
            {
                "username": m.username,
                "message": m.message,
                "created_at": m.created_at,
            }
            for m in messages
        ]
    }
