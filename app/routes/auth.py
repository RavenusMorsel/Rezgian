import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import Character

page_router = APIRouter()
api_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


TOKEN_STORAGE_KEY = "rezgian_character_token"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize_character(character: Character) -> dict:
    return {
        "id": character.id,
        "name": character.name,
        "currency": character.currency,
        "inventory_json": character.inventory_json,
        "last_room_id": character.last_room_id,
        "message_count": character.message_count,
    }


def get_current_character(
    db: Session = Depends(get_db), authorization: str | None = Header(default=None)
) -> Character:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    token_hash = _hash_token(token)
    character = db.query(Character).filter(Character.token_hash == token_hash).first()
    if character is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return character


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)


class CharacterContinueRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)


class CharacterImportRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)


@page_router.get("/")
def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@api_router.post("/create")
def create_character(payload: CharacterCreateRequest, db: Session = Depends(get_db)):
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Character name is required")

    existing = (
        db.query(Character)
        .filter(func.lower(Character.name) == clean_name.lower())
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Character name already exists")

    raw_token = secrets.token_urlsafe(32)
    character = Character(
        name=clean_name,
        token_hash=_hash_token(raw_token),
        currency=0,
        inventory_json="[]",
        last_room_id="tavern",
        message_count=0,
        last_active_at=datetime.utcnow(),
    )
    db.add(character)
    db.commit()
    db.refresh(character)

    return {
        "token": raw_token,
        "token_storage_key": TOKEN_STORAGE_KEY,
        "character": _serialize_character(character),
    }


@api_router.post("/continue")
def continue_character(payload: CharacterContinueRequest, db: Session = Depends(get_db)):
    token = payload.token.strip()
    character = db.query(Character).filter(Character.token_hash == _hash_token(token)).first()
    if character is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    character.last_active_at = datetime.utcnow()
    db.commit()

    return {
        "token": token,
        "token_storage_key": TOKEN_STORAGE_KEY,
        "character": _serialize_character(character),
    }


@api_router.post("/import")
def import_character(payload: CharacterImportRequest, db: Session = Depends(get_db)):
    token = payload.token.strip()
    character = db.query(Character).filter(Character.token_hash == _hash_token(token)).first()
    if character is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "token": token,
        "token_storage_key": TOKEN_STORAGE_KEY,
        "character": _serialize_character(character),
    }


@api_router.get("/me")
def get_me(character: Character = Depends(get_current_character)):
    return {"character": _serialize_character(character)}


@api_router.get("/export")
def export_character(character: Character = Depends(get_current_character)):
    return {
        "character": _serialize_character(character),
        "export_hint": "Copy your token from local storage and use Import/Continue on another device.",
    }
