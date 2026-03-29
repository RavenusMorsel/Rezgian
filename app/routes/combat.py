import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import Character, CombatEncounter
from app.routes.auth import get_current_character
from app.systems.player_state import apply_damage, get_or_create_stats, serialize_vitals

router = APIRouter()


ENEMY_CATALOG: dict[str, dict] = {
    "cellar": {
        "name": "Cellar Rat",
        "health": 14,
        "player_damage": (3, 8),
        "enemy_damage": (1, 4),
        "reward": (2, 5),
    },
    "forest_path": {
        "name": "Scrub Wolf",
        "health": 22,
        "player_damage": (3, 8),
        "enemy_damage": (2, 6),
        "reward": (3, 7),
    },
    "deep_forest_path": {
        "name": "Briar Boar",
        "health": 28,
        "player_damage": (3, 8),
        "enemy_damage": (3, 7),
        "reward": (5, 10),
    },
    "main_road": {
        "name": "Roadside Bandit",
        "health": 24,
        "player_damage": (3, 8),
        "enemy_damage": (2, 7),
        "reward": (4, 9),
    },
}

DEFAULT_ENEMY = {
    "name": "Restless Drifter",
    "health": 18,
    "player_damage": (3, 8),
    "enemy_damage": (2, 5),
    "reward": (3, 6),
}


class CombatRoomRequest(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)


def _enemy_for_room(room_id: str) -> dict:
    return ENEMY_CATALOG.get(room_id, DEFAULT_ENEMY)


def _serialize_encounter(encounter: CombatEncounter | None) -> dict | None:
    if encounter is None:
        return None
    return {
        "room_id": encounter.room_id,
        "enemy_name": encounter.enemy_name,
        "enemy_health": encounter.enemy_health,
        "enemy_max_health": encounter.enemy_max_health,
    }


def _get_encounter(db: Session, character: Character, room_id: str) -> CombatEncounter | None:
    return (
        db.query(CombatEncounter)
        .filter(
            CombatEncounter.character_id == character.id,
            CombatEncounter.room_id == room_id,
        )
        .first()
    )


def _create_encounter(db: Session, character: Character, room_id: str) -> CombatEncounter:
    profile = _enemy_for_room(room_id)
    encounter = CombatEncounter(
        character_id=character.id,
        room_id=room_id,
        enemy_name=profile["name"],
        enemy_health=int(profile["health"]),
        enemy_max_health=int(profile["health"]),
    )
    db.add(encounter)
    db.flush()
    return encounter


@router.get("/state")
def combat_state(
    room_id: str,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    stats = get_or_create_stats(db, character)
    encounter = _get_encounter(db, character, room_id)
    db.commit()
    return {
        "vitals": serialize_vitals(stats),
        "encounter": _serialize_encounter(encounter),
    }


@router.post("/engage")
def engage(
    payload: CombatRoomRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    stats = get_or_create_stats(db, character)
    if stats.health <= 0:
        stats.health = 1

    encounter = _get_encounter(db, character, payload.room_id)
    if encounter is None:
        encounter = _create_encounter(db, character, payload.room_id)

    db.commit()
    return {
        "status": "engaged",
        "vitals": serialize_vitals(stats),
        "encounter": _serialize_encounter(encounter),
    }


@router.post("/attack")
def attack(
    payload: CombatRoomRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    stats = get_or_create_stats(db, character)
    if stats.health <= 0:
        raise HTTPException(status_code=400, detail="You are incapacitated")

    encounter = _get_encounter(db, character, payload.room_id)
    if encounter is None:
        encounter = _create_encounter(db, character, payload.room_id)

    profile = _enemy_for_room(payload.room_id)
    min_p, max_p = profile["player_damage"]
    min_e, max_e = profile["enemy_damage"]
    min_reward, max_reward = profile["reward"]

    player_damage = random.randint(min_p, max_p)
    encounter.enemy_health = max(0, encounter.enemy_health - player_damage)

    log: list[str] = [f"You hit {encounter.enemy_name} for {player_damage}."]

    if encounter.enemy_health <= 0:
        reward = random.randint(min_reward, max_reward)
        character.currency += reward
        db.delete(encounter)
        db.commit()
        return {
            "status": "victory",
            "log": log + [f"{encounter.enemy_name} falls. You gain {reward} coins."],
            "reward": {"currency": reward},
            "vitals": serialize_vitals(stats),
            "encounter": None,
            "currency": character.currency,
        }

    enemy_damage = random.randint(min_e, max_e)
    taken = apply_damage(stats, enemy_damage)
    log.append(f"{encounter.enemy_name} strikes back for {taken}.")

    defeated = stats.health <= 0
    if defeated:
        stats.health = 1
        db.delete(encounter)
        log.append("You collapse and barely escape with 1 HP.")

    db.commit()
    return {
        "status": "defeated" if defeated else "ongoing",
        "log": log,
        "vitals": serialize_vitals(stats),
        "encounter": None if defeated else _serialize_encounter(encounter),
        "currency": character.currency,
    }


@router.post("/flee")
def flee(
    payload: CombatRoomRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    encounter = _get_encounter(db, character, payload.room_id)
    if encounter is not None:
        db.delete(encounter)
        db.commit()
        return {"status": "fled", "encounter": None}

    return {"status": "idle", "encounter": None}
