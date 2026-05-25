# How's Your Day

감정 상태를 행동 변수로 바꿔 하루 동선을 조율하는 planning agent입니다.

이 프로젝트는 단순 지도 앱이 아닙니다. 사용자의 할 일, 시간 제약, 현재
컨디션을 받아 Kakao 장소 데이터와 Tmap 경로 데이터를 조합하고, 감정 비용까지
포함해 하루 이동 계획을 만드는 agent harness입니다.

## 핵심 아이디어

사용자는 항상 장소 이름으로 검색하지 않습니다. 실제로는 의도에서 출발합니다.

- "수업 전에 프린트해야 해."
- "병원 들렀다가 5시까지 집에 가야 해."
- "오늘 너무 피곤해서 복잡한 길은 피하고 싶어."

How's Your Day는 이런 입력을 다음 구조로 바꿉니다.

- 할 일과 우선순위
- 감정 상태를 번역한 행동 변수
- Kakao POI 검색
- Tmap route 후보
- 감정 비용
- tradeoff 설명
- 최종 하루 플랜

## 현재 구현 상태

```text
User input
  -> intent/emotion 추출
  -> Kakao Local API로 POI 검색
  -> Tmap 도보/대중교통 route 후보 생성
  -> 실패한 짧은 leg는 estimated walking으로 보완
  -> route별 감정 비용 계산
  -> hard constraint와 emotional cost 기반 route 선택
  -> Kakao Maps JS SDK로 지도와 polyline 렌더링
```

mock route는 기본 후보가 아닙니다. Tmap route를 전혀 만들 수 없을 때만
fallback으로 사용합니다.

## 구조

```text
apps/web        Next.js 모바일 웹앱
server/api      FastAPI entrypoint와 응답 schema
server/agent    tool orchestration
server/tools    Kakao/Tmap provider adapter와 fallback tool
server/planner  경로 선택, tradeoff 평가, 최종 플랜 조합
server/memory   route feedback 기반 preference weight
docs            planner contract와 설계 문서
```

## 로컬 실행

### API

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

브라우저는 `http://localhost:3000`으로 여는 것을 권장합니다. Kakao
JavaScript SDK는 등록된 도메인에서만 동작하므로 Kakao Developers의 Web
플랫폼 도메인에도 `http://localhost:3000`을 등록해야 합니다.

## 환경 변수

root `.env`:

```text
KAKAO_REST_API_KEY=
TMAP_APP_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
```

`apps/web/.env.local`:

```text
NEXT_PUBLIC_KAKAO_JS_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
```

실제 키는 커밋하지 않습니다.

## 검증

```bash
cd server
python -m pytest
```

```bash
cd ..
npm run web:build
```

데모 확인:

- `I need to rest before going home.` 입력 시 Tmap route 후보가 표시되어야 합니다.
- Tmap key가 없거나 실패하면 mock fallback route가 표시됩니다.
- Kakao 지도는 `http://localhost:3000`에서 확인합니다.
