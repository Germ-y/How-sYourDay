# How's Your Day

Emotion-aware daily planning agent for urban movement.

This project is not just a map app. It is a small agent harness that turns a
person's tasks, time limits, and emotional state into a realistic day plan.

## Core Idea

Users do not always search by place name. They often start from intent:

- "I need to print something before class."
- "I have to visit the clinic and get home by 5."
- "I am tired, so avoid crowded routes."

How's Your Day uses an agent layer to translate those inputs into:

- tasks
- emotion state
- POI search needs
- route candidates
- comfort scoring
- a final daily flow

## Architecture

```text
apps/web        Next.js web shell
server/api      FastAPI entrypoints
server/agent    LLM/tool orchestration
server/tools    Pure tool functions
server/memory   Preference and feedback models
server/planner  Daily plan composition
docs            Specs and engineering notes
```

## MVP Flow

```text
User input
  -> extract tasks and constraints
  -> infer emotion state
  -> search POI candidates
  -> build route candidates
  -> score comfort and stress
  -> generate final daily plan
```

The current version ships with deterministic mock tools so the harness can be
developed before real map and LLM APIs are connected.

## Local Development

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

## Environment

Copy `.env.example` to `.env` when real providers are added.

```text
OPENAI_API_KEY=
KAKAO_REST_API_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
```
