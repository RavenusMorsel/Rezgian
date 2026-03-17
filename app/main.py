from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from fastapi.staticfiles import StaticFiles
from app.routes import rooms, chat

app = FastAPI()

app.mount("/app/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(rooms.router)
app.include_router(chat.router)
