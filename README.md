# How's Your Day

감정 상태를 행동 변수로 바꿔 하루 동선을 조율하는 planning agent입니다.

이 프로젝트는 단순한 지도 앱이 아닙니다. 사용자의 할 일, 시간 제약,
현재 감정 상태를 받아서 현실적인 하루 이동 계획을 만드는 deterministic
agent harness를 목표로 합니다.

## 핵심 아이디어

사용자는 항상 장소 이름으로 검색하지 않습니다. 실제로는 의도에서 출발합니다.

- "수업 전에 프린트해야 해."
- "병원 들렀다가 5시까지 집에 가야 해."
- "오늘 너무 피곤해서 복잡한 길은 피하고 싶어."

How's Your Day는 이런 입력을 다음 구조로 바꿉니다.

- 할 일과 우선순위
- 감정 상태를 번역한 행동 변수
- POI 검색 요구
- 후보 경로
- 감정 비용
- tradeoff 설명
- 최종 하루 플랜

## 감정의 역할

감정은 장식용 라벨이 아닙니다.

예를 들어 `tired`는 다음 결정 변수로 바뀝니다.

- 낮은 걷기 허용량
- 낮은 혼잡 허용량
- 중간 수준의 환승 허용량
- 높은 회복 필요성

planner는 이 값을 이용해 더 빠른 길과 더 편한 길 사이의 tradeoff를
계산합니다.

## 구조

```text
apps/web        Next.js 웹 shell
server/api      FastAPI entrypoint와 응답 schema
server/agent    tool orchestration
server/tools    mock/provider tool 함수
server/planner  경로 선택, tradeoff 평가, 최종 플랜 조합
server/memory   이후 개인화용 preference 모델
docs            planner contract와 설계 문서
```

## 현재 MVP 흐름

```text
User input
  -> intent/emotion 추출
  -> mock POI 후보 생성
  -> mock route 후보 생성
  -> route별 감정 비용 계산
  -> hard constraint와 emotional cost 기반 route 선택
  -> timeline, recommendation, map view model 조합
```

실제 Kakao API는 아직 연결하지 않았습니다. 대신 mock provider를 현실적으로
구성해 planner intelligence를 먼저 검증합니다.

## 로컬 실행

### Web

```bash
cd apps/web
npm install
npm run dev
```

### API

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn api.main:app --reload --port 8010
```

## 환경 변수

실제 provider를 연결할 때 `.env.example`을 `.env`로 복사합니다.

```text
OPENAI_API_KEY=
KAKAO_REST_API_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
```
