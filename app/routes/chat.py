from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import ChatMessageDB, PlayerState

router = APIRouter()

class ChatMessage(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)

@router.post("/send")
def send_message(msg: ChatMessage, db: Session = Depends(get_db)):
    saved_message = ChatMessageDB(
        room_id=msg.room_id,
        username=msg.username,
        message=msg.message,
    )
    db.add(saved_message)

    player = db.query(PlayerState).filter(PlayerState.username == msg.username).first()
    if player is None:
        player = PlayerState(
            username=msg.username,
            last_room_id=msg.room_id,
            message_count=1,
            last_active_at=datetime.utcnow(),
        )
        db.add(player)
    else:
        player.last_room_id = msg.room_id
        player.message_count += 1
        player.last_active_at = datetime.utcnow()

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
                "username": message.username,
                "message": message.message,
                "created_at": message.created_at,
            }
            for message in messages
        ]
    }
