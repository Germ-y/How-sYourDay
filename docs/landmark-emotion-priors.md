# Landmark Emotion Priors

사용자 피드백이 아직 없는 cold start 상태에서는 장소 유형별 임의 감정 prior로
route의 emotional cost를 계산한다. Tmap은 실제 시간, 거리, 도보, 환승 정보를
주고, 이 표는 그 route가 현재 감정 상태에 얼마나 부담스러운지 판단하는
planner 쪽 기준이다.

점수 의미:

- `emotion_tags`: route 설명과 감정 zone에 쓰는 정성 태그
- `fatigue_modifier`: 피곤함 비용 조정값. 낮을수록 덜 피곤한 장소
- `crowd_modifier`: 군중 부담 조정값. 높을수록 붐비는 장소
- `noise_modifier`: 소음 부담 조정값. 높을수록 시끄러운 장소
- `recovery_bonus`: 회복/휴식에 도움이 되는 정도

| Landmark type | 감정 prior | Fatigue | Crowd | Noise | Recovery | 메모 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `cafe` | calm, recovery, familiar | -3 | -2 | -1 | 7 | 카페는 지친 상태에서 쉬어가기 좋은 장소로 둔다. |
| `school` | crowded, stressful, familiar | 1 | 4 | 2 | 0 | 학교권은 익숙할 수 있지만 사람과 일정 압박이 있다고 본다. |
| `library` | calm, recovery, familiar | -2 | -2 | -3 | 5 | 조용하고 집중 회복에 좋은 장소로 둔다. |
| `convenience_store` | familiar, walkable | -1 | 0 | 0 | 2 | 편의점은 부담이 낮지만 강한 회복 장소는 아니다. |
| `restaurant` | crowded, familiar | 0 | 2 | 2 | 2 | 식사는 도움이 되지만 붐빔과 소음이 있을 수 있다. |
| `shopping_mall` | crowded, high_noise, stressful | 2 | 5 | 4 | 0 | 쇼핑몰은 자극이 큰 장소로 둔다. |
| `nightlife` | crowded, high_noise, stressful | 3 | 5 | 5 | 0 | 술집/번화가는 피곤한 사용자에게 비용이 크다. |
| `gym` | familiar, walkable | 2 | 1 | 1 | 1 | 익숙할 수 있지만 신체 피로 비용이 있다. |
| `government_office` | stressful, familiar | 1 | 2 | 1 | 0 | 행정 업무는 대기와 처리 부담이 있다고 본다. |
| `park` | calm, recovery, walkable | -4 | -3 | -2 | 8 | 공원은 가장 강한 회복 prior 중 하나다. |
| `river` | calm, recovery, walkable | -3 | -2 | -2 | 7 | 하천/강변은 산책과 감정 회복에 좋다고 본다. |
| `university` | familiar, walkable | -1 | 1 | 1 | 2 | 대학가는 익숙하지만 시간대에 따라 조금 붐빈다. |
| `transit_hub` | crowded, stressful, high_noise | 2 | 5 | 4 | 0 | 역/환승지는 빠르지만 감정 비용이 크다. |
| `main_road` | high_noise, walkable | 1 | 2 | 4 | 0 | 큰길은 효율적이지만 소음 부담이 있다. |
| `side_street` | calm, walkable | -2 | -2 | -2 | 3 | 골목길은 상대적으로 조용한 길로 둔다. |
| `medical` | stressful | 1 | 1 | 0 | 0 | 병원은 필요하지만 회복 장소로 보지는 않는다. |
| `commercial` | crowded, walkable | 1 | 3 | 2 | 1 | 기본 상권 fallback. 유용하지만 붐빌 수 있다. |

현재 반영 방식:

- `server/tools/landmark_emotion_prior.py`에 위 prior를 코드로 둔다.
- Kakao/Mock POI는 `landmark_type`과 `emotion_tags`를 가진다.
- Tmap route가 성공하더라도 `emotion_score`는 Tmap segment와 stop의
  `landmark_type`을 함께 읽어서 fatigue/crowd/familiarity/recovery 비용에
  반영한다.
- 따라서 Tmap route 우선 정책은 유지하되, 최종 선택은 실제 route 정보와 감정
  prior를 합친 planner objective로 결정한다.

나중에 사용자 피드백이 쌓이면 이 표 자체를 바꾸기보다 `memory/preferences.py`의
walking/crowd/transfer/recovery weight를 먼저 업데이트한다. 장소 prior는
서비스 전체의 기본 가정이고, preference weight는 사용자별 보정값이다.
