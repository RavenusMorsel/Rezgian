from sqlalchemy.orm import Session

from app.database.models import Character, CharacterStats

DEFAULT_MAX_HEALTH = 30


def get_or_create_stats(db: Session, character: Character) -> CharacterStats:
    stats = (
        db.query(CharacterStats)
        .filter(CharacterStats.character_id == character.id)
        .first()
    )
    if stats is None:
        stats = CharacterStats(
            character_id=character.id,
            health=DEFAULT_MAX_HEALTH,
            max_health=DEFAULT_MAX_HEALTH,
        )
        db.add(stats)
        db.flush()
    return stats


def serialize_vitals(stats: CharacterStats) -> dict:
    return {
        "health": stats.health,
        "max_health": stats.max_health,
        "health_pct": round((stats.health / stats.max_health) * 100, 1)
        if stats.max_health > 0
        else 0,
    }


def apply_heal(stats: CharacterStats, amount: int) -> int:
    if amount <= 0:
        return 0
    before = stats.health
    stats.health = min(stats.max_health, stats.health + amount)
    return stats.health - before


def apply_damage(stats: CharacterStats, amount: int) -> int:
    if amount <= 0:
        return 0
    before = stats.health
    stats.health = max(0, stats.health - amount)
    return before - stats.health
