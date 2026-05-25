"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Brain,
  CheckCircle2,
  Clock3,
  HeartPulse,
  MapPinned,
  MessageCircle,
  Navigation,
  Sparkles,
  Zap
} from "lucide-react";
import {
  requestDailyPlan,
  sendRouteFeedback,
  type Coordinate,
  type DailyPlan,
  type EmotionCost,
  type Location,
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
    label: "쉬고 싶은 날",
    text: "I need to rest before going home."
  }
];

const starterText = samplePrompts[0].text;
const DEMO_ORIGIN: Location = {
  label: "Demo origin",
  lat: 37.5882,
  lng: 126.9936
};
const DEFAULT_DESTINATIONS: Record<string, Location> = {
  집: {
    label: "집",
    lat: 37.5826,
    lng: 127.0019
  },
  학교: {
    label: "학교",
    lat: 37.5882,
    lng: 126.9936
  },
  회사: {
    label: "회사",
    lat: 37.5665,
    lng: 126.978
  }
};
const DESTINATION_STORAGE_KEY = "hows-your-day.destinations.v1";

export default function HomePage() {
  const [text, setText] = useState(starterText);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [origin, setOrigin] = useState<Location>(DEMO_ORIGIN);
  const [destinations, setDestinations] =
    useState<Record<string, Location>>(DEFAULT_DESTINATIONS);
  const [selectedDestinationKey, setSelectedDestinationKey] = useState("집");
  const [locationStatus, setLocationStatus] = useState("demo 위치 사용 중");

  useEffect(() => {
    const stored = window.localStorage.getItem(DESTINATION_STORAGE_KEY);
    if (!stored) {
      return;
    }

    try {
      setDestinations({
        ...DEFAULT_DESTINATIONS,
        ...JSON.parse(stored)
      });
    } catch {
      window.localStorage.removeItem(DESTINATION_STORAGE_KEY);
    }
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const result = await requestDailyPlan(
        text,
        origin,
        destinations[selectedDestinationKey] ?? DEFAULT_DESTINATIONS["집"]
      );
      setPlan(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to plan day.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleUseCurrentLocation() {
    if (!navigator.geolocation) {
      setLocationStatus("현재 위치를 사용할 수 없어 demo 위치를 유지해요");
      return;
    }

    setLocationStatus("현재 위치 확인 중");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin({
          label: "현재 위치",
          lat: position.coords.latitude,
          lng: position.coords.longitude
        });
        setLocationStatus("현재 위치 사용 중");
      },
      () => {
        setOrigin(DEMO_ORIGIN);
        setLocationStatus("권한이 없어 demo 위치 사용 중");
      },
      {
        enableHighAccuracy: true,
        maximumAge: 60_000,
        timeout: 8_000
      }
    );
  }

  function handleDestinationSelect(key: string) {
    setSelectedDestinationKey(key);
    window.localStorage.setItem(
      DESTINATION_STORAGE_KEY,
      JSON.stringify(destinations)
    );
  }

  return (
    <main className="min-h-screen bg-[#f6f8f4] text-ink">
      <form
        className="mx-auto flex min-h-screen w-full max-w-md flex-col pb-24 lg:max-w-6xl lg:px-6"
        onSubmit={handleSubmit}
      >
        <header className="px-5 pb-4 pt-5 lg:px-0">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-tide">How&apos;s Your Day</p>
              <h1 className="mt-1 text-2xl font-semibold leading-tight tracking-normal">
                오늘 하루를 무리 없이 조율해볼게요.
              </h1>
            </div>
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-ink text-white shadow-sm">
              <Brain size={22} aria-hidden />
            </span>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill icon={<HeartPulse size={14} aria-hidden />} label="감정 비용" />
            <StatusPill icon={<Navigation size={14} aria-hidden />} label="동선 조율" />
            <StatusPill icon={<Clock3 size={14} aria-hidden />} label="시간 제약" />
          </div>
        </header>

        <section className="grid gap-4 px-5 lg:grid-cols-[380px_1fr] lg:px-0">
          <div className="grid gap-4 lg:self-start lg:sticky lg:top-6">
            <article className="rounded-2xl border border-ink/10 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink/60">
                <MessageCircle size={17} aria-hidden />
                오늘 해야 할 일을 말해줘
              </div>
              <textarea
                className="mt-3 min-h-32 w-full resize-none rounded-xl border border-ink/10 bg-[#f9faf7] p-3 text-[15px] leading-6 outline-none transition focus:border-tide focus:bg-white"
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                {samplePrompts.map((prompt) => (
                  <button
                    className="min-h-10 shrink-0 rounded-full border border-ink/10 bg-white px-3 text-sm font-semibold text-ink/70 shadow-sm transition hover:border-tide hover:text-tide"
                    key={prompt.label}
                    type="button"
                    onClick={() => setText(prompt.text)}
                  >
                    {prompt.label}
                  </button>
                ))}
              </div>
            </article>

            <article className="rounded-2xl border border-ink/10 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-ink/60">출발/도착</p>
                  <p className="mt-1 text-xs text-ink/46">{locationStatus}</p>
                </div>
                <button
                  className="min-h-10 shrink-0 rounded-full bg-[#eef5f1] px-3 text-sm font-semibold text-tide transition hover:bg-[#e2efe9]"
                  type="button"
                  onClick={handleUseCurrentLocation}
                >
                  현재 위치 사용
                </button>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {Object.keys(destinations).map((key) => (
                  <button
                    className={`min-h-10 rounded-full border px-3 text-sm font-semibold transition ${
                      selectedDestinationKey === key
                        ? "border-tide bg-tide text-white"
                        : "border-ink/10 bg-white text-ink/70"
                    }`}
                    key={key}
                    type="button"
                    onClick={() => handleDestinationSelect(key)}
                  >
                    {key}
                  </button>
                ))}
              </div>
              <p className="mt-3 truncate text-xs text-ink/48">
                {origin.label} → {destinations[selectedDestinationKey]?.label}
              </p>
            </article>

            {error ? (
              <p className="rounded-2xl border border-coral/40 bg-white p-3 text-sm text-coral">
                {error}
              </p>
            ) : null}

            <article className="rounded-2xl bg-ink p-4 text-white shadow-sm">
              <div className="flex items-center gap-2 text-sm font-semibold text-white/70">
                <Sparkles size={16} aria-hidden />
                planner가 보는 것
              </div>
              <p className="mt-2 text-sm leading-6 text-white/82">
                Kakao 장소와 Tmap 경로를 조합하고, 실패한 구간만 fallback으로
                보완해 감정 비용과 시간 tradeoff를 계산합니다.
              </p>
            </article>
          </div>

          <div className="grid gap-4">
            {plan ? <MobilePlanResult plan={plan} /> : <EmptyState />}
          </div>
        </section>

        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-ink/10 bg-white/92 px-5 py-3 shadow-[0_-8px_24px_rgba(23,33,29,0.08)] backdrop-blur lg:hidden">
          <button
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 font-semibold text-white transition active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-ink/45"
            type="submit"
            disabled={isLoading}
          >
            {isLoading ? "계획을 계산하는 중" : "하루 계획 만들기"}
            <ArrowRight size={18} aria-hidden />
          </button>
        </div>

        <div className="hidden px-5 lg:mt-4 lg:block lg:px-0">
          <button
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 font-semibold text-white transition hover:bg-tide disabled:cursor-not-allowed disabled:bg-ink/45"
            type="submit"
            disabled={isLoading}
          >
            {isLoading ? "계획을 계산하는 중" : "하루 계획 만들기"}
            <ArrowRight size={18} aria-hidden />
          </button>
        </div>
      </form>
    </main>
  );
}

function MobilePlanResult({ plan }: { plan: DailyPlan }) {
  const firstTradeoff = plan.tradeoffs[0];
  const usesKakaoPoi = plan.stops.some((stop) => stop.source_confidence === "kakao");
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);

  async function handleFeedback(liked: boolean) {
    setFeedbackStatus("피드백 저장 중");
    try {
      await sendRouteFeedback({
        route_id: plan.selected_route.id,
        liked,
        emotion_primary: plan.emotion.primary,
        provider: plan.selected_route.provider,
        reason: firstTradeoff?.reason ?? plan.explanation
      });
      setFeedbackStatus(liked ? "좋았던 route로 기억했어요" : "불편했던 route로 기억했어요");
    } catch {
      setFeedbackStatus("피드백 저장에 실패했어요");
    }
  }

  return (
    <>
      <section className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-ink/10">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-moss">추천 route</p>
            <h2 className="mt-1 break-words text-2xl font-semibold leading-tight">
              {routeDisplayName(plan.selected_route)}
            </h2>
          </div>
          <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-2xl bg-tide text-white">
            <span className="text-xs font-semibold text-white/75">comfort</span>
            <span className="text-2xl font-semibold">
              {plan.emotional_cost.comfort_score}
            </span>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-ink/68">{plan.explanation}</p>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <MiniStat label="이동" value={durationLabel(plan.selected_route)} />
          <MiniStat label="걷기" value={`${plan.selected_route.walking_minutes}분`} />
          <MiniStat label="출처" value={routeProviderLabel(plan.selected_route)} />
        </div>

        <div className="mt-3 rounded-2xl bg-[#f6f8f4] p-3 text-xs leading-5 text-ink/58">
          {routeReliabilityLabel(plan.selected_route, usesKakaoPoi)}
          {plan.selected_route.fallback_reason ? (
            <span className="mt-1 block text-ink/42">
              {plan.selected_route.fallback_reason}
            </span>
          ) : null}
        </div>

        {firstTradeoff ? (
          <div className="mt-4 rounded-2xl bg-[#f6f8f4] p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Zap className="text-coral" size={16} aria-hidden />
              핵심 tradeoff
            </div>
            <p className="mt-2 text-sm leading-6 text-ink/68">{firstTradeoff.reason}</p>
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            className="min-h-11 rounded-xl bg-[#eef5f1] px-3 text-sm font-semibold text-moss transition active:scale-[0.99]"
            type="button"
            onClick={() => handleFeedback(true)}
          >
            이 route 괜찮았어요
          </button>
          <button
            className="min-h-11 rounded-xl bg-[#fff0ec] px-3 text-sm font-semibold text-coral transition active:scale-[0.99]"
            type="button"
            onClick={() => handleFeedback(false)}
          >
            별로였어요
          </button>
        </div>
        {feedbackStatus ? (
          <p className="mt-2 text-center text-xs font-medium text-ink/48">
            {feedbackStatus}
          </p>
        ) : null}
      </section>

      <KakaoMapPreview map={plan.map_overlays} usesKakaoPoi={usesKakaoPoi} />

      <section className="grid gap-3">
        <SectionTitle icon={<HeartPulse size={18} aria-hidden />} title="감정 비용" />
        <EmotionalCostCard cost={plan.emotional_cost} />
      </section>

      {plan.recommendations.length > 0 ? (
        <section className="grid gap-3">
          <SectionTitle icon={<Sparkles size={18} aria-hidden />} title="추천 조정" />
          {plan.recommendations.map((item) => (
            <InfoCard key={`${item.kind}-${item.label}`}>{item.label}</InfoCard>
          ))}
        </section>
      ) : null}

      <section className="grid gap-3">
        <SectionTitle icon={<Clock3 size={18} aria-hidden />} title="타임라인" />
        <TimelineList plan={plan} />
      </section>

      <section className="grid gap-3 pb-8">
        <SectionTitle icon={<Navigation size={18} aria-hidden />} title="후보 route" />
        <RouteList routes={plan.routes} selectedRouteId={plan.selected_route.id} />
      </section>
    </>
  );
}

function EmptyState() {
  return (
    <section className="rounded-3xl bg-white p-5 text-center shadow-sm ring-1 ring-ink/10">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#eef5f1] text-tide">
        <MessageCircle size={26} aria-hidden />
      </div>
      <h2 className="mt-4 text-xl font-semibold">아직 계획이 없어요</h2>
      <p className="mt-2 text-sm leading-6 text-ink/62">
        해야 할 일과 지금 컨디션을 적으면 planner가 route, 감정 비용,
        tradeoff를 계산해줍니다.
      </p>
    </section>
  );
}

type KakaoStatus = "loading" | "ready" | "fallback";

declare global {
  interface Window {
    kakao?: any;
    __kakaoMapsPromise?: Promise<void>;
  }
}

function KakaoMapPreview({
  map,
  usesKakaoPoi
}: {
  map: MapViewModel;
  usesKakaoPoi: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<KakaoStatus>("loading");
  const [sdkError, setSdkError] = useState<string | null>(null);
  const kakaoJsKey = process.env.NEXT_PUBLIC_KAKAO_JS_KEY;

  useEffect(() => {
    let cancelled = false;
    const fallbackTimer = window.setTimeout(() => {
      if (!cancelled) {
        setSdkError("Kakao SDK 응답이 늦어 preview로 표시해요.");
        setStatus("fallback");
      }
    }, 4500);

    if (!kakaoJsKey) {
      window.clearTimeout(fallbackTimer);
      setSdkError("Kakao JavaScript 키가 없어 preview로 표시해요.");
      setStatus("fallback");
      return;
    }

    setStatus("loading");
    setSdkError(null);
    loadKakaoMaps(kakaoJsKey)
      .then(() => {
        if (cancelled || !containerRef.current || !window.kakao?.maps) {
          return;
        }

        window.clearTimeout(fallbackTimer);
        renderKakaoMap(containerRef.current, map);
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) {
          window.clearTimeout(fallbackTimer);
          setSdkError("Kakao SDK 인증 또는 도메인 설정을 확인해야 해요.");
          setStatus("fallback");
        }
      });

    return () => {
      cancelled = true;
      window.clearTimeout(fallbackTimer);
    };
  }, [kakaoJsKey, map]);

  if (status === "fallback") {
    return (
      <MapPreview
        map={map}
        providerLabel={sdkError ? "Kakao 연결 실패" : "Mock fallback"}
        statusMessage={sdkError}
        usesKakaoPoi={usesKakaoPoi}
      />
    );
  }

  return (
    <section className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-ink/10">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-moss">
            {status === "ready" ? "Kakao map" : "지도 연결 중"}
          </p>
          <h2 className="text-lg font-semibold">동선 미리보기</h2>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="rounded-full bg-[#eef5f1] px-2.5 py-1 text-xs font-semibold text-tide">
            {usesKakaoPoi ? "Kakao POI" : "Mock POI"}
          </span>
          <MapPinned className="text-tide" size={22} aria-hidden />
        </div>
      </div>
      <div ref={containerRef} className="h-60 w-full bg-[#edf2ee]" />
    </section>
  );
}

function MapPreview({
  map,
  providerLabel = "mock map",
  statusMessage,
  usesKakaoPoi = false
}: {
  map: MapViewModel;
  providerLabel?: string;
  statusMessage?: string | null;
  usesKakaoPoi?: boolean;
}) {
  const projected = useMemo(() => createProjector(map), [map]);

  return (
    <section className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-ink/10">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-moss">{providerLabel}</p>
          <h2 className="text-lg font-semibold">동선 미리보기</h2>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="rounded-full bg-[#eef5f1] px-2.5 py-1 text-xs font-semibold text-tide">
            {usesKakaoPoi ? "Kakao POI" : "Mock POI"}
          </span>
          <MapPinned className="text-tide" size={22} aria-hidden />
        </div>
      </div>
      {statusMessage ? (
        <p className="mx-4 mb-3 rounded-2xl bg-[#fff7ed] px-3 py-2 text-xs leading-5 text-coral">
          {statusMessage}
        </p>
      ) : null}
      <div className="relative h-60 bg-[#edf2ee]">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(23,33,29,0.05)_1px,transparent_1px),linear-gradient(rgba(23,33,29,0.05)_1px,transparent_1px)] bg-[size:34px_34px]" />
        <svg
          className="absolute inset-0 h-full w-full"
          role="img"
          aria-label="planner route preview"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {map.emotion_zones.map((zone) => {
            const point = projected(zone.center);
            return (
              <circle
                cx={point.x}
                cy={point.y}
                fill="rgba(217,111,93,0.24)"
                key={zone.id}
                r="9"
                stroke="rgba(217,111,93,0.75)"
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
                stroke={routeStroke(polyline.emotion_level, polyline.selected)}
                strokeDasharray={polyline.selected ? "0" : "3 3"}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={polyline.selected ? "4" : "2"}
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
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white shadow-sm">
                {marker.badge}
              </span>
              <span className="max-w-20 truncate rounded-md bg-white/95 px-2 py-1 text-xs font-medium shadow-sm">
                {marker.label}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function EmotionalCostCard({ cost }: { cost: EmotionCost }) {
  const rows = [
    ["피로", cost.fatigue_cost],
    ["걷기", cost.walking_cost],
    ["혼잡", cost.crowd_cost],
    ["환승", cost.transfer_cost],
    ["시간 압박", cost.time_pressure_cost],
    ["익숙함 보너스", -cost.familiarity_bonus],
    ["회복 보너스", -cost.recovery_bonus]
  ] as const;

  return (
    <article className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-ink/10">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-ink/60">total emotional cost</span>
        <span className="rounded-full bg-[#eef5f1] px-3 py-1 text-sm font-semibold text-tide">
          {cost.total_emotional_cost}
        </span>
      </div>
      <div className="mt-4 grid gap-3">
        {rows.map(([label, value]) => (
          <CostRow key={label} label={label} value={value} />
        ))}
      </div>
    </article>
  );
}

function CostRow({ label, value }: { label: string; value: number }) {
  const isBonus = value < 0;
  const width = Math.min(100, Math.abs(value) * 4);

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className={isBonus ? "text-moss" : "text-coral"}>
          {isBonus ? value : `+${value}`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[#edf2ee]">
        <div
          className={isBonus ? "h-full bg-moss" : "h-full bg-coral"}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function TimelineList({ plan }: { plan: DailyPlan }) {
  return (
    <ol className="grid gap-2">
      {plan.estimated_timeline.map((item) => (
        <li
          className="grid grid-cols-[58px_1fr] gap-3 rounded-2xl bg-white p-3 shadow-sm ring-1 ring-ink/10"
          key={`${item.time}-${item.label}`}
        >
          <span className="rounded-xl bg-[#eef5f1] px-2 py-2 text-center text-sm font-semibold text-tide">
            {item.time}
          </span>
          <span className="min-w-0 text-sm leading-6 text-ink/72">
            <span className="block text-xs font-semibold uppercase tracking-[0.1em] text-ink/38">
              {item.type}
            </span>
            {item.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

function RouteList({
  routes,
  selectedRouteId
}: {
  routes: RouteCandidate[];
  selectedRouteId: string;
}) {
  return (
    <div className="grid gap-2">
      {routes.map((route) => {
        const selected = route.id === selectedRouteId;

        return (
          <article
            className={`rounded-2xl p-3 shadow-sm ring-1 ${
              selected ? "bg-[#eef7f8] ring-tide/35" : "bg-white ring-ink/10"
            }`}
            key={route.id}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-sm font-semibold">
                {routeDisplayName(route)}
              </span>
              <div className="flex shrink-0 items-center gap-1">
                <span className="rounded-full bg-[#eef5f1] px-2 py-1 text-xs font-semibold text-tide">
                  {routeProviderLabel(route)}
                </span>
                {selected ? (
                  <span className="rounded-full bg-tide px-2 py-1 text-xs font-semibold text-white">
                    선택됨
                  </span>
                ) : null}
              </div>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-ink/62">
              <span>{durationLabel(route)}</span>
              <span>걷기 {route.walking_minutes}분</span>
              <span>{distanceLabel(route.distance_meters)}</span>
            </div>
            {route.fallback_reason ? (
              <p className="mt-2 text-xs leading-5 text-ink/42">{route.fallback_reason}</p>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function StatusPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex min-h-8 items-center gap-1.5 rounded-full bg-white px-3 text-sm font-semibold text-ink/64 shadow-sm ring-1 ring-ink/8">
      {icon}
      {label}
    </span>
  );
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 px-1 text-sm font-semibold text-ink/68">
      {icon}
      {title}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-[#f6f8f4] p-3">
      <p className="text-xs font-semibold text-ink/42">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold">{value}</p>
    </div>
  );
}

function InfoCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-2xl bg-white p-3 text-sm leading-6 text-ink/70 shadow-sm ring-1 ring-ink/10">
      <CheckCircle2 className="mt-0.5 shrink-0 text-moss" size={17} aria-hidden />
      <span>{children}</span>
    </div>
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

function loadKakaoMaps(kakaoJsKey: string) {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Kakao Maps can only load in the browser."));
  }

  if (window.kakao?.maps) {
    return new Promise<void>((resolve) => window.kakao.maps.load(resolve));
  }

  if (window.__kakaoMapsPromise) {
    return window.__kakaoMapsPromise;
  }

  window.__kakaoMapsPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      "script[data-kakao-maps-sdk='true']"
    );

    const handleLoad = () => {
      if (!window.kakao?.maps) {
        reject(new Error("Kakao Maps SDK did not expose window.kakao.maps."));
        return;
      }
      window.kakao.maps.load(resolve);
    };

    if (existingScript) {
      existingScript.addEventListener("load", handleLoad, { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Kakao Maps SDK failed.")), {
        once: true
      });
      return;
    }

    const script = document.createElement("script");
    script.async = true;
    script.dataset.kakaoMapsSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(
      kakaoJsKey
    )}&autoload=false`;
    script.onload = handleLoad;
    script.onerror = () => reject(new Error("Kakao Maps SDK failed."));
    document.head.appendChild(script);
  });

  return window.__kakaoMapsPromise;
}

function renderKakaoMap(container: HTMLDivElement, map: MapViewModel) {
  const kakao = window.kakao;
  container.innerHTML = "";

  const center = new kakao.maps.LatLng(map.center.lat, map.center.lng);
  const kakaoMap = new kakao.maps.Map(container, {
    center,
    level: 4
  });
  const bounds = new kakao.maps.LatLngBounds();

  map.markers.forEach((marker) => {
    const position = new kakao.maps.LatLng(marker.lat, marker.lng);
    bounds.extend(position);
    const kakaoMarker = new kakao.maps.Marker({
      map: kakaoMap,
      position,
      title: marker.label
    });
    const infoWindow = new kakao.maps.InfoWindow({
      content: `<div style="padding:6px 8px;font-size:12px;white-space:nowrap;">${escapeHtml(
        marker.badge
      )}. ${escapeHtml(marker.label)}</div>`
    });

    kakao.maps.event.addListener(kakaoMarker, "click", () => {
      infoWindow.open(kakaoMap, kakaoMarker);
    });
  });

  map.polylines.forEach((polyline) => {
    const path = polyline.points.map((point) => {
      const position = new kakao.maps.LatLng(point.lat, point.lng);
      bounds.extend(position);
      return position;
    });

    new kakao.maps.Polyline({
      map: kakaoMap,
      path,
      strokeWeight: polyline.selected ? 6 : 3,
      strokeColor: routeStroke(polyline.emotion_level, polyline.selected),
      strokeOpacity: polyline.selected ? 0.95 : 0.62,
      strokeStyle: polyline.selected ? "solid" : "shortdash"
    });
  });

  map.emotion_zones.forEach((zone) => {
    new kakao.maps.Circle({
      map: kakaoMap,
      center: new kakao.maps.LatLng(zone.center.lat, zone.center.lng),
      radius: zone.radius_meters,
      strokeWeight: 1,
      strokeColor: "#d96f5d",
      strokeOpacity: 0.65,
      fillColor: "#d96f5d",
      fillOpacity: 0.18
    });
  });

  if (map.markers.length > 0 || map.polylines.length > 0) {
    kakaoMap.setBounds(bounds);
  }
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function routeStroke(emotionLevel: string, selected: boolean) {
  if (selected) {
    return "#4f8a9b";
  }
  if (emotionLevel === "stressful") {
    return "#d96f5d";
  }
  return "#7e9375";
}

function routeLabel(routeId: string) {
  return routeId
    .replace("route-", "")
    .split("-")
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

function routeDisplayName(route: RouteCandidate) {
  if (route.provider === "tmap-pedestrian") {
    return "Tmap 도보 경로";
  }
  if (route.provider === "tmap-transit") {
    return "Tmap 대중교통 경로";
  }
  if (route.provider === "tmap-mixed") {
    return "Tmap 혼합 경로";
  }
  return routeLabel(route.id);
}

function translateCrowd(level: string) {
  if (level === "low") {
    return "낮음";
  }
  if (level === "high") {
    return "높음";
  }
  return "보통";
}

function routeProviderLabel(route: RouteCandidate) {
  if (route.provider === "tmap-pedestrian") {
    return "Tmap 도보";
  }
  if (route.provider === "tmap-transit") {
    return "Tmap 대중교통";
  }
  if (route.provider === "tmap-mixed") {
    return "Tmap 혼합";
  }
  return "추정 fallback";
}

function routeReliabilityLabel(route: RouteCandidate, usesKakaoPoi: boolean) {
  const poiLabel = usesKakaoPoi ? "실제 장소" : "demo 장소";
  const routeLabelText =
    route.provider === "tmap-mixed"
      ? "일부 추정 경로"
      : route.provider.startsWith("tmap")
        ? "실제 경로"
        : "추정 경로";
  return `${poiLabel} + ${routeLabelText}`;
}

function durationLabel(route: RouteCandidate) {
  if (route.real_duration_minutes) {
    return `${route.real_duration_minutes}분`;
  }
  return `${route.estimated_duration_minutes ?? route.estimated_minutes}분 추정`;
}

function distanceLabel(distanceMeters: number | null) {
  if (!distanceMeters) {
    return "거리 추정";
  }
  if (distanceMeters >= 1000) {
    return `${(distanceMeters / 1000).toFixed(1)}km`;
  }
  return `${distanceMeters}m`;
}
