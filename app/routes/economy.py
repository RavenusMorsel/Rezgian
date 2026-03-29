"""Economy endpoints for shop state, buying/selling, and consumable item use."""

import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.database.models import Character
from app.routes.auth import get_current_character
from app.systems.player_state import apply_heal, get_or_create_stats, serialize_vitals

router = APIRouter()


ITEM_CATALOG: dict[str, dict] = {
    "ale": {
        "name": "Foamy Ale",
        "description": "A hearty mug to steady your nerves.",
        "price": 4,
        "use": {"heal": 2},
    },
    "stew": {
        "name": "Thick Tavern Stew",
        "description": "Warm, salty, and suspiciously filling.",
        "price": 7,
        "use": {"heal": 6},
    },
    "lockpick_set": {
        "name": "Lockpick Set",
        "description": "Old tools, still sharp enough for dusty chests.",
        "price": 18,
    },
    "healing_herb": {
        "name": "Healing Herb",
        "description": "A bitter herb bundle used in simple remedies.",
        "price": 12,
        "use": {"heal": 12},
    },
    "torch": {
        "name": "Pitch Torch",
        "description": "A slow-burning torch for dark halls below.",
        "price": 9,
    },
}

ROOM_SHOPS: dict[str, list[str]] = {
    "tavern": ["ale", "stew", "torch", "lockpick_set", "healing_herb"],
}


def _load_inventory(raw: str) -> dict[str, int]:
    """Load inventory from JSON, supporting both legacy list and dict formats."""
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if isinstance(data, list):
        counts = Counter(item for item in data if isinstance(item, str))
        return {item_id: qty for item_id, qty in counts.items() if qty > 0}

    if isinstance(data, dict):
        clean: dict[str, int] = {}
        for item_id, qty in data.items():
            if isinstance(item_id, str) and isinstance(qty, int) and qty > 0:
                clean[item_id] = qty
        return clean

    return {}


def _dump_inventory(inventory: dict[str, int]) -> str:
    """Persist inventory in compact deterministic JSON form."""
    clean = {k: int(v) for k, v in inventory.items() if isinstance(k, str) and int(v) > 0}
    return json.dumps(clean, separators=(",", ":"))


def _serialize_inventory(inventory: dict[str, int]) -> list[dict]:
    """Expand inventory IDs into UI-friendly item metadata payloads."""
    output = []
    for item_id, qty in sorted(inventory.items()):
        item_meta = ITEM_CATALOG.get(item_id)
        output.append(
            {
                "item_id": item_id,
                "name": item_meta["name"] if item_meta else item_id,
                "description": item_meta["description"] if item_meta else "Unknown item",
                "quantity": qty,
                "base_price": item_meta["price"] if item_meta else 0,
                "usable": bool(item_meta and item_meta.get("use")),
            }
        )
    return output


def _shop_for_room(room_id: str) -> list[dict]:
    """Return catalog entries available for a specific room shop."""
    item_ids = ROOM_SHOPS.get(room_id, [])
    return [
        {
            "item_id": item_id,
            "name": ITEM_CATALOG[item_id]["name"],
            "description": ITEM_CATALOG[item_id]["description"],
            "price": ITEM_CATALOG[item_id]["price"],
        }
        for item_id in item_ids
        if item_id in ITEM_CATALOG
    ]


@router.get("/state")
def economy_state(
    room_id: str = "",
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    inventory = _load_inventory(character.inventory_json)
    stats = get_or_create_stats(db, character)
    db.commit()
    return {
        "character": {
            "name": character.name,
            "currency": character.currency,
        },
        "vitals": serialize_vitals(stats),
        "inventory": _serialize_inventory(inventory),
        "shop": _shop_for_room(room_id),
    }


class BuyRequest(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)
    item_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=20)


class SellRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=20)


class UseItemRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=20)


@router.post("/buy")
def buy_item(
    payload: BuyRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    room_shop = set(ROOM_SHOPS.get(payload.room_id, []))
    if payload.item_id not in room_shop:
        raise HTTPException(status_code=400, detail="That item is not sold here")

    item = ITEM_CATALOG.get(payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown item")

    total_cost = item["price"] * payload.quantity
    if character.currency < total_cost:
        raise HTTPException(status_code=400, detail="Not enough coins")

    inventory = _load_inventory(character.inventory_json)
    inventory[payload.item_id] = inventory.get(payload.item_id, 0) + payload.quantity

    character.currency -= total_cost
    character.inventory_json = _dump_inventory(inventory)
    stats = get_or_create_stats(db, character)
    db.commit()

    return {
        "status": "ok",
        "currency": character.currency,
        "vitals": serialize_vitals(stats),
        "inventory": _serialize_inventory(inventory),
    }


@router.post("/sell")
def sell_item(
    payload: SellRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    item = ITEM_CATALOG.get(payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown item")

    inventory = _load_inventory(character.inventory_json)
    current_qty = inventory.get(payload.item_id, 0)
    if current_qty < payload.quantity:
        raise HTTPException(status_code=400, detail="You do not have enough of that item")

    sell_value = max(1, item["price"] // 2)
    total_gain = sell_value * payload.quantity

    remaining = current_qty - payload.quantity
    if remaining > 0:
        inventory[payload.item_id] = remaining
    else:
        inventory.pop(payload.item_id, None)

    character.currency += total_gain
    character.inventory_json = _dump_inventory(inventory)
    stats = get_or_create_stats(db, character)
    db.commit()

    return {
        "status": "ok",
        "currency": character.currency,
        "vitals": serialize_vitals(stats),
        "inventory": _serialize_inventory(inventory),
    }


@router.post("/use")
def use_item(
    payload: UseItemRequest,
    db: Session = Depends(get_db),
    character: Character = Depends(get_current_character),
):
    item = ITEM_CATALOG.get(payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown item")

    use_effect = item.get("use")
    if not use_effect:
        raise HTTPException(status_code=400, detail="That item cannot be used right now")

    inventory = _load_inventory(character.inventory_json)
    owned = inventory.get(payload.item_id, 0)
    if owned < payload.quantity:
        raise HTTPException(status_code=400, detail="You do not have enough of that item")

    stats = get_or_create_stats(db, character)
    total_healed = 0

    if "heal" in use_effect:
        for _ in range(payload.quantity):
            total_healed += apply_heal(stats, int(use_effect["heal"]))

    remaining = owned - payload.quantity
    if remaining > 0:
        inventory[payload.item_id] = remaining
    else:
        inventory.pop(payload.item_id, None)

    character.inventory_json = _dump_inventory(inventory)
    db.commit()

    return {
        "status": "ok",
        "used": {
            "item_id": payload.item_id,
            "quantity": payload.quantity,
        },
        "effects": {
            "healed": total_healed,
        },
        "vitals": serialize_vitals(stats),
        "inventory": _serialize_inventory(inventory),
    }
