from api.schemas import LandmarkEmotionPrior


LANDMARK_PRIORS = {
    "park": LandmarkEmotionPrior(
        landmark_type="park",
        emotion_tags=["calm", "recovery", "walkable"],
        fatigue_modifier=-4,
        crowd_modifier=-3,
        noise_modifier=-2,
        recovery_bonus=8,
        reason="Parks usually provide calm recovery value for cold-start scoring.",
    ),
    "river": LandmarkEmotionPrior(
        landmark_type="river",
        emotion_tags=["calm", "recovery", "walkable"],
        fatigue_modifier=-3,
        crowd_modifier=-2,
        noise_modifier=-2,
        recovery_bonus=7,
        reason="Riverside routes tend to support decompression and steady walking.",
    ),
    "university": LandmarkEmotionPrior(
        landmark_type="university",
        emotion_tags=["familiar", "walkable"],
        fatigue_modifier=-1,
        crowd_modifier=1,
        noise_modifier=1,
        recovery_bonus=2,
        reason="University areas are familiar but can become moderately busy.",
    ),
    "transit_hub": LandmarkEmotionPrior(
        landmark_type="transit_hub",
        emotion_tags=["crowded", "stressful", "high_noise"],
        fatigue_modifier=2,
        crowd_modifier=5,
        noise_modifier=4,
        recovery_bonus=0,
        reason="Transit hubs reduce travel time but often increase crowd stress.",
    ),
    "main_road": LandmarkEmotionPrior(
        landmark_type="main_road",
        emotion_tags=["high_noise", "walkable"],
        fatigue_modifier=1,
        crowd_modifier=2,
        noise_modifier=4,
        recovery_bonus=0,
        reason="Main roads are efficient but noisy.",
    ),
    "side_street": LandmarkEmotionPrior(
        landmark_type="side_street",
        emotion_tags=["calm", "walkable"],
        fatigue_modifier=-2,
        crowd_modifier=-2,
        noise_modifier=-2,
        recovery_bonus=3,
        reason="Side streets are usually calmer and easier to tolerate.",
    ),
    "medical": LandmarkEmotionPrior(
        landmark_type="medical",
        emotion_tags=["stressful"],
        fatigue_modifier=1,
        crowd_modifier=1,
        noise_modifier=0,
        recovery_bonus=0,
        reason="Medical stops can be necessary but rarely feel restorative.",
    ),
    "commercial": LandmarkEmotionPrior(
        landmark_type="commercial",
        emotion_tags=["crowded", "walkable"],
        fatigue_modifier=1,
        crowd_modifier=3,
        noise_modifier=2,
        recovery_bonus=1,
        reason="Commercial areas are useful but can add crowd load.",
    ),
}


def get_landmark_emotion_prior(landmark_type: str) -> LandmarkEmotionPrior:
    return LANDMARK_PRIORS.get(landmark_type, LANDMARK_PRIORS["commercial"])


def get_landmark_priors(landmark_types: list[str]) -> list[LandmarkEmotionPrior]:
    return [get_landmark_emotion_prior(landmark_type) for landmark_type in landmark_types]
