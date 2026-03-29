"""Page route for room rendering and visit tracking."""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import RoomState
from app.utils.room_loader import load_room

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/room/{room_id}")
async def room_page(request: Request, room_id: str, db: Session = Depends(get_db)):
    """Render the room page and increment visit counters."""
    room_data = load_room(room_id)

    room_state = db.query(RoomState).filter(RoomState.room_id == room_id).first()
    if room_state is None:
        room_state = RoomState(room_id=room_id, visit_count=1)
        db.add(room_state)
    else:
        room_state.visit_count += 1

    db.commit()

    return templates.TemplateResponse(
        "room.html",
        {
            "request": request,
            "room": room_data,
        },
    )
