from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from app.utils.room_loader import load_room

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/room/{room_id}")
async def room_page(request: Request, room_id: str):
    room_data = load_room(room_id)
    return templates.TemplateResponse(
        "room.html",
        {
            "request": request,
            "room": room_data
        }
    )
