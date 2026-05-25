export type DailyPlan = {
  summary: string;
  emotion: {
    primary: string;
    walking_tolerance: string;
    crowd_tolerance: string;
    transfer_tolerance: string;
    recovery_need: string;
  };
  constraints: {
    deadline: string | null;
    destination: string | null;
  };
  stops: Array<{
    id: string;
    name: string;
    category: string;
    landmark_type: string;
    lat: number;
    lng: number;
  }>;
  score: {
    comfort_score: number;
    stress_score: number;
    reasons: string[];
  };
  tradeoffs: string[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";

export async function requestDailyPlan(userText: string): Promise<DailyPlan> {
  const response = await fetch(`${API_BASE_URL}/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      user_text: userText,
      origin: {
        label: "Current location",
        lat: 37.5882,
        lng: 126.9936
      }
    })
  });

  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  return response.json();
}
