from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.database.base import Base, engine
from app.database import models as _models
from app.routes import rooms, chat

app = FastAPI()

app.mount("/app/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


app.include_router(rooms.router)
app.include_router(chat.router, prefix="/api/chat")
