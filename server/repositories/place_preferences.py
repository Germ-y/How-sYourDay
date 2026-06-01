from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from api.schemas import PlacePreferenceCreate
from db.models import PlacePreference
from repositories.saved_places import ensure_user


def list_place_preferences(db: Session, user_id: str) -> list[PlacePreference]:
    ensure_user(db, user_id)
    statement = (
        select(PlacePreference)
        .where(PlacePreference.user_id == user_id)
        .order_by(PlacePreference.updated_at.desc())
    )
    return list(db.scalars(statement).all())


def upsert_place_preference(
    db: Session,
    user_id: str,
    payload: PlacePreferenceCreate,
) -> PlacePreference:
    ensure_user(db, user_id)

    existing = _find_existing_preference(db, user_id, payload)
    if existing:
        existing.poi_provider_id = payload.poi_provider_id
        existing.name = payload.name
        existing.category = payload.category
        existing.lat = payload.lat
        existing.lng = payload.lng
        existing.preference = payload.preference
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    preference = PlacePreference(
        user_id=user_id,
        poi_provider_id=payload.poi_provider_id,
        name=payload.name,
        category=payload.category,
        lat=payload.lat,
        lng=payload.lng,
        preference=payload.preference,
    )
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


def _find_existing_preference(
    db: Session,
    user_id: str,
    payload: PlacePreferenceCreate,
) -> PlacePreference | None:
    conditions = []
    if payload.poi_provider_id:
        conditions.append(PlacePreference.poi_provider_id == payload.poi_provider_id)

    if payload.lat is not None and payload.lng is not None:
        conditions.append(
            and_(
                PlacePreference.name == payload.name,
                PlacePreference.lat == payload.lat,
                PlacePreference.lng == payload.lng,
            )
        )

    if not conditions:
        conditions.append(PlacePreference.name == payload.name)

    statement = select(PlacePreference).where(
        PlacePreference.user_id == user_id,
        or_(*conditions),
    )
    return db.scalars(statement).first()
