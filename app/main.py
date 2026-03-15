from fastapi import FastAPI
from app.routes import rooms, chat

app = FastAPI()

app.include_router(rooms.router)
app.include_router(chat.router)
