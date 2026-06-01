# Emotion Waypoint Routing

감정 기반 길찾기는 Tmap에 감정을 직접 넘기는 방식이 아니다. 앱이 먼저
감정적으로 의미 있는 중간 지점을 고르고, Tmap은 그 지점을 기준으로 leg 단위
경로를 만든다.

## Flow

```text
user text
  -> LLM intent extraction
  -> LLM waypoint policy
  -> Kakao waypoint search
  -> detour and corridor filtering
  -> Tmap origin -> waypoint -> destination
  -> emotional cost scoring
  -> final route selection
```

## Rules

- LLM은 좌표를 만들지 않는다.
- LLM은 `조용한 카페`, `공원`, `도서관` 같은 검색 정책만 만든다.
- Kakao가 실제 장소와 좌표를 찾는다.
- Tmap은 확정된 좌표를 기준으로 길을 만든다.
- 시간이 촉박하면 optional waypoint를 만들지 않는다.
- waypoint가 너무 돌아가면 후보에서 제외한다.
- 최종 선택은 시간, 걷기, 환승, 혼잡, 회복 bonus를 함께 scoring한다.

## Examples

```text
피곤함 + 회복 필요 높음 + 시간 여유 있음
-> 조용한 카페/공원/도서관 후보를 찾고, 작은 detour면 경유 후보 생성
```

```text
급함 + 마감 임박
-> waypoint 추가 안 함, 기존 route 중 도착 안정성을 우선
```

현재 구현:

- `server/tools/llm_waypoint_policy.py`: 감정 waypoint 정책 생성
- `server/tools/emotion_waypoints.py`: Kakao 검색, detour/corridor 필터링
- `server/tools/route_path.py`: 기본 route와 waypoint route 후보 생성
- `server/tools/emotion_score.py`: 후보별 감정 비용 계산
