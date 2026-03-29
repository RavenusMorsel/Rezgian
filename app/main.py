"""Application entrypoint and route wiring for Rezgian."""

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import models as _models
from app.database.base import Base, engine
from app.routes import auth, chat, combat, economy, rooms

app = FastAPI()

# Serve static assets under /app/static for templates and game UI scripts.
app.mount("/app/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.on_event("startup")
def startup_event():
    # Keep development setup simple by ensuring tables exist at startup.
    Base.metadata.create_all(bind=engine)


app.include_router(auth.page_router)
app.include_router(auth.api_router, prefix="/api/auth")
app.include_router(rooms.router)
app.include_router(chat.router, prefix="/api/chat")
app.include_router(economy.router, prefix="/api/economy")
app.include_router(combat.router, prefix="/api/combat")
