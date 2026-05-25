"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Brain, Clock, MapPinned, Route } from "lucide-react";
import { requestDailyPlan, type DailyPlan } from "@/lib/api";

const starterText =
  "I need to print my report, visit a clinic, and get home by 5. I am tired today.";

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
      <section className="mx-auto grid min-h-screen w-full max-w-7xl grid-cols-1 gap-8 px-5 py-6 md:grid-cols-[420px_1fr] md:px-8">
        <aside className="flex flex-col gap-5">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-moss">
              How's Your Day
            </p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight md:text-5xl">
              Plan the day around what you can actually handle.
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

          {error ? (
            <p className="rounded-lg border border-coral/40 bg-white p-3 text-sm text-coral">
              {error}
            </p>
          ) : null}
        </aside>

        <section className="grid min-h-[640px] grid-rows-[260px_1fr] gap-5">
          <div className="relative overflow-hidden rounded-lg bg-ink text-white">
            <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(79,138,155,0.85),rgba(111,139,99,0.86)),url('https://images.unsplash.com/photo-1518005020951-eccb494ad742?auto=format&fit=crop&w=1600&q=80')] bg-cover bg-center" />
            <div className="relative flex h-full flex-col justify-between p-5">
              <div className="inline-flex w-fit items-center gap-2 rounded-full bg-white/16 px-3 py-1 text-sm backdrop-blur">
                <MapPinned size={16} aria-hidden />
                Agent harness preview
              </div>
              <div>
                <p className="max-w-2xl text-2xl font-semibold leading-snug">
                  The map is the interface. The harness is the product.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard
              icon={<Brain size={20} aria-hidden />}
              label="Emotion"
              value={plan?.emotion.primary ?? "Waiting"}
              detail={plan?.emotion.recovery_need ?? "Run the agent"}
            />
            <MetricCard
              icon={<Route size={20} aria-hidden />}
              label="Comfort"
              value={plan ? `${plan.score.comfort_score}` : "--"}
              detail={plan?.score.reasons[0] ?? "Scored after routing"}
            />
            <MetricCard
              icon={<Clock size={20} aria-hidden />}
              label="Constraint"
              value={plan?.constraints.deadline ?? "--"}
              detail={plan?.constraints.destination ?? "No deadline yet"}
            />
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
            <h2 className="text-xl font-semibold">Daily flow</h2>
            {plan ? (
              <ol className="mt-4 grid gap-3">
                {plan.stops.map((stop, index) => (
                  <li
                    className="grid grid-cols-[32px_1fr] gap-3 rounded-lg bg-field p-3"
                    key={stop.id}
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white">
                      {index + 1}
                    </span>
                    <span>
                      <span className="block font-semibold">{stop.name}</span>
                      <span className="block text-sm text-ink/65">
                        {stop.category} · {stop.landmark_type}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-4 text-ink/65">
                Submit the prompt to see how tasks, emotion, POIs, routes, and
                scoring connect.
              </p>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail
}: {
  icon: React.ReactNode;
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

