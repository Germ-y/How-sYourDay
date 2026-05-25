from agent.daily_planning_agent import DailyPlanningAgent
from api.schemas import Location, PlanRequest


def test_agent_returns_structured_plan() -> None:
    agent = DailyPlanningAgent()
    request = PlanRequest(
        user_text="I need to print and visit a clinic before 5. I am tired.",
        origin=Location(label="Current location", lat=37.5882, lng=126.9936),
    )

    plan = agent.run(request)

    assert plan.emotion.primary == "tired"
    assert plan.constraints.deadline == "17:00"
    assert len(plan.stops) == 2
    assert plan.score.comfort_score > 0

