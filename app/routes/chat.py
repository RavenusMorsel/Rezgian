"""Realtime room chat routes with lightweight reward and ambient NPC behavior."""

import asyncio
import hashlib
import random
import time

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import SessionLocal, get_db
from app.database.models import Character, ChatMessageDB
from app.routes.auth import get_current_character

router = APIRouter()

# Weighted chat coin rewards per message (heavily biased toward 0).
CHAT_COIN_OUTCOMES = (0, 1, 2, 3, 4, 5)
CHAT_COIN_WEIGHTS = (50, 25, 12, 8, 3, 2)
CELLAR_RAT_USERNAME = "Cellar Rat"
CELLAR_RAT_CHANCE = 0.28
CELLAR_RAT_MAX_SILENT_MESSAGES = 4
CELLAR_RAT_DELAY_SECONDS = 3.0
CELLAR_RAT_MIN_INTERVAL_SECONDS = 120.0
CELLAR_RAT_LINES = (
    "Skritch... skritch...",
    "A rat darts between two barrels.",
    "Tiny claws scrape across old stone.",
    "Two bright eyes blink from the dark.",
    "A low squeak echoes near the stairs.",
)
CELLAR_RAT_SILENT_STREAK_BY_ROOM: dict[str, int] = {}
CELLAR_RAT_LAST_TRIGGER_BY_ROOM: dict[str, float] = {}


def _roll_chat_coin_reward() -> int:
    """Return weighted chat coin reward (biased toward low values)."""
    return random.choices(CHAT_COIN_OUTCOMES, weights=CHAT_COIN_WEIGHTS, k=1)[0]


def _roll_cellar_rat_line(room_id: str) -> str | None:
    """Pick an ambient cellar rat line with streak and cooldown safeguards."""
    if room_id != "cellar":
        return None

    now = time.monotonic()
    last_trigger = CELLAR_RAT_LAST_TRIGGER_BY_ROOM.get(room_id)
    if last_trigger is not None and (now - last_trigger) < CELLAR_RAT_MIN_INTERVAL_SECONDS:
        return None

    streak = CELLAR_RAT_SILENT_STREAK_BY_ROOM.get(room_id, 0)
    forced = streak >= CELLAR_RAT_MAX_SILENT_MESSAGES

    if not forced and random.random() > CELLAR_RAT_CHANCE:
        CELLAR_RAT_SILENT_STREAK_BY_ROOM[room_id] = streak + 1
        return None

    CELLAR_RAT_SILENT_STREAK_BY_ROOM[room_id] = 0
    CELLAR_RAT_LAST_TRIGGER_BY_ROOM[room_id] = now
    return random.choice(CELLAR_RAT_LINES)


async def _emit_delayed_rat_line(room_id: str, rat_line: str):
    """Emit rat ambience after a short delay to feel less mechanical."""
    await asyncio.sleep(CELLAR_RAT_DELAY_SECONDS)

    db = SessionLocal()
    try:
        db.add(
            ChatMessageDB(
                room_id=room_id,
                username=CELLAR_RAT_USERNAME,
                message=rat_line,
            )
        )
        db.commit()
    finally:
        db.close()

    await manager.broadcast(room_id, {
        "username": CELLAR_RAT_USERNAME,
        "message": rat_line,
    })


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Track websocket connections per room for targeted broadcasts."""

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
            rat_line: str | None = None

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
                    char.currency += _roll_chat_coin_reward()

                rat_line = _roll_cellar_rat_line(room_id)
                db.commit()
            finally:
                db.close()

            await manager.broadcast(room_id, {
                "username": character_name,
                "message": msg_text,
            })

            if rat_line:
                # Fire-and-forget ambient line so player messages are never delayed.
                asyncio.create_task(_emit_delayed_rat_line(room_id, rat_line))
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
    coin_reward = _roll_chat_coin_reward()
    character.currency += coin_reward

    rat_line = _roll_cellar_rat_line(msg.room_id)
    if rat_line:
        db.add(
            ChatMessageDB(
                room_id=msg.room_id,
                username=CELLAR_RAT_USERNAME,
                message=rat_line,
            )
        )

    db.commit()
    return {"status": "ok", "coin_reward": coin_reward, "rat_line": rat_line}


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
