<p align="center">
  <img src="apps/web/public/logo.svg" alt="How's Your Day logo" width="96" />
</p>

<h1 align="center">How's Your Day</h1>

<p align="center">
  감정, 취향, 상황을 함께 읽어 오늘의 이동을 덜 버겁게 정리하는 경로 추천 서비스
</p>

<p align="center">
  <a href="https://howsyourday.germy.kr">Live Demo</a>
  ·
  <a href="#local-development">Local Development</a>
  ·
  <a href="#api-overview">API</a>
</p>

How's Your Day는 사용자가 길찾기 앱처럼 출발지와 도착지를 직접 입력할 수도 있고,
문장으로 “지금 어디서 어디까지 가야 하는지, 들러야 할 곳은 무엇인지, 지금 어떤
상태인지”를 말하면 이를 경로 추천 입력으로 바꿔주는 데모 서비스입니다.

단순히 가장 빠른 길만 고르는 대신, 사용자의 컨디션, 시간 압박, 걷기 부담,
선호/비선호 장소, 저장 장소, 경유 의도를 함께 반영합니다.

## What It Does

- 자연어 이동 요청에서 출발지, 도착지, 시간 조건, 컨디션, 경유 의도를 추출합니다.
- 출발지와 도착지는 Kakao Local 검색 후보를 바탕으로 실제 장소에 가깝게 보정합니다.
- 카페, 다이소, 약국, 사진 찍기 같은 경유 의도를 카드로 보여주고 직접 수정할 수 있습니다.
- Kakao 장소 데이터와 OSRM/Tmap 경로 데이터를 이용해 후보 경로를 만듭니다.
- 피로, 혼잡, 걷기, 시간 압박, 회복 보너스 같은 감정 비용을 계산합니다.
- “이 길 괜찮았어요” 피드백은 사용자별 추천 기록으로 저장합니다.
- “별로였어요” 피드백은 저장하지 않고 사용자별 선호 가중치에만 반영합니다.
- 근처 실제 POI를 스와이프하며 선호/비선호를 쌓고, 경로 후보 판단에 반영합니다.

## Product Flow

```text
사용자 문장 입력
  -> LLM 기반 의도/컨디션/경유 후보 추출
  -> Kakao Local 후보 검색 및 장소 검증
  -> 출발지/도착지/경유 의도 미리보기
  -> Kakao POI + OSRM/Tmap 경로 후보 생성
  -> 감정 비용과 선호/비선호 점수 반영
  -> 추천 경로, 지도, XAI, 타임라인 표시
  -> 좋았던 경로 저장 / 별로였던 경로 학습
```

## Example Prompts

```text
지금 성균관대야. 홍대입구역 3번 출구 앞에서 친구 만나야 하는데
약속까지 1시간 반 남았어. 가기 전에 상도 건영 106동에 들러야 해.
늦을까 봐 정신없고, 걷는 건 최대한 줄이고 싶어.
시간 되면 다이소에서 내일 필요한 공책도 사고 싶어.
아 친구 만나서 인생네컷도 갈 거야.
```

```text
서울숲에서 성수역까지 가는데 카페에서 노트북 작업 좀 하다가 가고 싶어.
너무 시끄러운 곳은 싫어.
```

```text
잠실역에서 석촌호수 지나서 롯데월드몰까지 가고 싶어.
오늘은 여유 있어서 예쁜 길이면 좀 돌아가도 괜찮아.
```

## Tech Stack

- Frontend: Next.js 15, React 19, Tailwind CSS, lucide-react
- Backend: FastAPI, Pydantic, SQLAlchemy
- Database: PostgreSQL
- Auth: JWT access token
- LLM: OpenAI API for intent, condition, waypoint, and location reasoning
- Places: Kakao Local API
- Map: Kakao Maps JavaScript SDK
- Routing: OSRM fallback-first in development, Tmap optional

## Repository Structure

```text
apps/web               Next.js web app
server/api             FastAPI endpoints and schemas
server/agent           Planner orchestration
server/auth            JWT and password handling
server/db              SQLAlchemy session and models
server/memory          Feedback weight model
server/planner         Route scoring, tradeoff, final plan composition
server/prompts         LLM prompts
server/repositories    User-scoped DB access
server/tools           Kakao, OSRM, Tmap, LLM, geocoding tools
docs                   Design notes and tool contracts
deploy/ec2             systemd/nginx deployment files
```

## Requirements

- Node.js 20+
- Python 3.11+
- Docker or local PostgreSQL
- Kakao REST API key
- Kakao JavaScript key
- OpenAI API key
- Tmap app key if Tmap routing is enabled

## Environment

Create `.env` in the repository root. `.env.example` is the starting point.

```env
OPENAI_API_KEY=
OPENAI_INTENT_MODEL=gpt-5-nano

KAKAO_REST_API_KEY=
NEXT_PUBLIC_KAKAO_JS_KEY=

HYS_DISABLE_TMAP=1
HYS_ROUTE_PROVIDER=osrm
OSRM_BASE_URL=https://router.project-osrm.org
OSRM_PROFILE=driving

TMAP_APP_KEY=

DATABASE_URL=postgresql+psycopg://hows_your_day:hows_your_day@localhost:5432/hows_your_day
JWT_SECRET_KEY=change-me-in-production

NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
```

If you run the API on `8011`, also set:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8011
```

For Kakao Maps JavaScript SDK, add the local web origin to Kakao Developers:

```text
http://localhost:4000
http://127.0.0.1:4000
```

## Local Development

Install web dependencies:

```bash
npm install
```

Start PostgreSQL:

```bash
docker compose up -d db
```

Install and run the API:

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

Run the web app on port 4000:

```bash
npm --workspace apps/web run dev -- -p 4000
```

Open:

```text
http://localhost:4000
```

## Useful Commands

```bash
npm run web:build
```

```bash
cd server
python -m pytest
```

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8010
```

## API Overview

Auth:

```text
POST /auth/signup
POST /auth/login
GET  /auth/me
```

Planning:

```text
POST /plan
POST /resolve-route-locations
POST /preview-insights
POST /search-locations
POST /geocode
POST /feedback
```

User data:

```text
GET  /me/saved-places
POST /me/saved-places
DELETE /me/saved-places/{id}

GET  /me/place-preferences
POST /me/place-preferences

GET  /me/route-recommendations
```

## Personalization

Personalization currently has three layers.

1. Place preference

   Users swipe nearby real POIs as `like` or `dislike`.
   These are stored per user and included in route planning context.

2. Route feedback

   Positive feedback saves the selected route snapshot as a user route recommendation.
   Negative feedback updates user preference weights but does not save the route.

3. Preference weights

   Route feedback adjusts walking, crowd, transfer, and recovery sensitivity per user.
   These weights influence future emotional cost scoring.

## Design Principles

- Emotion is a decision variable, not decoration.
- The service should reduce choice load, not make the user manage more controls.
- LLM output must be grounded by Kakao place candidates where possible.
- Provider calls stay behind tool modules, not directly inside UI components.
- User-scoped data must stay user-scoped: saved places, place preferences, route feedback, and route recommendations should not bleed across accounts.

## Deployment

Deployment files live in `deploy/ec2`.

Production domain:

```text
https://howsyourday.germy.kr
```

The EC2 deployment uses:

- Nginx
- systemd service for FastAPI
- systemd service for Next web
- PostgreSQL-backed user data

## Notes

- Tmap can be disabled in development with `HYS_DISABLE_TMAP=1`.
- OSRM is used as a cheaper routing fallback for development and demos.
- The root `logo.svg` is treated as the source asset. The web app serves the committed copy at `apps/web/public/logo.svg`.
- Do not commit real API keys or production secrets.
