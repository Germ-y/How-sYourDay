"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";
import {
  ArrowRight,
  Brain,
  Clock,
  Compass,
  HeartPulse,
  MapPinned,
  Sparkles
} from "lucide-react";
import {
  requestDailyPlan,
  type Coordinate,
  type DailyPlan,
  type EmotionCost,
  type MapViewModel,
  type RouteCandidate
} from "@/lib/api";

const samplePrompts = [
  {
    label: "피곤한 날",
    text: "I need to print my report, visit a clinic, and get home by 5. I am tired today."
  },
  {
    label: "급한 날",
    text: "I am in a hurry and need to get home by 5."
  },
  {
    label: "회복이 필요한 날",
    text: "I need to rest before going home."
  }
];

const starterText = samplePrompts[0].text;

export default function HomePage() {
  const [text, setText] = useState(starterText);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const result = await requestDailyPlan(text);
      setPlan(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to plan day.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-field text-ink">
      <section className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-6 px-5 py-6 lg:grid-cols-[360px_1fr] lg:px-8">
        <aside className="flex flex-col gap-5 lg:sticky lg:top-6 lg:h-[calc(100vh-48px)]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-moss">
              How&apos;s Your Day
            </p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight">
              하루 동선을 감정 비용까지 계산해서 조율합니다.
            </h1>
          </div>

          <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
            <textarea
              className="min-h-44 resize-none rounded-lg border border-ink/15 bg-white p-4 text-base leading-7 shadow-sm outline-none focus:border-tide"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <button
              className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-ink px-4 font-semibold text-white transition hover:bg-tide disabled:cursor-not-allowed disabled:bg-ink/45"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? "Planning..." : "Generate plan"}
              <ArrowRight size={18} aria-hidden />
            </button>
          </form>

          <div className="grid gap-2">
            <p className="text-sm font-semibold text-ink/70">Demo prompts</p>
            <div className="grid grid-cols-1 gap-2">
              {samplePrompts.map((prompt) => (
                <button
                  className="flex items-center justify-between rounded-lg border border-ink/10 bg-white px-3 py-2 text-left text-sm shadow-sm transition hover:border-tide hover:text-tide"
                  key={prompt.label}
                  type="button"
                  onClick={() => setText(prompt.text)}
                >
                  <span>{prompt.label}</span>
                  <Sparkles size={15} aria-hidden />
                </button>
              ))}
            </div>
          </div>

          {error ? (
            <p className="rounded-lg border border-coral/40 bg-white p-3 text-sm text-coral">
              {error}
            </p>
          ) : null}

          <div className="rounded-lg border border-ink/10 bg-white p-4 text-sm leading-6 text-ink/65 shadow-sm">
            planner는 route 후보를 모두 scoring한 뒤, 시간 제약과 감정 비용의
            tradeoff를 비교합니다.
          </div>
        </aside>

        {plan ? <PlannerDashboard plan={plan} /> : <EmptyDashboard />}
      </section>
    </main>
  );
}

function EmptyDashboard() {
  return (
    <section className="grid min-h-[720px] place-items-center rounded-lg border border-ink/10 bg-white p-8 shadow-sm">
      <div className="max-w-xl text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-field text-tide">
          <Brain size={28} aria-hidden />
        </div>
        <h2 className="mt-5 text-2xl font-semibold">Planner dashboard</h2>
        <p className="mt-3 leading-7 text-ink/65">
          프롬프트를 실행하면 선택된 route, 감정 비용 breakdown, tradeoff,
          timeline, mock map preview가 이곳에 표시됩니다.
        </p>
      </div>
    </section>
  );
}

function PlannerDashboard({ plan }: { plan: DailyPlan }) {
  return (
    <section className="grid gap-5">
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <SelectedRouteCard plan={plan} />
        <MapPreview map={plan.map_overlays} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          icon={<Brain size={20} aria-hidden />}
          label="Emotion"
          value={plan.emotion.primary}
          detail={`${plan.emotion.walking_tolerance} walking · ${plan.emotion.crowd_tolerance} crowd`}
        />
        <MetricCard
          icon={<HeartPulse size={20} aria-hidden />}
          label="Comfort"
          value={`${plan.emotional_cost.comfort_score}`}
          detail={`stress ${plan.emotional_cost.stress_score}`}
        />
        <MetricCard
          icon={<Clock size={20} aria-hidden />}
          label="Deadline"
          value={plan.constraints.deadline ?? "--"}
          detail={plan.constraints.destination ?? "destination inferred later"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <EmotionalCostPanel cost={plan.emotional_cost} />
        <TradeoffPanel plan={plan} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <TimelinePanel plan={plan} />
        <RouteComparison routes={plan.routes} selectedRouteId={plan.selected_route.id} />
      </div>
    </section>
  );
}

function SelectedRouteCard({ plan }: { plan: DailyPlan }) {
  return (
    <article className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">
            Selected Route
          </p>
          <h2 className="mt-2 text-3xl font-semibold">{plan.selected_route.id}</h2>
        </div>
        <span className="rounded-full bg-field px-3 py-1 text-sm font-semibold text-tide">
          {plan.selected_route.provider}
        </span>
      </div>

      <p className="mt-4 max-w-3xl leading-7 text-ink/70">{plan.explanation}</p>

      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        <RouteStat label="Minutes" value={plan.selected_route.estimated_minutes} />
        <RouteStat label="Walking" value={plan.selected_route.walking_minutes} />
        <RouteStat label="Transfers" value={plan.selected_route.transfer_count} />
        <RouteStat label="Crowd" value={plan.selected_route.crowd_level} />
      </div>

      {plan.recommendations.length > 0 ? (
        <div className="mt-5 grid gap-2">
          {plan.recommendations.map((item) => (
            <div
              className="flex items-start gap-2 rounded-lg bg-field p-3 text-sm leading-6 text-ink/70"
              key={`${item.kind}-${item.label}`}
            >
              <Sparkles className="mt-0.5 text-coral" size={16} aria-hidden />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function RouteStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-field p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/45">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold capitalize">{value}</p>
    </div>
  );
}

function EmotionalCostPanel({ cost }: { cost: EmotionCost }) {
  const costs = [
    ["Fatigue", cost.fatigue_cost],
    ["Walking", cost.walking_cost],
    ["Crowd", cost.crowd_cost],
    ["Transfer", cost.transfer_cost],
    ["Time pressure", cost.time_pressure_cost],
    ["Familiarity bonus", -cost.familiarity_bonus],
    ["Recovery bonus", -cost.recovery_bonus]
  ] as const;

  return (
    <article className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">
            Emotional Cost
          </p>
          <h2 className="mt-2 text-2xl font-semibold">
            total {cost.total_emotional_cost}
          </h2>
        </div>
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-field text-2xl font-semibold text-tide">
          {cost.comfort_score}
        </div>
      </div>

      <div className="mt-5 grid gap-3">
        {costs.map(([label, value]) => (
          <CostBar key={label} label={label} value={value} />
        ))}
      </div>

      <ul className="mt-5 grid gap-2 text-sm leading-6 text-ink/65">
        {cost.reasons.slice(0, 3).map((reason) => (
          <li className="rounded-lg bg-field px-3 py-2" key={reason}>
            {reason}
          </li>
        ))}
      </ul>
    </article>
  );
}

function CostBar({ label, value }: { label: string; value: number }) {
  const width = Math.min(100, Math.abs(value) * 4);
  const isBonus = value < 0;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className={isBonus ? "text-moss" : "text-coral"}>
          {isBonus ? value : `+${value}`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-field">
        <div
          className={isBonus ? "h-full bg-moss" : "h-full bg-coral"}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function TradeoffPanel({ plan }: { plan: DailyPlan }) {
  return (
    <article className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">
        Tradeoffs
      </p>
      <h2 className="mt-2 text-2xl font-semibold">Why this route?</h2>

      <div className="mt-5 grid gap-3">
        {plan.tradeoffs.map((tradeoff) => (
          <div className="rounded-lg bg-field p-4" key={tradeoff.reason}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-ink px-3 py-1 text-xs font-semibold text-white">
                {tradeoff.user_visible_label}
              </span>
              <span className="text-sm text-ink/55">
                {tradeoff.chosen_option} vs {tradeoff.rejected_option}
              </span>
            </div>
            <p className="mt-3 leading-7 text-ink/72">{tradeoff.reason}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <span className="rounded-full bg-white px-3 py-1">
                time {formatDelta(tradeoff.cost_delta.estimated_minutes)}m
              </span>
              <span className="rounded-full bg-white px-3 py-1">
                emotion {formatDelta(tradeoff.cost_delta.emotional_cost)}
              </span>
            </div>
          </div>
        ))}

        {plan.tradeoffs.length === 0 ? (
          <p className="rounded-lg bg-field p-4 text-ink/65">
            No major tradeoff was needed for this plan.
          </p>
        ) : null}
      </div>
    </article>
  );
}

function TimelinePanel({ plan }: { plan: DailyPlan }) {
  return (
    <article className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">
        Timeline
      </p>
      <h2 className="mt-2 text-2xl font-semibold">Daily flow</h2>

      <ol className="mt-5 grid gap-3">
        {plan.estimated_timeline.map((item) => (
          <li className="grid grid-cols-[64px_1fr] gap-3" key={`${item.time}-${item.label}`}>
            <span className="rounded-lg bg-field px-2 py-2 text-center text-sm font-semibold">
              {item.time}
            </span>
            <span className="rounded-lg border border-ink/10 px-3 py-2 leading-6">
              <span className="block text-xs font-semibold uppercase tracking-[0.12em] text-ink/45">
                {item.type}
              </span>
              {item.label}
            </span>
          </li>
        ))}
      </ol>
    </article>
  );
}

function RouteComparison({
  routes,
  selectedRouteId
}: {
  routes: RouteCandidate[];
  selectedRouteId: string;
}) {
  return (
    <article className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">
        Candidate Routes
      </p>
      <h2 className="mt-2 text-2xl font-semibold">Planner search space</h2>
      <div className="mt-5 grid gap-3">
        {routes.map((route) => {
          const selected = route.id === selectedRouteId;
          return (
            <div
              className={`rounded-lg border p-4 ${
                selected ? "border-tide bg-tide/10" : "border-ink/10 bg-field"
              }`}
              key={route.id}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{route.id}</span>
                {selected ? (
                  <span className="rounded-full bg-tide px-3 py-1 text-xs font-semibold text-white">
                    selected
                  </span>
                ) : null}
              </div>
              <div className="mt-3 grid gap-2 text-sm text-ink/65 sm:grid-cols-4">
                <span>{route.estimated_minutes} min</span>
                <span>{route.walking_minutes} walking</span>
                <span>{route.transfer_count} transfers</span>
                <span className="capitalize">{route.crowd_level} crowd</span>
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function MapPreview({ map }: { map: MapViewModel }) {
  const projected = useMemo(() => createProjector(map), [map]);

  return (
    <article className="overflow-hidden rounded-lg border border-ink/10 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-ink/10 p-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">
            Map Preview
          </p>
          <h2 className="mt-1 text-2xl font-semibold">Mock route surface</h2>
        </div>
        <MapPinned className="text-tide" size={24} aria-hidden />
      </div>

      <div className="relative h-[360px] bg-field">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(23,33,29,0.05)_1px,transparent_1px),linear-gradient(rgba(23,33,29,0.05)_1px,transparent_1px)] bg-[size:42px_42px]" />
        <svg
          className="absolute inset-0 h-full w-full"
          role="img"
          aria-label="Mock map preview of planner routes"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {map.emotion_zones.map((zone) => {
            const point = projected(zone.center);
            return (
              <circle
                cx={point.x}
                cy={point.y}
                fill="rgba(217,111,93,0.22)"
                key={zone.id}
                r="8"
                stroke="rgba(217,111,93,0.7)"
                strokeWidth="0.8"
              />
            );
          })}

          {map.polylines.map((polyline) => {
            const path = polyline.points
              .map((point) => {
                const projectedPoint = projected(point);
                return `${projectedPoint.x},${projectedPoint.y}`;
              })
              .join(" ");
            return (
              <polyline
                fill="none"
                key={polyline.id}
                points={path}
                stroke={polyline.selected ? "#4f8a9b" : polyline.emotion_level === "stressful" ? "#d96f5d" : "#8f9f89"}
                strokeDasharray={polyline.selected ? "0" : "3 3"}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={polyline.selected ? "3.2" : "1.8"}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>

        {map.markers.map((marker) => {
          const point = projected(marker);
          return (
            <div
              className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1"
              key={marker.id}
              style={{ left: `${point.x}%`, top: `${point.y}%` }}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white shadow">
                {marker.badge}
              </span>
              <span className="max-w-[120px] rounded-md bg-white/92 px-2 py-1 text-center text-xs font-medium shadow-sm">
                {marker.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="grid gap-2 p-4 text-sm text-ink/65">
        {map.tradeoff_badges.map((badge) => (
          <div className="flex items-start gap-2 rounded-lg bg-field p-3" key={badge.description}>
            <Compass className="mt-0.5 text-tide" size={16} aria-hidden />
            <span>
              <span className="block font-semibold text-ink">{badge.label}</span>
              {badge.description}
            </span>
          </div>
        ))}
      </div>
    </article>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 text-ink/60">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <p className="mt-3 text-2xl font-semibold capitalize">{value}</p>
      <p className="mt-1 text-sm text-ink/60">{detail}</p>
    </article>
  );
}

function createProjector(map: MapViewModel) {
  const west = map.fit_bounds.south_west.lng;
  const east = map.fit_bounds.north_east.lng;
  const south = map.fit_bounds.south_west.lat;
  const north = map.fit_bounds.north_east.lat;
  const lngRange = Math.max(0.0001, east - west);
  const latRange = Math.max(0.0001, north - south);

  return (point: Coordinate) => ({
    x: 12 + ((point.lng - west) / lngRange) * 76,
    y: 88 - ((point.lat - south) / latRange) * 76
  });
}

function formatDelta(value: number) {
  if (value > 0) {
    return `+${value}`;
  }
  return `${value}`;
}
