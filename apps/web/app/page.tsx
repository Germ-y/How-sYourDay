"use client";

import { FormEvent, PointerEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Brain,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Coffee,
  Building2,
  Home,
  HeartPulse,
  Leaf,
  LogOut,
  Mail,
  MapPin,
  MapPinned,
  MessageCircle,
  Navigation,
  Plus,
  RotateCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UserRound,
  Zap,
  type LucideIcon
} from "lucide-react";
import {
  extractRouteLocations,
  fetchPreferencePoints,
  geocodeLocation,
  requestDailyPlan,
  sendRouteFeedback,
  searchLocations,
  type Coordinate,
  type DailyPlan,
  type EmotionCost,
  type Location,
  type LocationCandidate,
  type MapViewModel,
  type PoiCandidate,
  type RouteCandidate
} from "@/lib/api";

const starterText = "";
const QUICK_DESTINATIONS = ["집", "학교", "회사"];
const LAST_ORIGIN_KEY = "hows-your-day.origin-text.v1";
const LAST_DESTINATION_KEY = "hows-your-day.destination-text.v1";
const SAVED_PLACES_KEY = "hows-your-day.saved-places.v1";
const PROFILE_PLACEHOLDER = {
  nickname: "균이",
  email: "로그인 후 표시"
};
const MOOD_PRESETS = [
  {
    label: "피곤",
    sentence: "피로도 높음. 보행 시간과 혼잡도를 낮게 우선."
  },
  {
    label: "바쁨",
    sentence: "시간 제약 높음. 우회보다 도착 시간을 우선."
  },
  {
    label: "여유",
    sentence: "시간 여유 있음. 편안한 장소 경유 허용."
  },
  {
    label: "휴식",
    sentence: "휴식 필요. 조용한 카페나 공원 후보 반영."
  }
];
const POI_PREFERENCES = [
  {
    id: "quiet-cafe",
    name: "학림다방",
    kind: "카페",
    detail: "대학로 인근의 조용한 회복 후보",
    icon: Coffee,
    tags: ["회복", "실내"],
    lat: 37.5817,
    lng: 127.0011,
    source: "예시"
  },
  {
    id: "small-park",
    name: "마로니에공원",
    kind: "공원",
    detail: "짧게 환기할 수 있는 외부 장소",
    icon: Leaf,
    tags: ["산책", "환기"],
    lat: 37.5803,
    lng: 127.0023,
    source: "예시"
  },
  {
    id: "campus-street",
    name: "성균관대 정문 앞",
    kind: "학교 주변",
    detail: "익숙하지만 시간대에 따라 혼잡한 지점",
    icon: Building2,
    tags: ["익숙함", "혼잡"],
    lat: 37.5882,
    lng: 126.9936,
    source: "예시"
  },
  {
    id: "station-area",
    name: "혜화역 4번 출구",
    kind: "역세권",
    detail: "빠르지만 소음과 유동 인구가 큰 지점",
    icon: Navigation,
    tags: ["빠름", "혼잡"],
    lat: 37.5821,
    lng: 127.0018,
    source: "예시"
  }
];

type PreferenceVote = "like" | "dislike";
type PreferenceSignal = PreferenceVote | "similar-like" | "similar-dislike" | null;
type AppView = "planner" | "taste" | "profile";
type SavedPlaceKind = "home" | "school" | "work" | "favorite";
type SavedPlaceEntry = {
  id: string;
  name: string;
  address: string;
  kind: SavedPlaceKind;
  updatedAt: string;
};
type PreferencePoint = {
  id: string;
  name: string;
  kind: string;
  detail: string;
  icon: LucideIcon;
  tags: string[];
  lat: number;
  lng: number;
  source: string;
};
const SWIPE_THRESHOLD = 86;

export default function HomePage() {
  const [text, setText] = useState(starterText);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [originText, setOriginText] = useState("");
  const [destinationText, setDestinationText] = useState("");
  const [originEdited, setOriginEdited] = useState(false);
  const [destinationEdited, setDestinationEdited] = useState(false);
  const [currentLocation, setCurrentLocation] = useState<Location | null>(null);
  const [activeMood, setActiveMood] = useState(MOOD_PRESETS[0].label);
  const [poiPreferenceIndex, setPoiPreferenceIndex] = useState(0);
  const [poiVotes, setPoiVotes] = useState<Record<string, PreferenceVote>>({});
  const [nearbyPreferencePoints, setNearbyPreferencePoints] = useState<
    PreferencePoint[]
  >([]);
  const [isPreferenceLoading, setIsPreferenceLoading] = useState(false);
  const [preferenceStatus, setPreferenceStatus] = useState(
    "내 주변 장소 준비"
  );
  const [activeView, setActiveView] = useState<AppView>("planner");
  const [locationStatus, setLocationStatus] =
    useState("주소 또는 장소명 입력 필요");
  const [savedPlaces, setSavedPlaces] = useState<SavedPlaceEntry[]>([]);
  const [savedPlaceDraft, setSavedPlaceDraft] = useState({
    name: "",
    address: "",
    kind: "favorite" as SavedPlaceKind
  });
  const [savedPlaceNotice, setSavedPlaceNotice] = useState("");
  const [originCandidates, setOriginCandidates] = useState<LocationCandidate[]>([]);
  const [destinationCandidates, setDestinationCandidates] = useState<
    LocationCandidate[]
  >([]);
  const [selectedOriginLocation, setSelectedOriginLocation] =
    useState<Location | null>(null);
  const [selectedDestinationLocation, setSelectedDestinationLocation] =
    useState<Location | null>(null);
  const [activeLocationField, setActiveLocationField] = useState<
    "origin" | "destination" | null
  >(null);
  const [locationSearchLoading, setLocationSearchLoading] = useState<
    "origin" | "destination" | null
  >(null);

  useEffect(() => {
    const storedOriginText = window.localStorage.getItem(LAST_ORIGIN_KEY);
    const storedDestinationText = window.localStorage.getItem(LAST_DESTINATION_KEY);
    const storedSavedPlaces = window.localStorage.getItem(SAVED_PLACES_KEY);
    if (storedOriginText) {
      setOriginText(storedOriginText);
    }
    if (storedDestinationText) {
      setDestinationText(storedDestinationText);
    }
    if (storedSavedPlaces) {
      try {
        const parsed = JSON.parse(storedSavedPlaces);
        if (Array.isArray(parsed)) {
          setSavedPlaces(parsed.filter(isSavedPlaceEntry));
        }
      } catch {
        window.localStorage.removeItem(SAVED_PLACES_KEY);
      }
    }
  }, []);

  useEffect(() => {
    const trimmed = text.trim();
    if (!trimmed) {
      setLocationStatus("주소 또는 장소명 입력 필요");
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const hints = await extractRouteLocations(trimmed);
        if (cancelled) {
          return;
        }
        let changed = false;

        if (hints.origin_text && !originEdited && originText !== hints.origin_text) {
          setOriginText(hints.origin_text);
          changed = true;
        }
        if (
          hints.destination_text &&
          !destinationEdited &&
          destinationText !== hints.destination_text
        ) {
          setDestinationText(hints.destination_text);
          changed = true;
        }

        if (changed) {
          setLocationStatus(
            hints.source === "llm"
              ? "문장에서 경로 후보 추출"
              : "문장에서 경로 후보 감지"
          );
        } else if (!hints.origin_text && !hints.destination_text) {
          setLocationStatus("경로 후보 없음. 직접 입력 가능");
        }
      } catch {
        if (!cancelled) {
          setLocationStatus("자동 추출 실패. 직접 입력 가능");
        }
      }
    }, 450);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [text, originEdited, destinationEdited, originText, destinationText]);

  useEffect(() => {
    const query = originText.trim();
    if (!shouldSearchLocationInput(query)) {
      setOriginCandidates([]);
      setLocationSearchLoading((current) => (current === "origin" ? null : current));
      return;
    }

    let cancelled = false;
    setLocationSearchLoading("origin");
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchLocations(query, 5);
        if (!cancelled) {
          setOriginCandidates(result.candidates);
        }
      } catch {
        if (!cancelled) {
          setOriginCandidates([]);
        }
      } finally {
        if (!cancelled) {
          setLocationSearchLoading((current) =>
            current === "origin" ? null : current
          );
        }
      }
    }, 260);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [originText]);

  useEffect(() => {
    const query = destinationText.trim();
    if (!shouldSearchLocationInput(query)) {
      setDestinationCandidates([]);
      setLocationSearchLoading((current) =>
        current === "destination" ? null : current
      );
      return;
    }

    let cancelled = false;
    setLocationSearchLoading("destination");
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchLocations(query, 5);
        if (!cancelled) {
          setDestinationCandidates(result.candidates);
        }
      } catch {
        if (!cancelled) {
          setDestinationCandidates([]);
        }
      } finally {
        if (!cancelled) {
          setLocationSearchLoading((current) =>
            current === "destination" ? null : current
          );
        }
      }
    }, 260);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [destinationText]);

  function persistSavedPlaces(nextPlaces: SavedPlaceEntry[]) {
    setSavedPlaces(nextPlaces);
    window.localStorage.setItem(SAVED_PLACES_KEY, JSON.stringify(nextPlaces));
  }

  function handleSavedPlaceDraftChange(
    field: "name" | "address" | "kind",
    value: string
  ) {
    setSavedPlaceDraft((current) => ({
      ...current,
      [field]: field === "kind" ? (value as SavedPlaceKind) : value
    }));
  }

  function handleAddSavedPlace() {
    const name = savedPlaceDraft.name.trim();
    const address = savedPlaceDraft.address.trim();

    if (!name || !address) {
      setSavedPlaceNotice("장소 이름과 주소를 입력해야 합니다.");
      return;
    }

    savePlace({
      name,
      address,
      kind: savedPlaceDraft.kind
    });
    setSavedPlaceDraft({
      name: "",
      address: "",
      kind: "favorite"
    });
  }

  function handleSaveCurrentPlace(role: "origin" | "destination") {
    const address = role === "origin" ? originText.trim() : destinationText.trim();

    if (!address) {
      setSavedPlaceNotice(
        role === "origin"
          ? "먼저 출발지를 입력해야 합니다."
          : "먼저 도착지를 입력해야 합니다."
      );
      return;
    }

    savePlace({
      name: role === "origin" ? "기본 출발지" : "최근 도착지",
      address,
      kind: role === "origin" ? "favorite" : guessSavedPlaceKind(address)
    });
  }

  function savePlace(place: Omit<SavedPlaceEntry, "id" | "updatedAt">) {
    const normalizedAddress = normalizePlaceText(place.address);
    const nextPlace: SavedPlaceEntry = {
      ...place,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      updatedAt: new Date().toISOString()
    };
    const withoutDuplicate = savedPlaces.filter(
      (savedPlace) => normalizePlaceText(savedPlace.address) !== normalizedAddress
    );
    persistSavedPlaces([nextPlace, ...withoutDuplicate].slice(0, 12));
    setSavedPlaceNotice(`${place.name} 저장 완료`);
  }

  function handleRemoveSavedPlace(id: string) {
    const removed = savedPlaces.find((place) => place.id === id);
    persistSavedPlaces(savedPlaces.filter((place) => place.id !== id));
    setSavedPlaceNotice(
      removed ? `${removed.name} 삭제 완료` : "저장 장소 삭제 완료"
    );
  }

  function handleUseSavedPlace(place: SavedPlaceEntry, target: "origin" | "destination") {
    if (target === "origin") {
      setOriginText(place.address);
      setOriginEdited(true);
      setSelectedOriginLocation(null);
    } else {
      setDestinationText(place.address);
      setDestinationEdited(true);
      setSelectedDestinationLocation(null);
    }
    setLocationStatus(`${place.name}을 ${target === "origin" ? "출발지" : "도착지"}로 설정`);
    setActiveView("planner");
  }

  function handleLocationCandidateSelect(
    field: "origin" | "destination",
    candidate: LocationCandidate
  ) {
    const location = {
      label: candidate.label,
      lat: candidate.lat,
      lng: candidate.lng
    };

    if (field === "origin") {
      setOriginText(candidate.label);
      setOriginEdited(true);
      setSelectedOriginLocation(location);
      setOriginCandidates([]);
    } else {
      setDestinationText(candidate.label);
      setDestinationEdited(true);
      setSelectedDestinationLocation(location);
      setDestinationCandidates([]);
    }

    setActiveLocationField(null);
    setError(null);
    setLocationStatus(`${candidate.label} 선택됨`);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);

    if (!originText.trim() || !destinationText.trim()) {
      setIsLoading(false);
      setError("출발지와 도착지를 입력해야 합니다.");
      return;
    }

    try {
      setLocationStatus("주소를 좌표로 확인하는 중");
      const originResult = await resolveLocationInput(
        originText,
        currentLocation,
        selectedOriginLocation
      );
      const destinationResult = await resolveLocationInput(
        destinationText,
        currentLocation,
        selectedDestinationLocation
      );
      const planningText = buildPlanningText(
        text,
        activeMood,
        poiVotes,
        preferencePoints
      );
      const result = await requestDailyPlan(
        planningText,
        originResult.location,
        destinationResult.location
      );
      window.localStorage.setItem(LAST_ORIGIN_KEY, originText.trim());
      window.localStorage.setItem(LAST_DESTINATION_KEY, destinationText.trim());
      setLocationStatus(
        `${originResult.location.label} → ${destinationResult.location.label}`
      );
      setPlan(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "경로 생성 실패");
    } finally {
      setIsLoading(false);
    }
  }

  function handleUseCurrentLocation() {
    if (!navigator.geolocation) {
      setLocationStatus("현재 위치 사용 불가. 주소 입력 필요");
      return;
    }

    setLocationStatus("현재 위치 확인 중");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location = {
          label: "현재 위치",
          lat: position.coords.latitude,
          lng: position.coords.longitude
        };
        setCurrentLocation(location);
        setOriginText("현재 위치");
        setOriginEdited(true);
        setSelectedOriginLocation(location);
        setOriginCandidates([]);
        setLocationStatus("현재 위치 사용 중");
      },
      () => {
        setLocationStatus("위치 권한 없음. 주소 입력 필요");
      },
      {
        enableHighAccuracy: true,
        maximumAge: 60_000,
        timeout: 8_000
      }
    );
  }

  function handleViewChange(view: AppView) {
    setActiveView(view);
    if (
      view === "taste" &&
      nearbyPreferencePoints.length === 0 &&
      !isPreferenceLoading
    ) {
      loadNearbyPreferencePoints();
    }
  }

  function loadNearbyPreferencePoints() {
    if (!navigator.geolocation) {
      setPreferenceStatus("위치 사용 불가");
      return;
    }

    setIsPreferenceLoading(true);
    setPreferenceStatus("위치 확인 중");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const location = {
          label: "현재 위치",
          lat: position.coords.latitude,
          lng: position.coords.longitude
        };
        setCurrentLocation(location);
        setPreferenceStatus("장소 불러오는 중");

        try {
          const result = await fetchPreferencePoints(location);
          setNearbyPreferencePoints(
            result.points.map((candidate) => preferencePointFromCandidate(candidate))
          );
          setPreferenceStatus(
            result.points.length > 0
              ? `내 주변 실제 장소 ${result.points.length}개`
              : "예시 장소 표시"
          );
          setPoiPreferenceIndex(0);
        } catch {
          setPreferenceStatus("예시 장소 표시");
        } finally {
          setIsPreferenceLoading(false);
        }
      },
      () => {
        setIsPreferenceLoading(false);
        setPreferenceStatus("위치 권한 필요");
      },
      {
        enableHighAccuracy: true,
        maximumAge: 60_000,
        timeout: 8_000
      }
    );
  }

  function handleDestinationSelect(key: string) {
    setDestinationText(key);
    setDestinationEdited(true);
    setSelectedDestinationLocation(null);
    setError(null);
  }

  function handleMoodSelect(label: string) {
    setActiveMood(label);
  }

  function handlePoiVote(id: string, vote: PreferenceVote) {
    setPoiVotes((current) => ({
      ...current,
      [id]: vote
    }));
    setPoiPreferenceIndex(
      (current) => (current + 1) % Math.max(1, preferencePoints.length)
    );
  }

  function handlePoiSkip() {
    setPoiPreferenceIndex(
      (current) => (current + 1) % Math.max(1, preferencePoints.length)
    );
  }

  function handlePoiReset() {
    setPoiVotes({});
    setPoiPreferenceIndex(0);
  }

  const likedCount = Object.values(poiVotes).filter((vote) => vote === "like").length;
  const dislikedCount = Object.values(poiVotes).filter(
    (vote) => vote === "dislike"
  ).length;
  const preferencePoints = useMemo(
    () =>
      nearbyPreferencePoints.length > 0
        ? nearbyPreferencePoints
        : buildPreferencePoints(plan),
    [nearbyPreferencePoints, plan]
  );
  useEffect(() => {
    if (poiPreferenceIndex >= preferencePoints.length) {
      setPoiPreferenceIndex(0);
    }
  }, [poiPreferenceIndex, preferencePoints.length]);
  const primaryLabel = isLoading ? "경로 계산 중" : "경로 추천";

  return (
    <main className="min-h-screen bg-[#fff9ed] text-ink">
      <form
        className="mx-auto flex min-h-screen w-full max-w-md flex-col pb-24 lg:max-w-6xl lg:px-6"
        onSubmit={handleSubmit}
      >
        <ServiceTopBar activeView={activeView} onChange={handleViewChange} />
        {activeView === "planner" ? (
          <>
        <header className="px-5 pb-5 pt-5 lg:px-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-tide">경로 추천</p>
              <h1 className="mt-1 pr-2 text-[30px] font-semibold leading-tight tracking-normal [word-break:keep-all] sm:text-3xl">
                어디로 이동하나요
              </h1>
            </div>
            <span className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-tide shadow-sm ring-1 ring-ink/8">
              <Brain size={22} aria-hidden />
            </span>
          </div>
        </header>

        <section className="grid gap-5 px-5 lg:grid-cols-[420px_1fr] lg:items-start lg:px-0">
          <article className="overflow-hidden rounded-[28px] bg-white shadow-[0_18px_50px_rgba(23,26,24,0.07)] ring-1 ring-ink/8 lg:sticky lg:top-20">
            <div className="border-b border-ink/8 bg-[#fffdf8] px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-tide">이동 요청</p>
                  <p className="mt-1 text-xs font-medium text-ink/45">
                    문장에서 출발지와 도착지 추출
                  </p>
                </div>
                <span className="rounded-2xl bg-[#ddf3eb] px-3 py-1.5 text-xs font-semibold text-moss">
                  수정 가능
                </span>
              </div>
            </div>

            <div className="grid gap-5 p-5">
              <section>
                <ComposerTitle
                  icon={<MessageCircle size={17} aria-hidden />}
                  label="이동 요청"
                  support="일정, 장소, 시간 조건을 한 번에 입력"
                />
                <textarea
                  className="mt-3 min-h-28 w-full resize-none rounded-2xl border border-ink/10 bg-[#fffdf8] p-4 text-[15px] leading-6 outline-none transition placeholder:text-ink/35 focus:border-tide focus:bg-white"
                  placeholder="예: 성균관대학교에서 서울역까지, 18시 전 도착. 조용한 카페 경유 가능."
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                />
              </section>

              <div className="h-px bg-ink/8" />

              <section>
                <div className="flex items-start justify-between gap-3">
                  <ComposerTitle
                    icon={<Navigation size={17} aria-hidden />}
                    label="경로 확인"
                    support={`${locationStatus} · 직접 수정 가능`}
                  />
                  <button
                    className="min-h-9 shrink-0 rounded-xl bg-[#fde2ef] px-3 text-xs font-semibold text-tide transition hover:bg-[#fbd2e6] active:scale-[0.98]"
                    type="button"
                    onClick={handleUseCurrentLocation}
                  >
                    현재 위치
                  </button>
                </div>

                <div className="mt-3 rounded-2xl bg-[#fffdf8] p-3 ring-1 ring-ink/8">
                  <div className="grid grid-cols-[24px_1fr] gap-3">
                    <div className="flex flex-col items-center pt-3">
                      <span className="h-2.5 w-2.5 rounded-full bg-moss" />
                      <span className="my-1 h-12 w-px bg-ink/12" />
                      <span className="h-2.5 w-2.5 rounded-full bg-tide" />
                    </div>
                    <div className="grid gap-3">
                      <LocationSearchInput
                        active={activeLocationField === "origin"}
                        candidates={originCandidates}
                        id="origin"
                        isLoading={locationSearchLoading === "origin"}
                        label="출발지"
                        placeholder="예: 성균관대학교 서울캠퍼스"
                        value={originText}
                        onBlur={() => {
                          window.setTimeout(() => setActiveLocationField(null), 120);
                        }}
                        onChange={(value) => {
                          setOriginText(value);
                          setOriginEdited(true);
                          setSelectedOriginLocation(null);
                          setError(null);
                        }}
                        onFocus={() => setActiveLocationField("origin")}
                        onSelect={(candidate) =>
                          handleLocationCandidateSelect("origin", candidate)
                        }
                      />
                      <LocationSearchInput
                        active={activeLocationField === "destination"}
                        candidates={destinationCandidates}
                        id="destination"
                        isLoading={locationSearchLoading === "destination"}
                        label="도착지"
                        placeholder="예: 서울역, 집, 회사"
                        value={destinationText}
                        onBlur={() => {
                          window.setTimeout(() => setActiveLocationField(null), 120);
                        }}
                        onChange={(value) => {
                          setDestinationText(value);
                          setDestinationEdited(true);
                          setSelectedDestinationLocation(null);
                          setError(null);
                        }}
                        onFocus={() => setActiveLocationField("destination")}
                        onSelect={(candidate) =>
                          handleLocationCandidateSelect("destination", candidate)
                        }
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-2">
                  {QUICK_DESTINATIONS.map((key) => (
                    <button
                      className={`min-h-10 rounded-xl border px-3 text-sm font-semibold transition ${
                        normalizeLocationText(destinationText) === normalizeLocationText(key)
                          ? "border-tide bg-tide text-white shadow-sm"
                          : "border-ink/10 bg-white text-ink/62 hover:border-tide/45"
                      }`}
                      key={key}
                      type="button"
                      onClick={() => handleDestinationSelect(key)}
                    >
                      {key}
                    </button>
                  ))}
                </div>
              </section>

              <div className="h-px bg-ink/8" />

              <section>
                <ComposerTitle
                  icon={<HeartPulse size={17} aria-hidden />}
                  label="컨디션"
                  support="추천 기준 선택"
                />
                <div className="mt-3 grid grid-cols-4 gap-2">
                  {MOOD_PRESETS.map((mood) => {
                    const selected = activeMood === mood.label;
                    return (
                      <button
                        className={`flex min-h-10 items-center justify-center gap-1.5 rounded-xl border px-2 text-sm font-semibold transition active:scale-[0.98] ${
                          selected
                            ? "border-tide bg-[#fde2ef] text-tide shadow-sm"
                            : "border-ink/10 bg-[#fffdf8] text-ink/62 hover:border-tide/45"
                        }`}
                        key={mood.label}
                        type="button"
                        onClick={() => handleMoodSelect(mood.label)}
                      >
                        {selected ? <CheckCircle2 size={14} aria-hidden /> : null}
                        {mood.label}
                      </button>
                    );
                  })}
                </div>
              </section>

              {error ? (
                <p className="rounded-2xl border border-coral/40 bg-[#fff7fb] p-3 text-sm text-coral">
                  {error}
                </p>
              ) : null}
            </div>
          </article>

          <div className="grid gap-4 lg:self-start">
            {plan ? (
              <MobilePlanResult plan={plan} />
            ) : (
              <>
                <PlanPreview
                  activeMood={activeMood}
                  destinationText={destinationText}
                  dislikedCount={dislikedCount}
                  likedCount={likedCount}
                  originText={originText}
                />
                <button
                  className="hidden min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-ink px-4 font-semibold text-white shadow-[0_12px_30px_rgba(23,26,24,0.14)] transition hover:bg-tide disabled:cursor-not-allowed disabled:bg-ink/45 lg:flex"
                  type="submit"
                  disabled={isLoading}
                >
                  {primaryLabel}
                  <ArrowRight size={18} aria-hidden />
                </button>
              </>
            )}
          </div>
        </section>

        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-ink/10 bg-white/92 px-5 py-3 shadow-[0_-8px_24px_rgba(23,26,24,0.08)] backdrop-blur lg:hidden">
          <button
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 font-semibold text-white transition active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-ink/45"
            type="submit"
            disabled={isLoading}
          >
            {primaryLabel}
            <ArrowRight size={18} aria-hidden />
          </button>
        </div>

          </>
        ) : activeView === "taste" ? (
          <TastePage
            activeIndex={poiPreferenceIndex}
            isLoading={isPreferenceLoading}
            points={preferencePoints}
            status={preferenceStatus}
            votes={poiVotes}
            onLoadNearby={loadNearbyPreferencePoints}
            onReset={handlePoiReset}
            onSkip={handlePoiSkip}
            onVote={handlePoiVote}
          />
        ) : (
          <ProfilePage
            activeMood={activeMood}
            destinationText={destinationText}
            originText={originText}
            plan={plan}
            savedPlaceDraft={savedPlaceDraft}
            savedPlaceNotice={savedPlaceNotice}
            savedPlaces={savedPlaces}
            onAddSavedPlace={handleAddSavedPlace}
            onRemoveSavedPlace={handleRemoveSavedPlace}
            onSavedPlaceDraftChange={handleSavedPlaceDraftChange}
            onSaveCurrentPlace={handleSaveCurrentPlace}
            onOpenPlanner={() => setActiveView("planner")}
            onUseSavedPlace={handleUseSavedPlace}
          />
        )}
      </form>
    </main>
  );
}

function ServiceTopBar({
  activeView,
  onChange
}: {
  activeView: AppView;
  onChange: (view: AppView) => void;
}) {
  const items = [
    { id: "planner" as const, label: "오늘", icon: CalendarDays },
    { id: "taste" as const, label: "취향", icon: MapPin },
    { id: "profile" as const, label: "마이", icon: UserRound }
  ];

  return (
    <nav className="sticky top-0 z-30 border-b border-ink/8 bg-[#fff9ed]/88 px-4 py-3 backdrop-blur sm:px-5 lg:px-0">
      <div className="flex items-center justify-between gap-2">
        <button
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          type="button"
          onClick={() => onChange("planner")}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white text-tide shadow-sm ring-1 ring-ink/8 sm:h-10 sm:w-10">
            <MapPinned size={18} aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold leading-4">How's Your Day</span>
            <span className="block truncate text-[11px] font-medium text-ink/45">
              감정 기반 경로 추천
            </span>
          </span>
        </button>

        <div className="grid shrink-0 grid-cols-3 rounded-2xl bg-white p-1 shadow-sm ring-1 ring-ink/8">
          {items.map((item) => {
            const selected = activeView === item.id;
            const Icon = item.icon;
            return (
              <button
                className={`flex h-10 min-w-[58px] items-center justify-center gap-1 rounded-xl px-2 text-xs font-semibold transition sm:min-w-[70px] sm:gap-1.5 sm:px-3 sm:text-sm ${
                  selected
                    ? "bg-[#fde2ef] text-tide"
                    : "text-ink/48 hover:bg-[#fff9ed] hover:text-ink/70"
                }`}
                key={item.id}
                type="button"
                onClick={() => onChange(item.id)}
              >
                <Icon className="shrink-0" size={15} aria-hidden />
                <span className="whitespace-nowrap leading-none">{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

function TastePage({
  activeIndex,
  isLoading,
  points,
  status,
  votes,
  onLoadNearby,
  onReset,
  onSkip,
  onVote
}: {
  activeIndex: number;
  isLoading: boolean;
  points: PreferencePoint[];
  status: string;
  votes: Record<string, PreferenceVote>;
  onLoadNearby: () => void;
  onReset: () => void;
  onSkip: () => void;
  onVote: (id: string, vote: PreferenceVote) => void;
}) {
  const likedCount = Object.values(votes).filter((vote) => vote === "like").length;
  const dislikedCount = Object.values(votes).filter((vote) => vote === "dislike").length;
  const affectedCount = points.filter(
    (point) => resolvePreferenceSignal(point, points, votes) !== null
  ).length;

  return (
    <section className="grid gap-5 px-5 py-5 lg:grid-cols-[420px_1fr] lg:items-start lg:px-0">
      <div className="grid gap-4 lg:sticky lg:top-20">
        <TasteIntroCard
          affectedCount={affectedCount}
          dislikedCount={dislikedCount}
          isLoading={isLoading}
          likedCount={likedCount}
          onLoadNearby={onLoadNearby}
          status={status}
        />
        <article className="hidden">
          <p className="text-xs font-semibold text-tide">장소 취향</p>
          <h1 className="mt-1 text-[28px] font-semibold leading-tight [word-break:keep-all]">
            실제 위치를 기준으로 학습
          </h1>
          <p className="mt-2 text-sm leading-6 text-ink/52 [word-break:keep-all]">
            추천 경로 주변의 장소 포인트를 선호/비선호로 분류합니다. 이후 경유 후보와 감정 비용 계산에 내부적으로 반영됩니다.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <MiniStat label="선호" value={`${likedCount}개`} />
            <MiniStat label="비선호" value={`${dislikedCount}개`} />
          </div>
        </article>

        <PreferenceDeck
          activeIndex={activeIndex}
          points={points}
          votes={votes}
          onReset={onReset}
          onSkip={onSkip}
          onVote={onVote}
        />
      </div>

      <PreferenceMap points={points} votes={votes} />
    </section>
  );
}

function TasteIntroCard({
  affectedCount,
  dislikedCount,
  isLoading,
  likedCount,
  onLoadNearby,
  status
}: {
  affectedCount: number;
  dislikedCount: number;
  isLoading: boolean;
  likedCount: number;
  onLoadNearby: () => void;
  status: string;
}) {
  return (
    <article className="order-2 rounded-[20px] bg-white p-4 shadow-[0_10px_28px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-tide">장소 취향</p>
              <h1 className="mt-1 text-xl font-semibold leading-tight [word-break:keep-all]">
                내 주변 취향
              </h1>
        </div>
        <button
          className="min-h-10 shrink-0 rounded-2xl bg-[#ddf3eb] px-3 text-xs font-semibold text-moss transition active:scale-[0.98] disabled:opacity-55"
          type="button"
          onClick={onLoadNearby}
          disabled={isLoading}
        >
          {isLoading ? "확인 중" : "내 주변"}
        </button>
      </div>
      <p className="mt-3 rounded-2xl bg-[#fffdf8] px-3 py-2 text-xs font-semibold text-ink/48 ring-1 ring-ink/7">
        {status}
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <MiniStat label="선호" value={`${likedCount}개`} />
        <MiniStat label="비선호" value={`${dislikedCount}개`} />
        <MiniStat label="반영" value={`${affectedCount}개`} />
      </div>
    </article>
  );
}

function ProfilePage({
  activeMood,
  destinationText,
  onAddSavedPlace,
  originText,
  onOpenPlanner,
  onRemoveSavedPlace,
  onSaveCurrentPlace,
  onSavedPlaceDraftChange,
  onUseSavedPlace,
  plan,
  savedPlaceDraft,
  savedPlaceNotice,
  savedPlaces
}: {
  activeMood: string;
  destinationText: string;
  originText: string;
  plan: DailyPlan | null;
  savedPlaceDraft: { name: string; address: string; kind: SavedPlaceKind };
  savedPlaceNotice: string;
  savedPlaces: SavedPlaceEntry[];
  onAddSavedPlace: () => void;
  onOpenPlanner: () => void;
  onRemoveSavedPlace: (id: string) => void;
  onSaveCurrentPlace: (role: "origin" | "destination") => void;
  onSavedPlaceDraftChange: (
    field: "name" | "address" | "kind",
    value: string
  ) => void;
  onUseSavedPlace: (
    place: SavedPlaceEntry,
    target: "origin" | "destination"
  ) => void;
}) {
  return (
    <section className="grid gap-4 px-5 py-5 lg:grid-cols-[360px_1fr] lg:px-0">
      <div className="grid gap-4 lg:self-start lg:sticky lg:top-20">
        <AccountCard />
        <article className="overflow-hidden rounded-3xl bg-white shadow-[0_18px_46px_rgba(23,26,24,0.06)] ring-1 ring-ink/8">
          <div className="bg-[#fde2ef] px-5 py-5">
            <p className="text-sm font-semibold text-tide">나의 이동 프로필</p>
            <h1 className="mt-2 text-[28px] font-semibold leading-tight [word-break:keep-all]">
              컨디션별 이동 기록
            </h1>
          </div>
          <div className="grid grid-cols-3 gap-2 p-4">
            <ProfileStat label="컨디션" value={activeMood} />
            <ProfileStat label="출발" value={originText || "미지정"} />
            <ProfileStat label="도착" value={destinationText || "미지정"} />
          </div>
        </article>

        <PlaceSaverCard
          destinationText={destinationText}
          draft={savedPlaceDraft}
          notice={savedPlaceNotice}
          originText={originText}
          onAdd={onAddSavedPlace}
          onDraftChange={onSavedPlaceDraftChange}
          onSaveCurrent={onSaveCurrentPlace}
        />
      </div>

      <div className="grid gap-4">
        <SavedPlacesPanel
          places={savedPlaces}
          onRemove={onRemoveSavedPlace}
          onUse={onUseSavedPlace}
        />

        <article className="rounded-2xl bg-white p-4 shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-tide">최근 추천</p>
              <h2 className="mt-1 text-xl font-semibold [word-break:keep-all]">
                {plan ? routeDisplayName(plan.selected_route) : "최근 추천 기록 없음"}
              </h2>
            </div>
            <button
              className="min-h-10 shrink-0 rounded-xl bg-ink px-3 text-sm font-semibold text-white transition active:scale-[0.98]"
              type="button"
              onClick={onOpenPlanner}
            >
              경로 만들기
            </button>
          </div>
          {plan ? (
            <div className="mt-4 grid grid-cols-3 gap-2">
              <MiniStat label="이동" value={durationLabel(plan.selected_route)} />
              <MiniStat label="걷기" value={`${plan.selected_route.walking_minutes}분`} />
              <MiniStat label="편안함" value={`${plan.emotional_cost.comfort_score}`} />
            </div>
          ) : (
            <p className="mt-4 rounded-2xl bg-[#fff9ed] p-4 text-sm leading-6 text-ink/58 [word-break:keep-all]">
              출발지와 도착지를 입력하면 최근 추천과 피드백이 이곳에 기록됩니다.
            </p>
          )}
        </article>
      </div>
    </section>
  );
}

function AccountCard() {
  return (
    <article className="overflow-hidden rounded-3xl bg-white shadow-[0_18px_46px_rgba(23,26,24,0.06)] ring-1 ring-ink/8">
      <div className="bg-[#ddf3eb] px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-moss shadow-sm ring-1 ring-ink/8">
              <UserRound size={23} aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-moss">내 정보</span>
              <span className="mt-1 block truncate text-2xl font-semibold leading-tight">
                {PROFILE_PLACEHOLDER.nickname}
              </span>
            </span>
          </div>
          <button
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/78 text-ink/48 transition active:scale-95"
            type="button"
            aria-label="로그아웃"
          >
            <LogOut size={17} aria-hidden />
          </button>
        </div>
      </div>

      <div className="grid gap-2 p-4">
        <AccountRow
          icon={<Mail size={16} aria-hidden />}
          label="이메일"
          value={PROFILE_PLACEHOLDER.email}
        />
      </div>
    </article>
  );
}

function AccountRow({
  icon,
  label,
  value
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-[#fffdf8] px-3 py-3 ring-1 ring-ink/7">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fde2ef] text-tide">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-xs font-semibold text-ink/42">{label}</span>
        <span className="block truncate text-sm font-semibold text-ink/76">{value}</span>
      </span>
    </div>
  );
}

function ProfileStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-2xl bg-[#fffdf8] px-3 py-3 text-center ring-1 ring-ink/7">
      <p className="truncate text-[11px] font-semibold text-ink/42">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink/74">{value}</p>
    </div>
  );
}

function PlaceSaverCard({
  destinationText,
  draft,
  notice,
  originText,
  onAdd,
  onDraftChange,
  onSaveCurrent
}: {
  destinationText: string;
  draft: { name: string; address: string; kind: SavedPlaceKind };
  notice: string;
  originText: string;
  onAdd: () => void;
  onDraftChange: (field: "name" | "address" | "kind", value: string) => void;
  onSaveCurrent: (role: "origin" | "destination") => void;
}) {
  return (
    <article className="rounded-2xl bg-white p-4 shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-tide">장소 저장</p>
          <h2 className="mt-1 text-xl font-semibold [word-break:keep-all]">
            자주 가는 곳
          </h2>
        </div>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#fde2ef] text-tide">
          <MapPinned size={19} aria-hidden />
        </span>
      </div>

      <div className="mt-4 grid gap-2">
        <label className="grid gap-1 text-xs font-semibold text-ink/48">
          이름
          <input
            className="min-h-11 rounded-xl border border-ink/10 bg-[#fffdf8] px-3 text-sm font-semibold text-ink outline-none transition placeholder:text-ink/32 focus:border-tide focus:bg-white"
            value={draft.name}
            onChange={(event) => onDraftChange("name", event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAdd();
              }
            }}
            placeholder="예: 집, 학교, 스터디 카페"
          />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-ink/48">
          주소 또는 장소명
          <input
            className="min-h-11 rounded-xl border border-ink/10 bg-[#fffdf8] px-3 text-sm font-semibold text-ink outline-none transition placeholder:text-ink/32 focus:border-tide focus:bg-white"
            value={draft.address}
            onChange={(event) => onDraftChange("address", event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAdd();
              }
            }}
            placeholder="예: 성균관대학교 서울캠퍼스"
          />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-ink/48">
          분류
          <select
            className="min-h-11 rounded-xl border border-ink/10 bg-[#fffdf8] px-3 text-sm font-semibold text-ink outline-none transition focus:border-tide focus:bg-white"
            value={draft.kind}
            onChange={(event) => onDraftChange("kind", event.target.value)}
          >
            <option value="favorite">자주 감</option>
            <option value="home">집</option>
            <option value="school">학교</option>
            <option value="work">회사</option>
          </select>
        </label>
      </div>

      <button
        className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 text-sm font-semibold text-white transition active:scale-[0.98]"
        type="button"
        onClick={onAdd}
      >
        <Plus size={17} aria-hidden />
        저장하기
      </button>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          className="min-h-10 rounded-xl bg-[#ddf3eb] px-3 text-sm font-semibold text-moss transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45"
          type="button"
          disabled={!originText.trim()}
          onClick={() => onSaveCurrent("origin")}
        >
          출발지 저장
        </button>
        <button
          className="min-h-10 rounded-xl bg-[#fde2ef] px-3 text-sm font-semibold text-tide transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45"
          type="button"
          disabled={!destinationText.trim()}
          onClick={() => onSaveCurrent("destination")}
        >
          도착지 저장
        </button>
      </div>

      {notice ? (
        <p className="mt-3 rounded-xl bg-[#fff9ed] px-3 py-2 text-xs font-semibold text-ink/55">
          {notice}
        </p>
      ) : null}
    </article>
  );
}

function SavedPlacesPanel({
  places,
  onRemove,
  onUse
}: {
  places: SavedPlaceEntry[];
  onRemove: (id: string) => void;
  onUse: (place: SavedPlaceEntry, target: "origin" | "destination") => void;
}) {
  return (
    <article className="rounded-2xl bg-white p-4 shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-tide">저장 장소</p>
          <h2 className="mt-1 text-xl font-semibold [word-break:keep-all]">
            이동할 때 바로 꺼내기
          </h2>
        </div>
        <span className="rounded-xl bg-[#fff9ed] px-2.5 py-1 text-xs font-semibold text-ink/55">
          {places.length}개
        </span>
      </div>

      {places.length ? (
        <div className="mt-4 grid gap-3">
          {places.map((place) => (
            <SavedPlace
              key={place.id}
              place={place}
              onRemove={onRemove}
              onUse={onUse}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl bg-[#fffdf8] p-5 text-center ring-1 ring-ink/7">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#ddf3eb] text-moss">
            <MapPin size={21} aria-hidden />
          </span>
          <p className="mt-3 text-base font-semibold">저장한 장소 없음</p>
          <p className="mt-1 text-sm leading-6 text-ink/48 [word-break:keep-all]">
            자주 가는 곳을 저장하면 다음 경로 입력이 훨씬 짧아집니다.
          </p>
        </div>
      )}
    </article>
  );
}

function SavedPlace({
  place,
  onRemove,
  onUse
}: {
  place: SavedPlaceEntry;
  onRemove: (id: string) => void;
  onUse: (place: SavedPlaceEntry, target: "origin" | "destination") => void;
}) {
  return (
    <div className="rounded-2xl bg-[#fffdf8] p-3 ring-1 ring-ink/7">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#ddf3eb] text-moss">
          {savedPlaceIcon(place.kind)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold text-tide">
            {savedPlaceKindLabel(place.kind)}
          </span>
          <span className="mt-0.5 block truncate text-base font-semibold text-ink">
            {place.name}
          </span>
          <span className="mt-1 block truncate text-sm text-ink/50">
            {place.address}
          </span>
        </span>
        <button
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-ink/38 transition hover:text-tide active:scale-95"
          type="button"
          aria-label={`${place.name} 삭제`}
          onClick={() => onRemove(place.id)}
        >
          <Trash2 size={16} aria-hidden />
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          className="min-h-10 rounded-xl bg-[#ddf3eb] px-3 text-sm font-semibold text-moss transition active:scale-[0.98]"
          type="button"
          onClick={() => onUse(place, "origin")}
        >
          출발지로
        </button>
        <button
          className="min-h-10 rounded-xl bg-[#fde2ef] px-3 text-sm font-semibold text-tide transition active:scale-[0.98]"
          type="button"
          onClick={() => onUse(place, "destination")}
        >
          도착지로
        </button>
      </div>
    </div>
  );
}

function LocationSearchInput({
  active,
  candidates,
  id,
  isLoading,
  label,
  onBlur,
  onChange,
  onFocus,
  onSelect,
  placeholder,
  value
}: {
  active: boolean;
  candidates: LocationCandidate[];
  id: string;
  isLoading: boolean;
  label: string;
  placeholder: string;
  value: string;
  onBlur: () => void;
  onChange: (value: string) => void;
  onFocus: () => void;
  onSelect: (candidate: LocationCandidate) => void;
}) {
  const showPanel = active && (isLoading || candidates.length > 0);

  return (
    <label className="relative block" htmlFor={id}>
      <span className="text-xs font-semibold text-ink/46">{label}</span>
      <input
        autoComplete="off"
        className="mt-1 min-h-11 w-full rounded-xl border border-ink/10 bg-white px-3 text-sm font-semibold outline-none transition placeholder:text-ink/35 focus:border-tide"
        id={id}
        placeholder={placeholder}
        value={value}
        onBlur={onBlur}
        onChange={(event) => onChange(event.target.value)}
        onFocus={onFocus}
      />
      {showPanel ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-2xl bg-white shadow-[0_16px_40px_rgba(23,26,24,0.13)] ring-1 ring-ink/10">
          {isLoading ? (
            <div className="px-3 py-3 text-sm font-semibold text-ink/42">
              장소 검색 중
            </div>
          ) : null}
          {candidates.map((candidate) => (
            <button
              className="flex w-full items-start gap-3 px-3 py-3 text-left transition hover:bg-[#fff9ed] active:bg-[#fde2ef]"
              key={`${candidate.source}-${candidate.label}-${candidate.lat}-${candidate.lng}`}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onSelect(candidate)}
            >
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#ddf3eb] text-moss">
                <MapPin size={17} aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-ink">
                  {candidate.label}
                </span>
                <span className="mt-0.5 block truncate text-xs text-ink/46">
                  {locationCandidateMeta(candidate)}
                </span>
              </span>
              <span className="mt-1 rounded-lg bg-[#fde2ef] px-2 py-1 text-[11px] font-semibold text-tide">
                선택
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </label>
  );
}

function ComposerTitle({
  icon,
  label,
  support
}: {
  icon: ReactNode;
  label: string;
  support: string;
}) {
  return (
    <div className="flex min-w-0 items-start gap-2.5">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#ddf3eb] text-moss">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink/72">{label}</span>
        <span className="mt-0.5 block break-words text-xs leading-5 text-ink/45">
          {support}
        </span>
      </span>
    </div>
  );
}

function PlanPreview({
  activeMood,
  destinationText,
  dislikedCount,
  likedCount,
  originText
}: {
  activeMood: string;
  destinationText: string;
  dislikedCount: number;
  likedCount: number;
  originText: string;
}) {
  return (
    <section className="rounded-[24px] bg-white p-4 shadow-[0_14px_40px_rgba(23,26,24,0.055)] ring-1 ring-ink/8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-ink/42">미리보기</p>
          <h2 className="mt-1 text-xl font-semibold leading-tight [word-break:keep-all]">
            추천 전 확인
          </h2>
        </div>
        <span className="rounded-xl bg-[#ddf3eb] px-2.5 py-1 text-xs font-semibold text-moss">
          준비
        </span>
      </div>

      <div className="mt-4 rounded-2xl bg-[#fffdf8] p-3 ring-1 ring-ink/8">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fde2ef] text-tide">
            <Navigation size={18} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-ink/40">경로</p>
            <p className="mt-0.5 truncate text-base font-semibold">
              {originText || "출발지"} → {destinationText || "도착지"}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-3 divide-y divide-ink/8 rounded-2xl border border-ink/8 bg-white">
        <PreviewRow label="컨디션" value={activeMood} />
        <PreviewRow label="선호 장소" value={`${likedCount}개`} />
        <PreviewRow label="비선호 장소" value={`${dislikedCount}개`} />
      </div>

      <div className="mt-4 grid gap-2">
        <PlannerCue icon={<HeartPulse size={15} aria-hidden />} label="피로도와 혼잡도 반영" />
        <PlannerCue icon={<Coffee size={15} aria-hidden />} label="선호 장소는 경유 후보로만 사용" />
        <PlannerCue icon={<Clock3 size={15} aria-hidden />} label="시간 제약 시 우회 최소화" />
      </div>
    </section>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-3 px-3 py-2">
      <span className="text-xs font-semibold text-ink/42">{label}</span>
      <span className="min-w-0 truncate text-sm font-semibold text-ink/74">{value}</span>
    </div>
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
      setFeedbackStatus(liked ? "선호 경로로 저장됨" : "비선호 경로로 저장됨");
    } catch {
      setFeedbackStatus("피드백 저장 실패");
    }
  }

  return (
    <>
      <section className="rounded-2xl bg-white p-4 shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-moss">추천 경로</p>
            <h2 className="mt-1 break-words text-2xl font-semibold leading-tight">
              {routeDisplayName(plan.selected_route)}
            </h2>
          </div>
          <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-2xl bg-tide text-white">
            <span className="text-xs font-semibold text-white/75">편안함</span>
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

        <div className="mt-3 rounded-2xl bg-[#fff9ed] p-3 text-xs leading-5 text-ink/58">
          {routeReliabilityLabel(plan.selected_route, usesKakaoPoi)}
          {plan.selected_route.fallback_reason ? (
            <span className="mt-1 block text-ink/42">
              {plan.selected_route.fallback_reason}
            </span>
          ) : null}
        </div>

        {firstTradeoff ? (
          <div className="mt-4 rounded-2xl bg-[#fff9ed] p-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Zap className="text-coral" size={16} aria-hidden />
              핵심 균형점
            </div>
            <p className="mt-2 text-sm leading-6 text-ink/68">{firstTradeoff.reason}</p>
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            className="min-h-11 rounded-xl bg-[#ddf3eb] px-3 text-sm font-semibold text-moss transition active:scale-[0.99]"
            type="button"
            onClick={() => handleFeedback(true)}
          >
            이 길 괜찮았어요
          </button>
          <button
            className="min-h-11 rounded-xl bg-[#fde2ef] px-3 text-sm font-semibold text-coral transition active:scale-[0.99]"
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
        <SectionTitle icon={<Navigation size={18} aria-hidden />} title="후보 경로" />
        <RouteList routes={plan.routes} selectedRouteId={plan.selected_route.id} />
      </section>
    </>
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
        setSdkError("카카오 지도 지연. 간단 미리보기 표시");
        setStatus("fallback");
      }
    }, 4500);

    if (!kakaoJsKey) {
      window.clearTimeout(fallbackTimer);
      setSdkError("카카오 지도 키 없음. 간단 미리보기 표시");
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
          setSdkError("카카오 지도 인증 또는 도메인 설정 확인 필요");
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
        providerLabel={sdkError ? "카카오 연결 실패" : "간단 미리보기"}
        statusMessage={sdkError}
        usesKakaoPoi={usesKakaoPoi}
      />
    );
  }

  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-moss">
            {status === "ready" ? "카카오 지도" : "지도 연결 중"}
          </p>
          <h2 className="text-lg font-semibold">동선 미리보기</h2>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="rounded-xl bg-[#fde2ef] px-2.5 py-1 text-xs font-semibold text-tide">
            {usesKakaoPoi ? "실제 장소" : "예시 장소"}
          </span>
          <MapPinned className="text-tide" size={22} aria-hidden />
        </div>
      </div>
      <div ref={containerRef} className="h-60 w-full bg-[#fff4cc]" />
    </section>
  );
}

function MapPreview({
  map,
  providerLabel = "간단 지도",
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
    <section className="overflow-hidden rounded-2xl bg-white shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-moss">{providerLabel}</p>
          <h2 className="text-lg font-semibold">동선 미리보기</h2>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="rounded-xl bg-[#fde2ef] px-2.5 py-1 text-xs font-semibold text-tide">
            {usesKakaoPoi ? "실제 장소" : "예시 장소"}
          </span>
          <MapPinned className="text-tide" size={22} aria-hidden />
        </div>
      </div>
      {statusMessage ? (
        <p className="mx-4 mb-3 rounded-2xl bg-[#fde2ef] px-3 py-2 text-xs leading-5 text-coral">
          {statusMessage}
        </p>
      ) : null}
      <div className="relative h-60 bg-[#fff4cc]">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(23,26,24,0.05)_1px,transparent_1px),linear-gradient(rgba(23,26,24,0.05)_1px,transparent_1px)] bg-[size:34px_34px]" />
        <svg
          className="absolute inset-0 h-full w-full"
          role="img"
          aria-label="플래너 경로 미리보기"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {map.emotion_zones.map((zone) => {
            const point = projected(zone.center);
            return (
              <circle
                cx={point.x}
                cy={point.y}
                fill="rgba(217,120,166,0.20)"
                key={zone.id}
                r="9"
                stroke="rgba(217,120,166,0.70)"
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
    <article className="rounded-2xl bg-white p-4 shadow-[0_12px_34px_rgba(23,26,24,0.04)] ring-1 ring-ink/8">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-ink/60">전체 감정 비용</span>
        <span className="rounded-xl bg-[#fde2ef] px-3 py-1 text-sm font-semibold text-tide">
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
      <div className="h-2 overflow-hidden rounded-full bg-[#fff4cc]">
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
          className="grid grid-cols-[58px_1fr] gap-3 rounded-2xl bg-white p-3 shadow-[0_8px_22px_rgba(23,26,24,0.035)] ring-1 ring-ink/8"
          key={`${item.time}-${item.label}`}
        >
          <span className="rounded-xl bg-[#fde2ef] px-2 py-2 text-center text-sm font-semibold text-tide">
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
            className={`rounded-2xl p-3 shadow-[0_8px_22px_rgba(23,26,24,0.035)] ring-1 ${
              selected ? "bg-[#fff1f7] ring-tide/35" : "bg-white ring-ink/8"
            }`}
            key={route.id}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-sm font-semibold">
                {routeDisplayName(route)}
              </span>
              <div className="flex shrink-0 items-center gap-1">
                <span className="rounded-xl bg-[#fde2ef] px-2 py-1 text-xs font-semibold text-tide">
                  {routeProviderLabel(route)}
                </span>
                {selected ? (
                  <span className="rounded-xl bg-tide px-2 py-1 text-xs font-semibold text-white">
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

function PlannerCue({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="flex min-h-10 items-center gap-2 rounded-xl bg-[#fffdf8] px-3 text-sm font-semibold text-ink/64 ring-1 ring-ink/7">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#fde2ef] text-tide/80">
        {icon}
      </span>
      <span>{label}</span>
    </div>
  );
}

function PreferenceMap({
  points,
  votes
}: {
  points: PreferencePoint[];
  votes: Record<string, PreferenceVote>;
}) {
  const visiblePoints = points.length > 0 ? points : POI_PREFERENCES;
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const [mapStatus, setMapStatus] = useState<KakaoStatus>("loading");
  const [selectedPointId, setSelectedPointId] = useState(visiblePoints[0]?.id ?? "");
  const selectedPoint =
    visiblePoints.find((point) => point.id === selectedPointId) ?? visiblePoints[0];
  const kakaoJsKey = process.env.NEXT_PUBLIC_KAKAO_JS_KEY;

  useEffect(() => {
    if (!visiblePoints.some((point) => point.id === selectedPointId)) {
      setSelectedPointId(visiblePoints[0]?.id ?? "");
    }
  }, [selectedPointId, visiblePoints]);

  useEffect(() => {
    let cancelled = false;
    if (!kakaoJsKey || !mapContainerRef.current) {
      setMapStatus("fallback");
      return;
    }

    setMapStatus("loading");
    loadKakaoMaps(kakaoJsKey)
      .then(() => {
        if (cancelled || !mapContainerRef.current || !window.kakao?.maps) {
          return;
        }
        renderPreferenceKakaoMap(
          mapContainerRef.current,
          visiblePoints,
          votes,
          selectedPointId,
          setSelectedPointId
        );
        setMapStatus("ready");
      })
      .catch((caught) => {
        if (!cancelled) {
          console.warn("Preference map fell back because Kakao Maps failed.", caught);
          setMapStatus("fallback");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [kakaoJsKey, selectedPointId, visiblePoints, votes]);

  return (
    <section className="overflow-hidden rounded-[24px] bg-white shadow-[0_14px_40px_rgba(23,26,24,0.055)] ring-1 ring-ink/8">
      <div className="flex items-start justify-between gap-3 px-5 py-4">
        <div>
          <p className="text-xs font-semibold text-moss">선호 지도</p>
          <h2 className="mt-1 text-xl font-semibold">선호 지도</h2>
        </div>
        <div className="flex gap-1.5 text-[11px] font-semibold text-ink/45">
          <span className="rounded-lg bg-[#ddf3eb] px-2 py-1">선호</span>
          <span className="rounded-lg bg-[#fde2ef] px-2 py-1">비선호</span>
        </div>
      </div>

      <div className="relative mx-5 h-[300px] overflow-hidden rounded-2xl bg-[#fff9ed] ring-1 ring-ink/8">
        <div ref={mapContainerRef} className="absolute inset-0" />
        {mapStatus !== "ready" ? (
          <>
            <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(23,26,24,0.05)_1px,transparent_1px),linear-gradient(rgba(23,26,24,0.05)_1px,transparent_1px)] bg-[size:36px_36px]" />
            <div className="absolute left-[16%] right-[18%] top-[48%] h-2 -rotate-12 rounded-full bg-white/80 shadow-sm" />
            <div className="absolute bottom-[18%] left-[46%] top-[14%] w-2 rotate-6 rounded-full bg-white/80 shadow-sm" />
          </>
        ) : null}
        <div className="absolute inset-0 bg-white/10" />

        {mapStatus !== "ready"
          ? visiblePoints.map((point) => {
              const signal = resolvePreferenceSignal(point, visiblePoints, votes);
              const bounds = pointBounds(visiblePoints);
              const position = projectPoint(point, bounds);
              const selected = selectedPoint?.id === point.id;

              return (
                <button
                  aria-label={point.name}
                  className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full transition ${
                    selected ? "z-10 h-8 w-8 scale-110" : "h-7 w-7 hover:scale-105"
                  } ${preferenceMapTone(signal)}`}
                  key={point.id}
                  type="button"
                  onClick={() => setSelectedPointId(point.id)}
                  style={{ left: `${position.x}%`, top: `${position.y}%` }}
                >
                  <span className="flex h-full w-full items-center justify-center rounded-full">
                    <MapPin size={13} aria-hidden />
                  </span>
                </button>
              );
            })
          : null}
      </div>

      {selectedPoint ? (
        <div className="p-5">
          <button
            className="flex w-full items-center justify-between gap-3 rounded-2xl bg-[#fffdf8] px-4 py-3 text-left ring-1 ring-tide/35"
            type="button"
          >
            <span className="min-w-0">
              <span className="block text-xs font-semibold text-ink/42">
                {selectedPoint.kind}
              </span>
              <span className="mt-0.5 block truncate text-lg font-semibold">
                {selectedPoint.name}
              </span>
            </span>
            <span className="shrink-0 text-sm font-semibold text-tide">
              {preferenceSignalLabel(
                resolvePreferenceSignal(selectedPoint, visiblePoints, votes)
              )}
            </span>
          </button>
        </div>
      ) : null}
    </section>
  );
}

function PreferenceDeck({
  activeIndex,
  points,
  votes,
  onReset,
  onSkip,
  onVote
}: {
  activeIndex: number;
  points: PreferencePoint[];
  votes: Record<string, PreferenceVote>;
  onReset: () => void;
  onSkip: () => void;
  onVote: (id: string, vote: PreferenceVote) => void;
}) {
  const visiblePoints = points.length > 0 ? points : POI_PREFERENCES;
  const active = visiblePoints[activeIndex % visiblePoints.length];
  const Icon = active.icon;
  const liked = visiblePoints.filter((item) => votes[item.id] === "like");
  const disliked = visiblePoints.filter((item) => votes[item.id] === "dislike");
  const affected = visiblePoints.filter(
    (item) => resolvePreferenceSignal(item, visiblePoints, votes) !== null
  );
  const [dragStartX, setDragStartX] = useState<number | null>(null);
  const [dragX, setDragX] = useState(0);
  const [leavingVote, setLeavingVote] = useState<PreferenceVote | null>(null);

  useEffect(() => {
    setDragStartX(null);
    setDragX(0);
    setLeavingVote(null);
  }, [active.id]);

  function commitSwipe(vote: PreferenceVote) {
    setLeavingVote(vote);
    setDragX(vote === "like" ? 360 : -360);
    window.setTimeout(() => onVote(active.id, vote), 150);
  }

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    setDragStartX(event.clientX - dragX);
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (dragStartX === null) {
      return;
    }
    setDragX(Math.max(-150, Math.min(150, event.clientX - dragStartX)));
  }

  function handlePointerUp() {
    if (dragStartX === null) {
      return;
    }
    setDragStartX(null);
    if (dragX > SWIPE_THRESHOLD) {
      commitSwipe("like");
      return;
    }
    if (dragX < -SWIPE_THRESHOLD) {
      commitSwipe("dislike");
      return;
    }
    setDragX(0);
  }

  const dragVote = dragX > 32 ? "like" : dragX < -32 ? "dislike" : null;
  const rotate = dragX / 18;
  const cardStyle = {
    transform: `translateX(${dragX}px) rotate(${rotate}deg)`,
    transition: dragStartX === null ? "transform 160ms ease-out" : "none"
  };

  return (
    <article className="order-1 overflow-hidden rounded-[24px] border border-ink/8 bg-white p-4 shadow-[0_18px_48px_rgba(23,26,24,0.07)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-tide">위치 포인트</p>
          <p className="mt-1 text-xs leading-5 text-ink/48">스와이프</p>
        </div>
        <button
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fff9ed] text-ink/54 transition hover:text-tide active:scale-95"
          type="button"
          onClick={onReset}
          aria-label="장소 취향 다시 고르기"
        >
          <RotateCcw size={16} aria-hidden />
        </button>
      </div>

      <div className="relative mt-4 h-[430px] rounded-[24px] bg-[#fff9ed] p-3 shadow-[inset_0_0_0_1px_rgba(217,120,166,0.10)]">
        <div className="absolute inset-x-8 bottom-5 top-7 rotate-[-5deg] rounded-2xl bg-white/60 ring-1 ring-ink/5" />
        <div className="absolute inset-x-5 bottom-4 top-5 rotate-[4deg] rounded-2xl bg-white/75 ring-1 ring-ink/6" />
        <div
          className="preference-card relative h-full cursor-grab select-none overflow-hidden rounded-[22px] bg-white p-0 shadow-[0_18px_38px_rgba(23,26,24,0.12)] ring-1 ring-ink/8 active:cursor-grabbing"
          key={active.id}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          style={cardStyle}
        >
          <div
            className={`pointer-events-none absolute left-4 top-4 rounded-xl border px-3 py-1 text-sm font-bold transition ${
              dragVote === "dislike" || leavingVote === "dislike"
                ? "rotate-[-10deg] border-coral text-coral opacity-100"
                : "opacity-0"
            }`}
          >
            별로
          </div>
          <div
            className={`pointer-events-none absolute right-4 top-4 rounded-xl border px-3 py-1 text-sm font-bold transition ${
              dragVote === "like" || leavingVote === "like"
                ? "rotate-[10deg] border-moss text-moss opacity-100"
                : "opacity-0"
            }`}
          >
            선호
          </div>
          <PreferenceVisual icon={Icon} point={active} />
          <div className="flex items-start gap-3 p-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#fde2ef] text-tide">
              <Icon size={24} aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-ink/42">{active.kind}</p>
              <h3 className="mt-1 text-xl font-semibold leading-tight [word-break:keep-all]">
                {active.name}
              </h3>
              <p className="mt-2 text-sm leading-5 text-ink/58 [word-break:keep-all]">
                {active.detail}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5 px-4 pb-4">
            {preferenceDisplayTags(active, visiblePoints, votes).map((tag) => (
              <span
                className="rounded-lg bg-[#fff9ed] px-2.5 py-1 text-xs font-semibold text-ink/50"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <button
          className="flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-[#ddf3eb] text-sm font-semibold text-moss transition active:scale-[0.98]"
          type="button"
          onClick={() => commitSwipe("like")}
        >
          <ThumbsUp size={16} aria-hidden />
          선호
        </button>
        <button
          className="min-h-11 rounded-xl bg-[#fff9ed] px-3 text-sm font-semibold text-ink/52 transition active:scale-[0.98]"
          type="button"
          onClick={onSkip}
        >
          넘기기
        </button>
        <button
          className="flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-[#fde2ef] text-sm font-semibold text-coral transition active:scale-[0.98]"
          type="button"
          onClick={() => commitSwipe("dislike")}
        >
          <ThumbsDown size={16} aria-hidden />
          별로
        </button>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="flex gap-1">
          {visiblePoints.map((item, index) => (
            <span
              className={`h-1.5 rounded-full transition-all ${
                index === activeIndex ? "w-5 bg-tide" : "w-1.5 bg-ink/14"
              }`}
              key={item.id}
            />
          ))}
        </div>
        <p className="text-xs font-medium text-ink/42">
          선호 {liked.length} · 비선호 {disliked.length} · 반영 {affected.length}
        </p>
      </div>
    </article>
  );
}

function PreferenceVisual({
  icon: Icon,
  point
}: {
  icon: LucideIcon;
  point: PreferencePoint;
}) {
  return (
    <div
      className={`relative h-48 overflow-hidden ${preferenceVisualTone(point)} text-white`}
    >
      <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.20),transparent_45%),radial-gradient(circle_at_78%_22%,rgba(255,255,255,0.30),transparent_28%)]" />
      <div className="absolute -bottom-12 -right-10 h-36 w-36 rounded-full bg-white/18" />
      <div className="absolute left-5 top-5 flex items-center gap-2 rounded-2xl bg-white/22 px-3 py-2 text-xs font-semibold backdrop-blur">
        <Icon size={16} aria-hidden />
        {point.kind}
      </div>
      <div className="absolute bottom-5 left-5 right-5">
        <h3 className="mt-1 line-clamp-2 text-3xl font-semibold leading-tight [word-break:keep-all]">
          {point.name}
        </h3>
      </div>
    </div>
  );
}

function isSavedPlaceKind(value: unknown): value is SavedPlaceKind {
  return (
    value === "home" ||
    value === "school" ||
    value === "work" ||
    value === "favorite"
  );
}

function isSavedPlaceEntry(value: unknown): value is SavedPlaceEntry {
  if (!value || typeof value !== "object") {
    return false;
  }

  const place = value as Partial<SavedPlaceEntry>;
  return (
    typeof place.id === "string" &&
    typeof place.name === "string" &&
    typeof place.address === "string" &&
    isSavedPlaceKind(place.kind) &&
    typeof place.updatedAt === "string"
  );
}

function normalizePlaceText(value: string) {
  return value.toLowerCase().replace(/\s+/g, "");
}

function guessSavedPlaceKind(value: string): SavedPlaceKind {
  const normalized = value.toLowerCase();
  if (normalized.includes("집") || normalized.includes("home")) {
    return "home";
  }
  if (
    normalized.includes("학교") ||
    normalized.includes("대학교") ||
    normalized.includes("campus") ||
    normalized.includes("school")
  ) {
    return "school";
  }
  if (
    normalized.includes("회사") ||
    normalized.includes("오피스") ||
    normalized.includes("office")
  ) {
    return "work";
  }
  return "favorite";
}

function savedPlaceKindLabel(kind: SavedPlaceKind) {
  if (kind === "home") {
    return "집";
  }
  if (kind === "school") {
    return "학교";
  }
  if (kind === "work") {
    return "회사";
  }
  return "자주 감";
}

function savedPlaceIcon(kind: SavedPlaceKind) {
  if (kind === "home") {
    return <Home size={18} aria-hidden />;
  }
  if (kind === "school") {
    return <Building2 size={18} aria-hidden />;
  }
  if (kind === "work") {
    return <Coffee size={18} aria-hidden />;
  }
  return <MapPin size={18} aria-hidden />;
}

function preferenceDisplayTags(
  point: PreferencePoint,
  points: PreferencePoint[],
  votes: Record<string, PreferenceVote>
) {
  const signal = resolvePreferenceSignal(point, points, votes);
  const hasVotes = Object.keys(votes).length > 0;

  if (signal === "like") {
    return ["내가 선호", `${point.kind} 취향 강화`];
  }
  if (signal === "dislike") {
    return ["내가 비선호", `${point.kind} 노출 줄임`];
  }
  if (signal === "similar-like") {
    return ["비슷한 선호", `${point.kind} 계열`];
  }
  if (signal === "similar-dislike") {
    return ["비슷한 비선호", `${point.kind} 계열`];
  }
  if (hasVotes) {
    return ["새 후보", "판단 전"];
  }
  return ["첫 판단", point.kind];
}

function preferencePointFromCandidate(candidate: PoiCandidate): PreferencePoint {
  return {
    id: createPointId(candidate),
    name: candidate.name,
    kind: landmarkLabel(candidate),
    detail: pointDetail(candidate),
    icon: iconForLandmark(candidate.landmark_type, candidate.category),
    tags: pointTags(candidate),
    lat: candidate.lat,
    lng: candidate.lng,
    source: sourceLabel(candidate.source_confidence)
  };
}

function buildPreferencePoints(plan: DailyPlan | null): PreferencePoint[] {
  if (!plan) {
    return POI_PREFERENCES;
  }

  const candidates = [
    ...plan.stops,
    ...plan.routes.flatMap((route) => route.stops)
  ];
  const pointsById = new Map<string, PreferencePoint>();

  candidates.forEach((candidate) => {
    if (!Number.isFinite(candidate.lat) || !Number.isFinite(candidate.lng)) {
      return;
    }

    const id = createPointId(candidate);
    if (pointsById.has(id)) {
      return;
    }

    pointsById.set(id, preferencePointFromCandidate(candidate));
  });

  return pointsById.size > 0 ? Array.from(pointsById.values()) : POI_PREFERENCES;
}

function createPointId(candidate: PoiCandidate) {
  return candidate.provider_id
    ? `poi-${candidate.provider_id}`
    : `poi-${candidate.id}-${candidate.lat.toFixed(5)}-${candidate.lng.toFixed(5)}`;
}

function iconForLandmark(landmarkType: string, category: string): LucideIcon {
  const normalized = `${landmarkType} ${category}`.toLowerCase();
  if (normalized.includes("cafe") || normalized.includes("coffee")) {
    return Coffee;
  }
  if (normalized.includes("park") || normalized.includes("green")) {
    return Leaf;
  }
  if (
    normalized.includes("station") ||
    normalized.includes("transit") ||
    normalized.includes("subway")
  ) {
    return Navigation;
  }
  if (
    normalized.includes("school") ||
    normalized.includes("university") ||
    normalized.includes("campus")
  ) {
    return Building2;
  }
  if (normalized.includes("hospital") || normalized.includes("medical")) {
    return HeartPulse;
  }
  return MapPin;
}

function landmarkLabel(candidate: PoiCandidate) {
  const normalized = `${candidate.landmark_type} ${candidate.category}`.toLowerCase();
  if (normalized.includes("cafe") || normalized.includes("coffee")) {
    return "카페";
  }
  if (normalized.includes("bookstore")) {
    return "서점";
  }
  if (normalized.includes("library")) {
    return "도서관";
  }
  if (normalized.includes("food") || normalized.includes("restaurant")) {
    return "음식점";
  }
  if (normalized.includes("park") || normalized.includes("green")) {
    return "공원";
  }
  if (normalized.includes("station") || normalized.includes("transit")) {
    return "교통";
  }
  if (normalized.includes("school") || normalized.includes("university")) {
    return "학교";
  }
  if (normalized.includes("hospital") || normalized.includes("medical")) {
    return "의료";
  }
  return candidate.category || candidate.landmark_type || "장소";
}

function pointDetail(candidate: PoiCandidate) {
  const source = sourceLabel(candidate.source_confidence);
  const distance =
    candidate.distance_meters === null
      ? "주변 후보"
      : `약 ${Math.round(candidate.distance_meters)}m`;

  return `${source} · ${distance}`;
}

function pointTags(candidate: PoiCandidate) {
  const tags = candidate.emotion_tags
    .filter(Boolean)
    .map(translateEmotionTag)
    .slice(0, 3);
  if (tags.length > 0) {
    return tags;
  }
  return [landmarkLabel(candidate)];
}

function translateEmotionTag(tag: string) {
  const labels: Record<string, string> = {
    calm: "차분함",
    recovery: "회복",
    familiar: "익숙함",
    crowded: "혼잡",
    stressful: "부담",
    high_noise: "소음",
    walkable: "걷기 좋음"
  };

  return labels[tag] ?? tag;
}

function sourceLabel(source: string) {
  if (source === "kakao") {
    return "실제 위치";
  }
  if (source === "mock") {
    return "예시 위치";
  }
  return source || "위치 정보";
}

function pointBounds(points: PreferencePoint[]) {
  const lats = points.map((point) => point.lat);
  const lngs = points.map((point) => point.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);

  return {
    minLat,
    maxLat,
    minLng,
    maxLng,
    latRange: Math.max(0.0001, maxLat - minLat),
    lngRange: Math.max(0.0001, maxLng - minLng)
  };
}

function projectPoint(
  point: PreferencePoint,
  bounds: ReturnType<typeof pointBounds>
) {
  return {
    x: 12 + ((point.lng - bounds.minLng) / bounds.lngRange) * 76,
    y: 88 - ((point.lat - bounds.minLat) / bounds.latRange) * 76
  };
}

function preferenceVisualTone(point: PreferencePoint) {
  const normalized = `${point.kind} ${point.tags.join(" ")}`.toLowerCase();
  if (normalized.includes("cafe") || normalized.includes("카페")) {
    return "bg-[linear-gradient(135deg,#d978a6,#f6c56f)]";
  }
  if (normalized.includes("park") || normalized.includes("공원")) {
    return "bg-[linear-gradient(135deg,#6f9f87,#b6dfd0)]";
  }
  if (normalized.includes("book") || normalized.includes("도서") || normalized.includes("서점")) {
    return "bg-[linear-gradient(135deg,#b781b6,#f2c7d8)]";
  }
  if (normalized.includes("transit") || normalized.includes("교통") || normalized.includes("역")) {
    return "bg-[linear-gradient(135deg,#6fa5b8,#d8e9df)]";
  }
  return "bg-[linear-gradient(135deg,#d978a6,#8fcfbd)]";
}

function resolvePreferenceSignal(
  point: PreferencePoint,
  points: PreferencePoint[],
  votes: Record<string, PreferenceVote>
): PreferenceSignal {
  const direct = votes[point.id];
  if (direct) {
    return direct;
  }

  const similarLiked = points.some(
    (candidate) => votes[candidate.id] === "like" && areSimilarPoints(point, candidate)
  );
  if (similarLiked) {
    return "similar-like";
  }

  const similarDisliked = points.some(
    (candidate) =>
      votes[candidate.id] === "dislike" && areSimilarPoints(point, candidate)
  );
  if (similarDisliked) {
    return "similar-dislike";
  }

  return null;
}

function areSimilarPoints(a: PreferencePoint, b: PreferencePoint) {
  if (a.id === b.id) {
    return false;
  }
  if (a.kind === b.kind) {
    return true;
  }
  return a.tags.some((tag) => b.tags.includes(tag));
}

function preferenceSignalLabel(signal: PreferenceSignal) {
  if (signal === "like") {
    return "선호";
  }
  if (signal === "dislike") {
    return "비선호";
  }
  if (signal === "similar-like") {
    return "비슷한 선호";
  }
  if (signal === "similar-dislike") {
    return "비슷한 비선호";
  }
  return "미분류";
}

function preferenceMapTone(signal: PreferenceSignal) {
  if (signal === "like") {
    return "bg-[#73b89e] text-white shadow-[0_3px_10px_rgba(95,114,95,0.22)]";
  }
  if (signal === "similar-like") {
    return "bg-[#dff3eb] text-moss shadow-[0_3px_8px_rgba(95,114,95,0.14)]";
  }
  if (signal === "dislike") {
    return "bg-[#d978a6] text-white shadow-[0_3px_10px_rgba(217,120,166,0.24)]";
  }
  if (signal === "similar-dislike") {
    return "bg-[#f7d6e6] text-tide shadow-[0_3px_8px_rgba(217,120,166,0.14)]";
  }
  return "bg-white text-ink/58 shadow-[0_3px_8px_rgba(23,26,24,0.16)]";
}

async function resolveLocationInput(
  rawText: string,
  currentLocation: Location | null,
  selectedLocation: Location | null = null
) {
  const normalized = normalizeLocationText(rawText);
  if (selectedLocation && normalized === normalizeLocationText(selectedLocation.label)) {
    return {
      location: selectedLocation,
      source: "selected-search"
    };
  }

  if (
    currentLocation &&
    ["현재위치", "내위치", "currentlocation"].includes(normalized)
  ) {
    return {
      location: currentLocation,
      source: "browser-geolocation"
    };
  }

  return geocodeLocation(rawText.trim());
}

function shouldSearchLocationInput(query: string) {
  return query.length >= 2 || ["집", "학교", "회사"].includes(query);
}

function normalizeLocationText(value: string) {
  return value.toLowerCase().replace(/\s+/g, "");
}

function locationCandidateMeta(candidate: LocationCandidate) {
  const parts = [
    locationSourceLabel(candidate.source),
    candidate.category,
    candidate.address,
    candidate.distance_meters ? `약 ${candidate.distance_meters}m` : null
  ].filter(Boolean);

  return parts.join(" · ") || "장소 후보";
}

function locationSourceLabel(source: string) {
  if (source === "kakao-address") {
    return "주소";
  }
  if (source === "kakao-keyword") {
    return "장소";
  }
  if (source === "known") {
    return "바로가기";
  }
  return "검색";
}

function buildPlanningText(
  current: string,
  activeMood: string,
  votes: Record<string, PreferenceVote>,
  points: PreferencePoint[]
) {
  const liked = points.filter((item) => votes[item.id] === "like").map(
    (item) => item.name
  );
  const disliked = points.filter((item) => votes[item.id] === "dislike").map(
    (item) => item.name
  );
  const likedTypes = preferenceTypeSummary(points, votes, "like");
  const dislikedTypes = preferenceTypeSummary(points, votes, "dislike");
  const moodPreset = MOOD_PRESETS.find((mood) => mood.label === activeMood);
  const additions = [
    `컨디션 기준: ${moodPreset ? moodPreset.sentence : activeMood}`
  ];

  if (liked.length > 0) {
    additions.push(`선호하는 근처 장소: ${liked.join(", ")}`);
  }
  if (disliked.length > 0) {
    additions.push(`피하고 싶은 근처 장소: ${disliked.join(", ")}`);
  }
  if (likedTypes.length > 0) {
    additions.push(`선호하는 장소 유형/태그: ${likedTypes.join(", ")}`);
  }
  if (dislikedTypes.length > 0) {
    additions.push(`피하고 싶은 장소 유형/태그: ${dislikedTypes.join(", ")}`);
  }

  return [current.trim(), additions.join("\n")].filter(Boolean).join("\n\n");
}

function preferenceTypeSummary(
  points: PreferencePoint[],
  votes: Record<string, PreferenceVote>,
  vote: PreferenceVote
) {
  const values = points.flatMap((point) =>
    votes[point.id] === vote ? [point.kind, ...point.tags] : []
  );
  return Array.from(new Set(values)).slice(0, 8);
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
    <div className="rounded-2xl bg-[#fff9ed] p-3">
      <p className="text-xs font-semibold text-ink/42">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold">{value}</p>
    </div>
  );
}

function InfoCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-2xl bg-white p-3 text-sm leading-6 text-ink/70 shadow-[0_8px_22px_rgba(23,26,24,0.035)] ring-1 ring-ink/8">
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
      existingScript.addEventListener(
        "error",
        () => reject(createKakaoSdkError(kakaoJsKey)),
        {
          once: true
        }
      );
      return;
    }

    const script = document.createElement("script");
    script.async = true;
    script.dataset.kakaoMapsSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(
      kakaoJsKey
    )}&autoload=false`;
    script.onload = handleLoad;
    script.onerror = () => {
      window.__kakaoMapsPromise = undefined;
      script.remove();
      reject(createKakaoSdkError(kakaoJsKey));
    };
    document.head.appendChild(script);
  });

  return window.__kakaoMapsPromise;
}

function createKakaoSdkError(kakaoJsKey: string) {
  return new Error(
    [
      "Kakao Maps SDK failed.",
      `url=https://dapi.kakao.com/v2/maps/sdk.js?appkey=${kakaoJsKey.slice(0, 6)}...&autoload=false`,
      "Check Kakao JavaScript key, Web platform domain http://localhost:4000, and browser/network blocking."
    ].join(" ")
  );
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
      strokeColor: "#d978a6",
      strokeOpacity: 0.65,
      fillColor: "#d978a6",
      fillOpacity: 0.18
    });
  });

  if (map.markers.length > 0 || map.polylines.length > 0) {
    kakaoMap.setBounds(bounds);
  }
}

function renderPreferenceKakaoMap(
  container: HTMLDivElement,
  points: PreferencePoint[],
  votes: Record<string, PreferenceVote>,
  selectedPointId: string,
  onSelect: (id: string) => void
) {
  const kakao = window.kakao;
  container.innerHTML = "";

  const centerPoint = averagePoint(points);
  const kakaoMap = new kakao.maps.Map(container, {
    center: new kakao.maps.LatLng(centerPoint.lat, centerPoint.lng),
    level: 5
  });
  const bounds = new kakao.maps.LatLngBounds();

  points.forEach((point) => {
    const position = new kakao.maps.LatLng(point.lat, point.lng);
    bounds.extend(position);
    const signal = resolvePreferenceSignal(point, points, votes);
    const overlayElement = createPreferenceOverlayElement(
      point,
      signal,
      point.id === selectedPointId,
      onSelect
    );

    new kakao.maps.CustomOverlay({
      map: kakaoMap,
      position,
      content: overlayElement,
      xAnchor: 0.5,
      yAnchor: 0.5,
      zIndex: point.id === selectedPointId ? 20 : 10
    });
  });

  if (points.length > 1) {
    kakaoMap.setBounds(bounds);
  }
}

function createPreferenceOverlayElement(
  point: PreferencePoint,
  signal: PreferenceSignal,
  selected: boolean,
  onSelect: (id: string) => void
) {
  const element = document.createElement("button");
  element.type = "button";
  element.ariaLabel = point.name;
  element.className = [
    "flex items-center justify-center rounded-full transition",
    selected ? "h-8 w-8 scale-110" : "h-7 w-7",
    preferenceMapTone(signal)
  ].join(" ");
  element.onclick = () => onSelect(point.id);
  element.innerHTML =
    '<span class="flex h-full w-full items-center justify-center rounded-full"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></svg></span>';

  return element;
}

function averagePoint(points: PreferencePoint[]) {
  if (points.length === 0) {
    return { lat: 37.5665, lng: 126.978 };
  }

  const totals = points.reduce(
    (sum, point) => ({
      lat: sum.lat + point.lat,
      lng: sum.lng + point.lng
    }),
    { lat: 0, lng: 0 }
  );

  return {
    lat: totals.lat / points.length,
    lng: totals.lng / points.length
  };
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
    return "#d978a6";
  }
  if (emotionLevel === "stressful") {
    return "#d96f9a";
  }
  return "#5f725f";
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
  return "추정 경로";
}

function routeReliabilityLabel(route: RouteCandidate, usesKakaoPoi: boolean) {
  const poiLabel = usesKakaoPoi ? "실제 장소" : "예시 장소";
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
