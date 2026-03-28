from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import Character, ChatMessageDB
from app.routes.auth import get_current_character

router = APIRouter()

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
