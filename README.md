<p align="center">
  <img src="apps/web/public/logo.svg" alt="How's Your Day 로고" width="96" />
</p>

<h1 align="center">How's Your Day</h1>

<p align="center">
  감정, 취향, 상황을 함께 읽어 오늘의 이동을 덜 버겁게 정리하는 경로 추천 서비스
</p>

<p align="center">
  <a href="https://howsyourday.germy.kr">서비스 보기</a>
  ·
  <a href="#로컬-실행">로컬 실행</a>
  ·
  <a href="#api-개요">API 개요</a>
</p>

How's Your Day는 사용자가 길찾기 앱처럼 출발지와 도착지를 직접 입력할 수도 있고,
문장으로 “지금 어디서 어디까지 가야 하는지, 들러야 할 곳은 무엇인지, 지금 어떤
상태인지”를 말하면 이를 경로 추천 입력으로 바꿔주는 데모 서비스입니다.

단순히 가장 빠른 길만 고르는 대신, 사용자의 컨디션, 시간 압박, 걷기 부담,
선호/비선호 장소, 저장 장소, 경유 의도를 함께 반영합니다.

## 무엇을 하나요

- 자연어 이동 요청에서 출발지, 도착지, 시간 조건, 컨디션, 경유 의도를 추출합니다.
- 출발지와 도착지는 Kakao Local 검색 후보를 바탕으로 실제 장소에 가깝게 보정합니다.
- 카페, 다이소, 약국, 사진 찍기 같은 경유 의도를 카드로 보여주고 직접 수정할 수 있습니다.
- Kakao 장소 데이터와 OSRM/Tmap 경로 데이터를 이용해 후보 경로를 만듭니다.
- 피로, 혼잡, 걷기, 시간 압박, 회복 보너스 같은 감정 비용을 계산합니다.
- “이 길 괜찮았어요” 피드백은 사용자별 추천 기록으로 저장합니다.
- “별로였어요” 피드백은 저장하지 않고 사용자별 선호 가중치에만 반영합니다.
- 근처 실제 POI를 스와이프하며 선호/비선호를 쌓고, 경로 후보 판단에 반영합니다.

## 사용자 흐름

```text
사용자 문장 입력
  -> LLM 기반 의도/컨디션/경유 후보 추출
  -> Kakao Local 후보 검색 및 장소 검증
  -> 출발지/도착지/경유 의도 미리보기
  -> Kakao POI + OSRM/Tmap 경로 후보 생성
  -> 감정 비용과 선호/비선호 점수 반영
  -> 추천 경로, 지도, 판단 근거, 타임라인 표시
  -> 좋았던 경로 저장 / 별로였던 경로 학습
```

## 데모 문장 예시

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

## 기술 스택

- 프론트엔드: Next.js 15, React 19, Tailwind CSS, lucide-react
- 백엔드: FastAPI, Pydantic, SQLAlchemy
- 데이터베이스: PostgreSQL
- 인증: JWT access token
- LLM: OpenAI API를 활용한 의도, 컨디션, 경유지, 장소 판단
- 장소 검색: Kakao Local API
- 지도: Kakao Maps JavaScript SDK
- 경로 탐색: 개발 환경에서는 OSRM 우선, Tmap은 선택적으로 사용

## 저장소 구조

```text
apps/web               Next.js 웹 앱
server/api             FastAPI 엔드포인트와 스키마
server/agent           플래너 오케스트레이션
server/auth            JWT와 비밀번호 처리
server/db              SQLAlchemy 세션과 모델
server/memory          피드백 기반 가중치 모델
server/planner         경로 점수, 균형점, 최종 계획 조합
server/prompts         LLM 프롬프트
server/repositories    사용자별 DB 접근 계층
server/tools           Kakao, OSRM, Tmap, LLM, 지오코딩 도구
docs                   설계 메모와 도구 계약 문서
deploy/ec2             systemd/nginx 배포 파일
```

## 준비물

- Node.js 20 이상
- Python 3.11 이상
- Docker 또는 로컬 PostgreSQL
- Kakao REST API 키
- Kakao JavaScript 키
- OpenAI API 키
- Tmap 경로 탐색을 켤 경우 Tmap 앱 키

## 환경 변수

저장소 루트에 `.env`를 만듭니다. `.env.example`을 시작점으로 사용하면 됩니다.

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

API 서버를 `8011`번 포트에서 실행한다면 아래 값도 맞춰야 합니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8011
```

Kakao Maps JavaScript SDK를 로컬에서 쓰려면 Kakao Developers에 아래 웹 출처를 등록합니다.

```text
http://localhost:4000
http://127.0.0.1:4000
```

## 로컬 실행

웹 의존성을 설치합니다.

```bash
npm install
```

PostgreSQL을 실행합니다.

```bash
docker compose up -d db
```

API 서버 의존성을 설치하고 실행합니다.

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

웹 앱은 4000번 포트로 실행합니다.

```bash
npm --workspace apps/web run dev -- -p 4000
```

브라우저에서 아래 주소를 엽니다.

```text
http://localhost:4000
```

## 자주 쓰는 명령

웹 빌드:

```bash
npm run web:build
```

서버 테스트:

```bash
cd server
python -m pytest
```

API 서버 실행:

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8010
```

## API 개요

인증:

```text
POST /auth/signup
POST /auth/login
GET  /auth/me
```

경로 추천:

```text
POST /plan
POST /resolve-route-locations
POST /preview-insights
POST /search-locations
POST /geocode
POST /feedback
```

사용자 데이터:

```text
GET  /me/saved-places
POST /me/saved-places
DELETE /me/saved-places/{id}

GET  /me/place-preferences
POST /me/place-preferences

GET  /me/route-recommendations
```

## 개인화 구조

개인화는 현재 세 가지 층으로 동작합니다.

1. 장소 선호

   사용자는 주변 실제 POI를 `like` 또는 `dislike`로 스와이프합니다.
   이 데이터는 사용자별로 저장되고 경로 계획 맥락에 포함됩니다.

2. 경로 피드백

   긍정 피드백은 선택한 경로 스냅샷을 사용자별 추천 기록으로 저장합니다.
   부정 피드백은 경로를 저장하지 않고 사용자별 선호 가중치만 업데이트합니다.

3. 선호 가중치

   경로 피드백은 사용자별 걷기 민감도, 혼잡 민감도, 환승 민감도, 회복 선호도를 조정합니다.
   이 가중치는 이후 경로의 감정 비용 계산에 반영됩니다.

## 설계 원칙

- 감정은 장식이 아니라 경로 판단 변수로 다룹니다.
- 서비스는 사용자의 선택 부담을 줄여야 하며, 더 많은 조작을 강요하지 않아야 합니다.
- LLM 출력은 가능한 한 Kakao 장소 후보로 검증합니다.
- 외부 제공자 호출은 UI 컴포넌트에 직접 넣지 않고 도구 모듈 뒤에 둡니다.
- 저장 장소, 장소 선호, 경로 피드백, 경로 추천 기록은 사용자별로 분리되어야 합니다.

## 배포

배포 관련 파일은 `deploy/ec2`에 있습니다.

운영 도메인:

```text
https://howsyourday.germy.kr
```

EC2 배포는 아래 구성으로 동작합니다.

- Nginx
- FastAPI용 systemd 서비스
- Next 웹 앱용 systemd 서비스
- PostgreSQL 기반 사용자 데이터 저장

## 메모

- 개발 중에는 `HYS_DISABLE_TMAP=1`로 Tmap 호출을 끌 수 있습니다.
- OSRM은 개발과 데모에서 비용이 적은 경로 탐색 대체 수단으로 사용합니다.
- 루트의 `logo.svg`는 원본 에셋으로 취급하고, 웹 앱은 `apps/web/public/logo.svg`에 커밋된 사본을 제공합니다.
- 실제 API 키나 운영 시크릿은 커밋하지 않습니다.
