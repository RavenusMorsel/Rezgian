"""Room-based combat endpoints and encounter lifecycle management."""

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import Character, CombatEncounter
from app.routes.auth import get_current_character
from app.routes.economy import ITEM_CATALOG, _dump_inventory, _load_inventory
from app.systems.player_state import apply_damage, get_or_create_stats, serialize_vitals

router = APIRouter()
COMBAT_ENABLED_ROOMS = {"cellar"}


ENEMY_CATALOG: dict[str, list[dict]] = {
    "cellar": [
        {
            "name": "Skittering Rat",
            "weight": 40,
            "health": 12,
            "player_damage": (3, 8),
            "enemy_damage": (1, 3),
            "reward": (2, 4),
            "drops": [
                {"item_id": "rat_tail", "chance": 0.45, "quantity": (1, 1)},
            ],
        },
        {
            "name": "Bloated Cellar Rat",
            "weight": 30,
            "health": 16,
            "player_damage": (3, 8),
            "enemy_damage": (2, 4),
            "reward": (3, 6),
            "drops": [
                {"item_id": "mildewed_fang", "chance": 0.35, "quantity": (1, 1)},
            ],
        },
        {
            "name": "Gnawtooth Rat",
            "weight": 20,
            "health": 20,
            "player_damage": (3, 8),
            "enemy_damage": (2, 5),
            "reward": (5, 8),
            "drops": [
                {"item_id": "mildewed_fang", "chance": 0.55, "quantity": (1, 1)},
                {"item_id": "cellar_key_fragment", "chance": 0.18, "quantity": (1, 1)},
            ],
        },
        {
            "name": "Starved Cave Bat",
            "weight": 10,
            "health": 10,
            "player_damage": (3, 8),
            "enemy_damage": (1, 5),
            "reward": (4, 7),
            "drops": [
                {"item_id": "bat_wing", "chance": 0.5, "quantity": (1, 2)},
            ],
        },
    ]
}


class CombatRoomRequest(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)


def _enemy_pool_for_room(room_id: str) -> list[dict]:
    """Return encounter profiles for a combat-enabled room."""
    return ENEMY_CATALOG.get(room_id, [])


def _enemy_profile_for_encounter(room_id: str, enemy_name: str) -> dict | None:
    """Resolve profile by persisted encounter name."""
    for profile in _enemy_pool_for_room(room_id):
        if profile["name"] == enemy_name:
            return profile
    return None


def _roll_enemy_for_room(room_id: str) -> dict | None:
    """Choose a weighted enemy variant for room encounter creation."""
    pool = _enemy_pool_for_room(room_id)
    if not pool:
        return None

    total_weight = sum(max(1, int(profile.get("weight", 1))) for profile in pool)
    pick = random.randint(1, total_weight)
    running = 0
    for profile in pool:
        running += max(1, int(profile.get("weight", 1)))
        if pick <= running:
            return profile
    return pool[-1]


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
    profile = _roll_enemy_for_room(room_id)
    if profile is None:
        raise HTTPException(status_code=400, detail="Combat is not available in this room")

    # Encounters are deterministic from room profile and persist until victory/flee/defeat.
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


def _resolve_enemy_drops(profile: dict) -> list[dict]:
    """Resolve random drop list for defeated enemy profile."""
    dropped: list[dict] = []
    for drop in profile.get("drops", []):
        chance = float(drop.get("chance", 0.0))
        if random.random() > chance:
            continue

        item_id = str(drop.get("item_id", "")).strip()
        if not item_id:
            continue

        qty_min, qty_max = drop.get("quantity", (1, 1))
        quantity = random.randint(int(qty_min), int(qty_max))
        if quantity <= 0:
            continue

        dropped.append({"item_id": item_id, "quantity": quantity})
    return dropped


@router.get("/state")
def combat_state(
    room_id: str,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    combat_available = room_id in COMBAT_ENABLED_ROOMS
    stats = get_or_create_stats(db, character)
    encounter = _get_encounter(db, character, room_id) if combat_available else None
    db.commit()
    return {
        "combat_available": combat_available,
        "vitals": serialize_vitals(stats),
        "encounter": _serialize_encounter(encounter),
    }


@router.post("/engage")
def engage(
    payload: CombatRoomRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    if payload.room_id not in COMBAT_ENABLED_ROOMS:
        stats = get_or_create_stats(db, character)
        db.commit()
        return {
            "status": "peaceful",
            "combat_available": False,
            "vitals": serialize_vitals(stats),
            "encounter": None,
        }

    stats = get_or_create_stats(db, character)
    if stats.health <= 1:
        raise HTTPException(status_code=400, detail="You are too wounded to fight. Heal before engaging.")

    encounter = _get_encounter(db, character, payload.room_id)
    if encounter is None:
        encounter = _create_encounter(db, character, payload.room_id)

    db.commit()
    return {
        "status": "engaged",
        "combat_available": True,
        "vitals": serialize_vitals(stats),
        "encounter": _serialize_encounter(encounter),
    }


@router.post("/attack")
def attack(
    payload: CombatRoomRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    if payload.room_id not in COMBAT_ENABLED_ROOMS:
        raise HTTPException(status_code=400, detail="This is a safe area")

    stats = get_or_create_stats(db, character)
    if stats.health <= 1:
        raise HTTPException(status_code=400, detail="You are too wounded to fight. Heal first.")

    encounter = _get_encounter(db, character, payload.room_id)
    if encounter is None:
        raise HTTPException(status_code=400, detail="No active encounter. Engage first.")

    profile = _enemy_profile_for_encounter(payload.room_id, encounter.enemy_name)
    if profile is None:
        raise HTTPException(status_code=500, detail="Encounter profile mismatch")

    min_p, max_p = profile["player_damage"]
    min_e, max_e = profile["enemy_damage"]
    min_reward, max_reward = profile["reward"]

    player_damage = random.randint(min_p, max_p)
    encounter.enemy_health = max(0, encounter.enemy_health - player_damage)

    log: list[str] = [f"You hit {encounter.enemy_name} for {player_damage}."]

    if encounter.enemy_health <= 0:
        reward = random.randint(min_reward, max_reward)
        character.currency += reward
        inventory = _load_inventory(character.inventory_json)
        drops = _resolve_enemy_drops(profile)
        reward_lines = [f"{encounter.enemy_name} falls. You gain {reward} coins."]

        serialized_drops: list[dict] = []
        for drop in drops:
            item_id = drop["item_id"]
            quantity = int(drop["quantity"])
            inventory[item_id] = inventory.get(item_id, 0) + quantity
            item_meta = ITEM_CATALOG.get(item_id)
            item_name = item_meta["name"] if item_meta else item_id.replace("_", " ").title()
            reward_lines.append(f"Loot: {item_name} x{quantity}.")
            serialized_drops.append({
                "item_id": item_id,
                "name": item_name,
                "quantity": quantity,
            })

        if drops:
            character.inventory_json = _dump_inventory(inventory)

        db.delete(encounter)
        db.commit()
        return {
            "status": "victory",
            "combat_available": True,
            "log": log + reward_lines,
            "reward": {"currency": reward, "items": serialized_drops},
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
        "combat_available": True,
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
    if payload.room_id not in COMBAT_ENABLED_ROOMS:
        return {"status": "peaceful", "combat_available": False, "encounter": None}

    encounter = _get_encounter(db, character, payload.room_id)
    if encounter is not None:
        db.delete(encounter)
        db.commit()
        return {"status": "fled", "combat_available": True, "encounter": None}

    return {"status": "idle", "combat_available": True, "encounter": None}
