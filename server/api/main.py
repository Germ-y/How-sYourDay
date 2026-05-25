from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.daily_planning_agent import DailyPlanningAgent
from api.schemas import PlanRequest, PlanResponse

app = FastAPI(title="How's Your Day API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = DailyPlanningAgent()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse)
def plan_day(request: PlanRequest) -> PlanResponse:
    return agent.run(request)

