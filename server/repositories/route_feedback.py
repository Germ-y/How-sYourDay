from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import FeedbackRequest
from db.models import RouteFeedback, UserPreferenceWeight
from memory.preferences import UserPreferenceWeights, update_weights_from_feedback
from repositories.saved_places import ensure_user


def load_user_preference_weights(db: Session, user_id: str) -> UserPreferenceWeights:
    ensure_user(db, user_id)
    row = db.get(UserPreferenceWeight, user_id)
    if row is None:
        return UserPreferenceWeights()

    return _weights_from_row(row)


def record_user_route_feedback(
    db: Session,
    user_id: str,
    payload: FeedbackRequest,
) -> UserPreferenceWeights:
    ensure_user(db, user_id)

    current = load_user_preference_weights(db, user_id)
    next_weights = update_weights_from_feedback(
        current=current,
        liked_route=payload.liked,
        reason=payload.reason,
    )

    row = db.get(UserPreferenceWeight, user_id)
    if row is None:
        row = UserPreferenceWeight(user_id=user_id)

    row.walking_sensitivity = next_weights.walking_sensitivity
    row.crowd_sensitivity = next_weights.crowd_sensitivity
    row.transfer_sensitivity = next_weights.transfer_sensitivity
    row.recovery_affinity = next_weights.recovery_affinity

    feedback = RouteFeedback(
        user_id=user_id,
        route_recommendation_id=None,
        route_id=payload.route_id,
        emotion_primary=payload.emotion_primary,
        provider=payload.provider,
        liked=payload.liked,
        reason=payload.reason,
    )

    db.add(row)
    db.add(feedback)
    db.commit()
    db.refresh(row)
    return _weights_from_row(row)


def list_route_feedback(db: Session, user_id: str) -> list[RouteFeedback]:
    ensure_user(db, user_id)
    statement = (
        select(RouteFeedback)
        .where(RouteFeedback.user_id == user_id)
        .order_by(RouteFeedback.created_at.desc())
    )
    return list(db.scalars(statement).all())


def _weights_from_row(row: UserPreferenceWeight) -> UserPreferenceWeights:
    return UserPreferenceWeights(
        walking_sensitivity=row.walking_sensitivity,
        crowd_sensitivity=row.crowd_sensitivity,
        transfer_sensitivity=row.transfer_sensitivity,
        recovery_affinity=row.recovery_affinity,
    )
