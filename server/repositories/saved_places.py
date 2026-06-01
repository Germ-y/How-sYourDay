from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import SavedPlaceCreate
from db.models import SavedPlace, User


DEMO_USER_EMAIL = "demo@hows-your-day.local"


def ensure_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user:
        return user

    user = User(
        id=user_id,
        email=DEMO_USER_EMAIL if user_id == "demo-user" else f"{user_id}@local",
        nickname="균이" if user_id == "demo-user" else user_id,
    )
    db.add(user)
    db.flush()
    return user


def list_saved_places(db: Session, user_id: str) -> list[SavedPlace]:
    ensure_user(db, user_id)
    statement = (
        select(SavedPlace)
        .where(SavedPlace.user_id == user_id)
        .order_by(SavedPlace.updated_at.desc())
    )
    return list(db.scalars(statement).all())


def create_saved_place(
    db: Session,
    user_id: str,
    payload: SavedPlaceCreate,
) -> SavedPlace:
    ensure_user(db, user_id)

    existing = _find_by_address(db, user_id, payload.address)
    if existing:
        existing.name = payload.name
        existing.kind = payload.kind
        existing.lat = payload.lat
        existing.lng = payload.lng
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    place = SavedPlace(
        user_id=user_id,
        name=payload.name,
        address=payload.address,
        kind=payload.kind,
        lat=payload.lat,
        lng=payload.lng,
    )
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


def delete_saved_place(db: Session, user_id: str, place_id: str) -> bool:
    place = db.get(SavedPlace, place_id)
    if place is None or place.user_id != user_id:
        return False

    db.delete(place)
    db.commit()
    return True


def _find_by_address(db: Session, user_id: str, address: str) -> SavedPlace | None:
    statement = select(SavedPlace).where(
        SavedPlace.user_id == user_id,
        SavedPlace.address == address,
    )
    return db.scalars(statement).first()
