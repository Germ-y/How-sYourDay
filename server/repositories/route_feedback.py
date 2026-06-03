from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import FeedbackRequest
from db.models import RouteFeedback, RouteRecommendation, UserPreferenceWeight
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
) -> tuple[UserPreferenceWeights, RouteRecommendation | None]:
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

    recommendation = _create_route_recommendation(db, user_id, payload)
    feedback = RouteFeedback(
        user_id=user_id,
        route_recommendation_id=recommendation.id if recommendation else None,
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
    if recommendation:
        db.refresh(recommendation)
    return _weights_from_row(row), recommendation


def list_route_feedback(db: Session, user_id: str) -> list[RouteFeedback]:
    ensure_user(db, user_id)
    statement = (
        select(RouteFeedback)
        .where(RouteFeedback.user_id == user_id)
        .order_by(RouteFeedback.created_at.desc())
    )
    return list(db.scalars(statement).all())


def list_route_recommendations(
    db: Session, user_id: str, limit: int = 20
) -> list[RouteRecommendation]:
    ensure_user(db, user_id)
    statement = (
        select(RouteRecommendation)
        .where(RouteRecommendation.user_id == user_id)
        .order_by(RouteRecommendation.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def _create_route_recommendation(
    db: Session,
    user_id: str,
    payload: FeedbackRequest,
) -> RouteRecommendation | None:
    if not payload.liked or not payload.origin or not payload.selected_route:
        return None

    destination = payload.destination
    recommendation = RouteRecommendation(
        user_id=user_id,
        origin_label=payload.origin.label,
        origin_lat=payload.origin.lat,
        origin_lng=payload.origin.lng,
        destination_label=destination.label if destination else None,
        destination_lat=destination.lat if destination else None,
        destination_lng=destination.lng if destination else None,
        selected_route_json={
            "selected_route": payload.selected_route,
            "plan_snapshot": payload.plan_snapshot,
        },
        emotion_json=payload.emotion or {"primary": payload.emotion_primary},
    )
    db.add(recommendation)
    db.flush()
    return recommendation


def _weights_from_row(row: UserPreferenceWeight) -> UserPreferenceWeights:
    return UserPreferenceWeights(
        walking_sensitivity=row.walking_sensitivity,
        crowd_sensitivity=row.crowd_sensitivity,
        transfer_sensitivity=row.transfer_sensitivity,
        recovery_affinity=row.recovery_affinity,
    )
