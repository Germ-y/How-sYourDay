"use client";

import { FormEvent, PointerEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Coffee,
  Building2,
  ExternalLink,
  Home,
  HeartPulse,
  Leaf,
  LockKeyhole,
  LogOut,
  Mail,
  MapPin,
  MapPinned,
  MessageCircle,
  Navigation,
  PencilLine,
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
  createSavedPlace,
  deleteSavedPlace,
  fetchMe,
  fetchPreviewInsights,
  fetchPlacePreferences,
  fetchPreferencePoints,
  fetchSavedPlaces,
  geocodeLocation,
  login as loginUser,
  logout as logoutUser,
  requestDailyPlan,
  resolveRouteLocations,
  savePlacePreference,
  sendRouteFeedback,
  searchLocations,
  signup as signupUser,
  type AuthUser,
  type Coordinate,
  type DailyPlan,
  type EmotionCost,
  type Location,
  type LocationCandidate,
  type MapViewModel,
  type PoiCandidate,
  type PreviewInsight,
  type RouteCandidate,
  type TimelineItem,
  type Tradeoff,
  type PlacePreferenceRecord,
  type SavedPlaceRecord
} from "@/lib/api";

const starterText = "";

type WaypointCategoryValue = "cafe" | "walk" | "rest" | "errand" | "meal";

const WAYPOINT_CATEGORY_OPTIONS: Array<{
  label: string;
  value: WaypointCategoryValue;
  hint: string;
  placeholder: string;
  icon: LucideIcon;
}> = [
  { label: "카페", value: "cafe", hint: "작업/휴식 카페", placeholder: "예: 스타벅스, 조용한 카페", icon: Coffee },
  { label: "산책", value: "walk", hint: "산책할 곳", placeholder: "예: 공원, 산책로", icon: Leaf },
  { label: "쉼", value: "rest", hint: "잠깐 쉴 곳", placeholder: "예: 벤치 있는 공원, 조용한 곳", icon: HeartPulse },
  { label: "볼일", value: "errand", hint: "볼일 장소", placeholder: "예: 약국, 다이소, 올리브영", icon: MapPin },
  { label: "식사", value: "meal", hint: "식사 장소", placeholder: "예: 김밥집, 수림식당", icon: Building2 }
];
const SAVED_PLACES_KEY = "hows-your-day.saved-places.v1";
const MOOD_PRESETS = [
  {
    label: "피곤",
    sentence: "피로도 높음. 보행 시간과 혼잡도를 낮게 우선.",
    keywords: ["피곤", "지침", "지쳐", "힘들", "무리", "tired", "exhausted"]
  },
  {
    label: "바쁨",
    sentence: "시간 제약 높음. 우회보다 도착 시간을 우선.",
    keywords: ["바쁨", "급", "빨리", "늦", "촉박", "약속", "보기로", "만나", "도착해야", "urgent", "hurry"]
  },
  {
    label: "급함",
    sentence: "즉시 이동 필요. 지연과 우회를 최소화.",
    keywords: ["급", "빨리", "늦", "촉박", "urgent", "hurry"]
  },
  {
    label: "여유",
    sentence: "시간 여유 있음. 편안한 장소 경유 허용.",
    keywords: ["여유", "천천", "둘러", "괜찮", "slow"]
  },
  {
    label: "산책",
    sentence: "걷기 의향 있음. 주변 탐색과 짧은 경유 허용.",
    keywords: ["산책", "걸을", "걷", "돌아다니", "선선", "walk"]
  },
  {
    label: "휴식",
    sentence: "휴식 필요. 조용한 카페나 공원 후보 반영.",
    keywords: ["휴식", "쉬", "카페", "커피", "편한", "rest", "cafe", "coffee"]
  },
  {
    label: "회복",
    sentence: "에너지 회복 필요. 부담 낮은 경유 후보 반영.",
    keywords: ["회복", "충전", "리셋", "쉬", "recover", "rest"]
  },
  {
    label: "불안",
    sentence: "불안감 높음. 혼잡과 환승 부담을 낮게 우선.",
    keywords: ["불안", "긴장", "복잡", "사람", "혼잡", "무서", "anxious", "nervous"]
  },
  {
    label: "혼잡",
    sentence: "사람 많은 구간 회피. 밀도 낮은 동선 우선.",
    keywords: ["혼잡", "사람", "붐비", "복잡", "crowd"]
  },
  {
    label: "집중",
    sentence: "집중 필요. 목적지까지 예측 가능한 동선을 우선.",
    keywords: ["집중", "공부", "과제", "작업", "시험", "회의", "업무", "focus", "study", "work"]
  },
  {
    label: "몰입",
    sentence: "작업 흐름 유지. 조용하고 예측 가능한 경유 우선.",
    keywords: ["몰입", "과제", "작업", "공부", "집중", "focus"]
  },
  {
    label: "조용",
    sentence: "소음 민감도 높음. 조용한 구간과 장소를 우선.",
    keywords: ["조용", "소음", "시끄", "quiet", "noise"]
  },
  {
    label: "쾌적",
    sentence: "쾌적한 이동 선호. 날씨와 보행감 좋은 구간 반영.",
    keywords: ["쾌적", "선선", "상쾌", "좋아", "pleasant"]
  },
  {
    label: "익숙",
    sentence: "익숙한 동선 선호. 낯선 환승과 복잡도 축소.",
    keywords: ["익숙", "아는", "편한 길", "familiar"]
  },
  {
    label: "편안",
    sentence: "부담 낮은 이동 선호. 무리 없는 경로 우선.",
    keywords: ["편안", "편한", "부담", "무리", "comfortable"]
  },
  {
    label: "안정",
    sentence: "컨디션 안정. 과한 우회 없이 균형 있게 반영.",
    keywords: ["안정", "괜찮", "차분", "steady", "fine"]
  }
];
const DEFAULT_MOOD_LABELS = ["피곤", "바쁨", "여유", "휴식"];
type PreferenceVote = "like" | "dislike";
type PreferenceSignal = PreferenceVote | "similar-like" | "similar-dislike" | null;
type AppView = "planner" | "result" | "taste" | "profile";
type AuthMode = "login" | "signup";
type SavedPlaceKind = "home" | "school" | "work" | "favorite";
type SavedPlaceEntry = {
  id: string;
  name: string;
  address: string;
  kind: SavedPlaceKind;
  lat?: number | null;
  lng?: number | null;
  updatedAt: string;
};
type CustomWaypoint = {
  id: string;
  category: WaypointCategoryValue;
  value: string;
};
type PreferencePoint = {
  id: string;
  name: string;
  kind: string;
  detail: string;
  address: string | null;
  categoryName: string | null;
  categoryGroupName: string | null;
  phone: string | null;
  placeUrl: string | null;
  distanceMeters: number | null;
  icon: LucideIcon;
  tags: string[];
  lat: number;
  lng: number;
  source: string;
};
const SWIPE_THRESHOLD = 86;
const INITIAL_PREFERENCE_RADIUS_METERS = 1800;
const MAX_PREFERENCE_RADIUS_METERS = 5000;
const PREFERENCE_RADIUS_STEP_METERS = 1200;

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
  const [activeMood, setActiveMood] = useState("");
  const [moodEdited, setMoodEdited] = useState(false);
  const [poiPreferenceIndex, setPoiPreferenceIndex] = useState(0);
  const [poiVotes, setPoiVotes] = useState<Record<string, PreferenceVote>>({});
  const [nearbyPreferencePoints, setNearbyPreferencePoints] = useState<
    PreferencePoint[]
  >([]);
  const [preferenceRadiusMeters, setPreferenceRadiusMeters] = useState(
    INITIAL_PREFERENCE_RADIUS_METERS
  );
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
  const [previewInsights, setPreviewInsights] = useState<PreviewInsight[]>(
    defaultPreviewInsights()
  );
  const [editedWaypoints, setEditedWaypoints] = useState<Record<string, string>>({});
  const [deletedWaypoints, setDeletedWaypoints] = useState<Record<string, boolean>>({});
  const [customWaypoints, setCustomWaypoints] = useState<CustomWaypoint[]>([]);
  const [editingWaypointKey, setEditingWaypointKey] = useState<string | null>(null);
  const [suggestedMoodLabels, setSuggestedMoodLabels] = useState<string[]>([]);
  const [previewSource, setPreviewSource] = useState("rules");
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isRouteConfirming, setIsRouteConfirming] = useState(false);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [authForm, setAuthForm] = useState({
    email: "",
    password: "",
    nickname: ""
  });
  const [authStatus, setAuthStatus] = useState("");
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const moodCandidates = useMemo(
    () => buildMoodCandidates(text, suggestedMoodLabels),
    [suggestedMoodLabels, text]
  );
  const visibleMoodCandidates = useMemo(
    () => ensureActiveMoodCandidate(moodCandidates, activeMood),
    [activeMood, moodCandidates]
  );
  const routeWaypointHints = useMemo(
    () =>
      uniqueWaypointHints([
        ...collectTextWaypointHints(text),
        ...collectPreviewWaypointHints(
          previewInsights,
          editedWaypoints,
          deletedWaypoints
        ),
        ...customWaypoints
          .map(customWaypointToHint)
          .filter(Boolean)
      ]).slice(0, 5),
    [customWaypoints, deletedWaypoints, editedWaypoints, previewInsights, text]
  );
  const quickSavedPlaces = useMemo(
    () => buildQuickSavedPlaces(savedPlaces),
    [savedPlaces]
  );

  useEffect(() => {
    const storedSavedPlaces = window.localStorage.getItem(SAVED_PLACES_KEY);
    window.localStorage.removeItem("hows-your-day.origin-text.v1");
    window.localStorage.removeItem("hows-your-day.destination-text.v1");
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
    let cancelled = false;

    fetchMe()
      .then((user) => {
        if (!cancelled) {
          setAuthUser(user);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAuthUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAuthChecked(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!authUser) {
      return;
    }

    let cancelled = false;
    fetchSavedPlaces()
      .then((result) => {
        if (cancelled) {
          return;
        }
        const nextPlaces = result.places.map(savedPlaceRecordToEntry);
        setSavedPlaces(nextPlaces);
        window.localStorage.setItem(SAVED_PLACES_KEY, JSON.stringify(nextPlaces));
        setSavedPlaceNotice("");
      })
      .catch(() => {
        if (!cancelled) {
          setSavedPlaceNotice("");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authUser]);

  useEffect(() => {
    if (!authUser) {
      setPoiVotes({});
      return;
    }

    let cancelled = false;
    fetchPlacePreferences()
      .then((result) => {
        if (cancelled) {
          return;
        }
        setPoiVotes(placePreferenceRecordsToVotes(result.preferences));
      })
      .catch(() => {
        if (!cancelled) {
          setPoiVotes({});
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authUser]);

  useEffect(() => {
    if (!text.trim()) {
      setLocationStatus("이동 요청을 입력한 뒤 내용 확인");
    }
  }, [text]);

  useEffect(() => {
    if (!text.trim()) {
      setMoodEdited(false);
      setActiveMood("");
      return;
    }

    if (!moodEdited) {
      setActiveMood((current) => {
        if (!moodCandidates.length) {
          return "";
        }
        if (current && moodCandidates.some((mood) => mood.label === current)) {
          return current;
        }
        return moodCandidates[0]?.label ?? "";
      });
    }
  }, [moodCandidates, moodEdited, text]);

  useEffect(() => {
    let cancelled = false;
    setPreviewInsights(
      buildLocalPreviewInsights(text, originText, destinationText, activeMood)
    );
    setSuggestedMoodLabels(buildLocalMoodLabels(text));
    setPreviewSource("local");
    setIsPreviewLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const hasRouteRequestText = Boolean(text.trim());
        const result = await fetchPreviewInsights({
          user_text: text,
          origin_text: hasRouteRequestText ? undefined : originText,
          destination_text: hasRouteRequestText ? undefined : destinationText,
          active_mood: moodEdited ? activeMood : undefined
        });
        if (!cancelled) {
          setPreviewInsights(result.insights);
          setSuggestedMoodLabels(result.mood_candidates ?? []);
          if (!moodEdited && text.trim() && result.mood_candidates?.[0]) {
            setActiveMood(result.mood_candidates[0]);
          }
          setPreviewSource(result.source);
        }
      } catch {
        if (!cancelled) {
          setPreviewInsights(
            buildLocalPreviewInsights(text, originText, destinationText, activeMood)
          );
          setSuggestedMoodLabels(buildLocalMoodLabels(text));
          setPreviewSource("local");
        }
      } finally {
        if (!cancelled) {
          setIsPreviewLoading(false);
        }
      }
    }, 420);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [text, originText, destinationText, activeMood, moodEdited]);

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
        const result = await searchLocations(query, 5, currentLocation);
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
  }, [originText, currentLocation]);

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
        const result = await searchLocations(query, 5, currentLocation);
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
  }, [destinationText, currentLocation]);

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

  async function handleAddSavedPlace() {
    const name = savedPlaceDraft.name.trim();
    const address = savedPlaceDraft.address.trim();

    if (!name || !address) {
      setSavedPlaceNotice("장소 이름과 주소를 입력해야 합니다.");
      return;
    }

    await savePlace({
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

  async function savePlace(place: Omit<SavedPlaceEntry, "id" | "updatedAt">) {
    const normalizedAddress = normalizePlaceText(place.address);
    try {
      const saved = await createSavedPlace({
        name: place.name,
        address: place.address,
        kind: place.kind,
        lat: place.lat ?? null,
        lng: place.lng ?? null
      });
      const nextPlace = savedPlaceRecordToEntry(saved);
      const withoutDuplicate = savedPlaces.filter(
        (savedPlace) => normalizePlaceText(savedPlace.address) !== normalizedAddress
      );
      persistSavedPlaces([nextPlace, ...withoutDuplicate].slice(0, 12));
      setSavedPlaceNotice("");
    } catch {
      const nextPlace: SavedPlaceEntry = {
        ...place,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        updatedAt: new Date().toISOString()
      };
      const withoutDuplicate = savedPlaces.filter(
        (savedPlace) => normalizePlaceText(savedPlace.address) !== normalizedAddress
      );
      persistSavedPlaces([nextPlace, ...withoutDuplicate].slice(0, 12));
      setSavedPlaceNotice("");
    }
  }

  async function handleRemoveSavedPlace(id: string) {
    const removed = savedPlaces.find((place) => place.id === id);
    try {
      await deleteSavedPlace(id);
      persistSavedPlaces(savedPlaces.filter((place) => place.id !== id));
      setSavedPlaceNotice("");
    } catch {
      persistSavedPlaces(savedPlaces.filter((place) => place.id !== id));
      setSavedPlaceNotice("");
    }
  }

  function handleUseSavedPlace(place: SavedPlaceEntry, target: "origin" | "destination") {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

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
    window.requestAnimationFrame(() => {
      resetPlannerScroll();
    });
  }

  function handleLocationCandidateSelect(
    field: "origin" | "destination",
    candidate: LocationCandidate
  ) {
    const location = locationFromCandidate(candidate);

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

  function handleLocationTextChange(field: "origin" | "destination", value: string) {
    if (field === "origin") {
      setOriginText(value);
      setOriginEdited(true);
      setSelectedOriginLocation(null);
      setLocationStatus(value.trim() ? "출발지를 직접 입력 중" : "출발지 입력 필요");
    } else {
      setDestinationText(value);
      setDestinationEdited(true);
      setSelectedDestinationLocation(null);
      setLocationStatus(value.trim() ? "도착지를 직접 입력 중" : "도착지 입력 필요");
    }
    setError(null);
  }

  function handleRouteRequestTextChange(value: string) {
    setText(value);
    setEditedWaypoints({});
    setDeletedWaypoints({});
    setCustomWaypoints([]);
    setEditingWaypointKey(null);
    if (!originEdited) {
      setOriginText("");
      setSelectedOriginLocation(null);
      setOriginCandidates([]);
    }
    if (!destinationEdited) {
      setDestinationText("");
      setSelectedDestinationLocation(null);
      setDestinationCandidates([]);
    }
    setLocationStatus(value.trim() ? "내용 확인 필요" : "");
    setError(null);
  }

  function handleAuthFormChange(field: "email" | "password" | "nickname", value: string) {
    setAuthForm((current) => ({
      ...current,
      [field]: value
    }));
    setAuthStatus("");
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsAuthLoading(true);
    setAuthStatus("");

    try {
      const email = authForm.email.trim();
      if (authMode === "signup") {
        await signupUser({
          email,
          password: authForm.password,
          nickname: authForm.nickname.trim() || buildSignupNickname(email)
        });
      }
      await loginUser({
        email,
        password: authForm.password
      });
      const user = await fetchMe();
      setAuthUser(user);
      setAuthForm((current) => ({
        ...current,
        password: ""
      }));
    } catch (caught) {
      setAuthStatus(getAuthErrorMessage(caught));
    } finally {
      setIsAuthLoading(false);
    }
  }

  function handleAuthModeChange(mode: AuthMode) {
    setAuthMode(mode);
    setAuthStatus("");
  }

  function handleLogout() {
    logoutUser();
    setAuthUser(null);
    setSavedPlaces([]);
    setSavedPlaceNotice("");
    setNearbyPreferencePoints([]);
    setPreferenceRadiusMeters(INITIAL_PREFERENCE_RADIUS_METERS);
    setPreferenceStatus("내 주변 장소 준비");
    setPoiVotes({});
    setPoiPreferenceIndex(0);
    setActiveView("planner");
  }

  async function handleRouteTextConfirm() {
    const trimmed = text.trim();
    if (!trimmed) {
      setLocationStatus("이동 요청을 먼저 입력해주세요");
      return;
    }

    setIsRouteConfirming(true);
    setLocationStatus("문장에서 경로 확인 중");
    const localRoute = extractLocalPreviewRoute(trimmed, "", "");

    try {
      const resolved = await resolveRouteLocations(trimmed, currentLocation);
      const originHint = resolved.origin_text ?? localRoute.origin;
      const destinationHint = resolved.destination_text ?? localRoute.destination;
      const [originFallback, destinationFallback] = await Promise.all([
        !resolved.origin && originHint
          ? searchFirstLocationCandidate(originHint, currentLocation)
          : null,
        !resolved.destination && destinationHint
          ? searchFirstLocationCandidate(destinationHint, currentLocation)
          : null
      ]);
      let changed = false;
      let resolvedCount = 0;
      const requestedCount =
        Number(Boolean(originHint)) + Number(Boolean(destinationHint));
      const originCandidate = resolved.origin ?? originFallback;
      const destinationCandidate = resolved.destination ?? destinationFallback;

      if (originHint) {
        if (originCandidate) {
          setOriginText(originCandidate.label);
          setSelectedOriginLocation(locationFromCandidate(originCandidate));
          resolvedCount += 1;
        }
        setOriginEdited(false);
        setOriginCandidates([]);
        changed = changed || Boolean(originCandidate);
      }
      if (destinationHint) {
        if (destinationCandidate) {
          setDestinationText(destinationCandidate.label);
          setSelectedDestinationLocation(locationFromCandidate(destinationCandidate));
          resolvedCount += 1;
        }
        setDestinationEdited(false);
        setDestinationCandidates([]);
        changed = changed || Boolean(destinationCandidate);
      }

      if (changed) {
        setActiveLocationField(null);
        setError(null);
        if (resolvedCount === requestedCount) {
          setLocationStatus("실제 장소로 경로 확인");
        } else if (resolvedCount > 0) {
          setLocationStatus("일부 장소는 실제 장소로 확인");
        } else {
          setLocationStatus("카카오에서 확인된 장소만 입력칸에 반영");
        }
      } else {
        setLocationStatus("카카오에서 확인된 장소를 찾지 못했어요");
      }
    } catch {
      const [originFallback, destinationFallback] = await Promise.all([
        localRoute.origin
          ? searchFirstLocationCandidate(localRoute.origin, currentLocation)
          : null,
        localRoute.destination
          ? searchFirstLocationCandidate(localRoute.destination, currentLocation)
          : null
      ]);
      let changed = false;
      let resolvedCount = 0;
      const requestedCount =
        Number(Boolean(localRoute.origin)) + Number(Boolean(localRoute.destination));

      if (localRoute.origin) {
        if (originFallback) {
          setOriginText(originFallback.label);
          setSelectedOriginLocation(locationFromCandidate(originFallback));
          resolvedCount += 1;
        }
        setOriginEdited(false);
        setOriginCandidates([]);
        changed = changed || Boolean(originFallback);
      }
      if (localRoute.destination) {
        if (destinationFallback) {
          setDestinationText(destinationFallback.label);
          setSelectedDestinationLocation(locationFromCandidate(destinationFallback));
          resolvedCount += 1;
        }
        setDestinationEdited(false);
        setDestinationCandidates([]);
        changed = changed || Boolean(destinationFallback);
      }

      if (changed) {
        setActiveLocationField(null);
        setError(null);
        setLocationStatus(
          resolvedCount === requestedCount
            ? "실제 장소로 경로 확인"
            : "카카오에서 확인된 장소만 입력칸에 반영"
        );
      } else {
        setLocationStatus("카카오에서 확인된 장소를 찾지 못했어요");
      }
    } finally {
      setIsRouteConfirming(false);
    }
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
        destinationResult.location,
        routeWaypointHints
      );
      setLocationStatus(
        `${originResult.location.label} → ${destinationResult.location.label}`
      );
      setPlan(result);
      setActiveView("result");
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
    if (view === "result" && !plan) {
      setActiveView("planner");
      return;
    }

    setActiveView(view);
    if (
      view === "taste" &&
      nearbyPreferencePoints.length === 0 &&
      !isPreferenceLoading
    ) {
      loadNearbyPreferencePoints();
    }
  }

  async function loadPreferencePointsForLocation(
    location: Location,
    radiusMeters: number,
    append: boolean
  ) {
    setIsPreferenceLoading(true);
    setPreferenceStatus(
      append
        ? `범위 넓히는 중 · 약 ${formatDistanceMeters(radiusMeters)}`
        : "장소 불러오는 중"
    );

    try {
      const result = await fetchPreferencePoints(location, radiusMeters);
      const nextPoints = result.points.map((candidate) =>
        preferencePointFromCandidate(candidate)
      );
      setNearbyPreferencePoints((current) =>
        append ? mergePreferencePoints(current, nextPoints) : nextPoints
      );
      setPreferenceStatus(() => {
        if (nextPoints.length === 0) {
          return append ? "새 장소를 더 찾지 못했어요" : "내 주변 실제 장소 없음";
        }
        const mergedCount = append
          ? mergePreferencePoints(nearbyPreferencePoints, nextPoints).length
          : nextPoints.length;
        return `내 주변 실제 장소 ${mergedCount}개 · 약 ${formatDistanceMeters(
          radiusMeters
        )}`;
      });
      setPoiPreferenceIndex(0);
    } catch {
      if (!append) {
        setNearbyPreferencePoints([]);
      }
      setPreferenceStatus("실제 장소를 불러오지 못했어요");
    } finally {
      setIsPreferenceLoading(false);
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
        setPreferenceRadiusMeters(INITIAL_PREFERENCE_RADIUS_METERS);
        await loadPreferencePointsForLocation(
          location,
          INITIAL_PREFERENCE_RADIUS_METERS,
          false
        );
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

  function loadMorePreferencePoints() {
    if (!currentLocation) {
      loadNearbyPreferencePoints();
      return;
    }

    const nextRadius = Math.min(
      MAX_PREFERENCE_RADIUS_METERS,
      preferenceRadiusMeters + PREFERENCE_RADIUS_STEP_METERS
    );
    if (nextRadius <= preferenceRadiusMeters) {
      setPreferenceStatus("최대 범위까지 확인했어요");
      return;
    }

    setPreferenceRadiusMeters(nextRadius);
    void loadPreferencePointsForLocation(currentLocation, nextRadius, true);
  }

  function handleQuickSavedPlaceSelect(place: SavedPlaceEntry) {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

    setDestinationText(place.address);
    setDestinationEdited(true);
    setSelectedDestinationLocation(
      typeof place.lat === "number" && typeof place.lng === "number"
        ? {
            label: place.name,
            lat: place.lat,
            lng: place.lng
          }
        : null
    );
    setDestinationCandidates([]);
    setActiveLocationField(null);
    setLocationStatus(`${place.name}을 도착지로 설정`);
    setError(null);
  }

  function handleMoodSelect(label: string) {
    setMoodEdited(true);
    setActiveMood(label);
  }

  function handleWaypointEditToggle(key: string, value: string) {
    setEditedWaypoints((current) =>
      key in current
        ? current
        : {
            ...current,
            [key]: value
          }
    );
    setEditingWaypointKey((current) => (current === key ? null : key));
  }

  function handleWaypointChange(key: string, value: string) {
    setEditedWaypoints((current) => ({
      ...current,
      [key]: value
    }));
  }

  function handleWaypointDelete(key: string) {
    setDeletedWaypoints((current) => ({
      ...current,
      [key]: true
    }));
    setEditingWaypointKey((current) => (current === key ? null : current));
  }

  function handleCustomWaypointAdd() {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const key = customWaypointKey(id);
    setCustomWaypoints((current) => [...current, { id, category: "cafe", value: "" }]);
    setEditingWaypointKey(key);
  }

  function handleCustomWaypointChange(id: string, value: string) {
    setCustomWaypoints((current) =>
      current.map((waypoint) =>
        waypoint.id === id ? { ...waypoint, value } : waypoint
      )
    );
  }

  function handleCustomWaypointCategoryChange(
    id: string,
    category: WaypointCategoryValue
  ) {
    setCustomWaypoints((current) =>
      current.map((waypoint) =>
        waypoint.id === id ? { ...waypoint, category } : waypoint
      )
    );
  }

  function handleCustomWaypointDelete(id: string) {
    const key = customWaypointKey(id);
    setCustomWaypoints((current) =>
      current.filter((waypoint) => waypoint.id !== id)
    );
    setEditingWaypointKey((current) => (current === key ? null : current));
  }

  function handlePoiVote(id: string, vote: PreferenceVote) {
    const point = preferencePoints.find((item) => item.id === id);
    const pendingBeforeVote = preferencePoints.filter(
      (item) => !poiVotes[item.id]
    ).length;
    setPoiVotes((current) => ({
      ...current,
      [id]: vote
    }));
    setPoiPreferenceIndex((current) => {
      const remaining = Math.max(0, pendingBeforeVote - 1);
      return remaining === 0 ? 0 : Math.min(current, remaining - 1);
    });
    if (point) {
      void savePlacePreference({
        poi_provider_id: point.id,
        name: point.name,
        category: point.kind,
        lat: point.lat,
        lng: point.lng,
        preference: vote
      }).catch(() => {
        setPreferenceStatus("취향 저장 실패");
      });
    }
  }

  function handlePoiSkip() {
    const pendingCount = preferencePoints.filter((item) => !poiVotes[item.id]).length;
    setPoiPreferenceIndex(
      (current) => (current + 1) % Math.max(1, pendingCount)
    );
  }

  function handlePoiReset() {
    setPoiPreferenceIndex(0);
  }

  const likedCount = Object.values(poiVotes).filter((vote) => vote === "like").length;
  const dislikedCount = Object.values(poiVotes).filter(
    (vote) => vote === "dislike"
  ).length;
  const preferencePoints = useMemo(
    () => nearbyPreferencePoints,
    [nearbyPreferencePoints]
  );
  useEffect(() => {
    const pendingCount = preferencePoints.filter((item) => !poiVotes[item.id]).length;
    if (poiPreferenceIndex >= pendingCount) {
      setPoiPreferenceIndex(0);
    }
  }, [poiPreferenceIndex, preferencePoints, poiVotes]);
  const primaryLabel = isLoading ? "경로 계산 중" : "경로 추천";

  if (!authChecked) {
    return <AuthLoading />;
  }

  if (!authUser) {
    return (
      <AuthPage
        form={authForm}
        isLoading={isAuthLoading}
        mode={authMode}
        status={authStatus}
        onChange={handleAuthFormChange}
        onModeChange={handleAuthModeChange}
        onSubmit={handleAuthSubmit}
      />
    );
  }

  return (
    <main className="planner-shell min-h-screen max-w-full overflow-x-hidden bg-[#fff9ed] text-ink">
      <form
        className="mx-auto flex min-h-screen w-full max-w-full flex-col overflow-x-hidden sm:max-w-md lg:max-w-6xl lg:px-6"
        onSubmit={handleSubmit}
      >
        {activeView !== "result" ? (
          <ServiceTopBar
            activeView={activeView}
            onChange={handleViewChange}
          />
        ) : null}
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

        <section className="mt-2 grid min-w-0 gap-5 overflow-x-clip px-5 pb-24 pt-1 lg:grid-cols-[420px_minmax(0,1fr)] lg:items-start lg:px-0 lg:pb-0">
          <article className="min-w-0 overflow-hidden rounded-[28px] bg-white shadow-[0_18px_50px_rgba(23,26,24,0.07)] ring-1 ring-ink/8 lg:sticky lg:top-20">
            <div className="border-b border-ink/8 bg-[#fffdf8] px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-tide">이동 요청</p>
                  <p className="mt-1 text-xs font-medium text-ink/45">
                    문장에서 출발지와 도착지 추출
                  </p>
                </div>
              </div>
            </div>

            <div className="grid min-w-0 gap-5 overflow-visible p-5">
              <section className="min-w-0 overflow-hidden rounded-[22px] bg-[#fff8e6] p-3 shadow-[0_10px_26px_rgba(217,151,76,0.08)] ring-1 ring-[#f2d89d]">
                <ComposerTitle
                  icon={<MessageCircle size={17} aria-hidden />}
                  label="이동 요청"
                  support="일정, 장소, 시간 조건을 한 번에 입력"
                />
                <textarea
                  className="mt-3 min-h-28 w-full resize-none rounded-2xl border border-[#ecd29a] bg-white p-4 text-[15px] leading-6 shadow-sm outline-none transition placeholder:text-ink/35 focus:border-tide focus:bg-white"
                  placeholder="예: 성균관대학교에서 서울역까지, 18시 전 도착. 조용한 카페 경유 가능."
                  value={text}
                  onChange={(event) => handleRouteRequestTextChange(event.target.value)}
                />
                <button
                  className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#ddf3eb] px-4 text-sm font-semibold text-moss shadow-sm ring-1 ring-moss/15 transition hover:bg-[#d2eee4] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
                  type="button"
                  disabled={!text.trim() || isRouteConfirming}
                  onClick={handleRouteTextConfirm}
                >
                  {isRouteConfirming ? "확인 중" : "내용 확인"}
                  <ArrowRight size={17} aria-hidden />
                </button>
              </section>

              <div className="h-px bg-ink/8" />

              <section className="w-full min-w-0 max-w-full overflow-visible rounded-[22px] bg-[#f3fbf7] p-3 ring-1 ring-moss/18">
                <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
                  <ComposerTitle
                    icon={<Navigation size={17} aria-hidden />}
                    label="경로 확인"
                    support="내용 확인으로 채우거나 직접 입력"
                  />
                  <button
                    className="min-h-9 max-w-[86px] shrink-0 rounded-xl bg-white px-3 text-xs font-semibold text-moss shadow-sm ring-1 ring-moss/15 transition hover:bg-[#ddf3eb] active:scale-[0.98]"
                    type="button"
                    onClick={handleUseCurrentLocation}
                  >
                    현재 위치
                  </button>
                </div>

                <div className="mt-3 min-w-0 overflow-visible rounded-2xl bg-white p-3 shadow-sm ring-1 ring-moss/14">
                  <div className="grid min-w-0 gap-3">
                    <div className="grid min-w-0 grid-cols-[12px_minmax(0,1fr)] items-start gap-2">
                      <span className="mt-8 h-2.5 w-2.5 rounded-full bg-moss" />
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
                          handleLocationTextChange("origin", value);
                        }}
                        onFocus={() => setActiveLocationField("origin")}
                        onSelect={(candidate) =>
                          handleLocationCandidateSelect("origin", candidate)
                        }
                      />
                    </div>
                    <div className="grid min-w-0 grid-cols-[12px_minmax(0,1fr)] items-start gap-2">
                      <span className="mt-8 h-2.5 w-2.5 rounded-full bg-tide" />
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
                          handleLocationTextChange("destination", value);
                        }}
                        onFocus={() => setActiveLocationField("destination")}
                        onSelect={(candidate) =>
                          handleLocationCandidateSelect("destination", candidate)
                        }
                      />
                    </div>
                  </div>
                </div>

                {quickSavedPlaces.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {quickSavedPlaces.map((place) => {
                      const selected =
                        normalizeLocationText(destinationText) ===
                        normalizeLocationText(place.address);
                      return (
                        <button
                          className={`inline-flex min-h-10 max-w-full shrink-0 items-center rounded-xl border px-4 text-sm font-semibold transition ${
                            selected
                              ? "border-tide bg-tide text-white shadow-sm"
                              : "border-ink/10 bg-white text-ink/62 hover:border-tide/45"
                          }`}
                          key={place.id}
                          type="button"
                          title={place.address}
                          onClick={() => handleQuickSavedPlaceSelect(place)}
                        >
                          <span className="block max-w-[136px] truncate">
                            {place.name}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </section>

              <div className="h-px bg-ink/8" />

              <section>
                <ComposerTitle
                  icon={<HeartPulse size={17} aria-hidden />}
                  label="컨디션"
                  support="입력 내용에서 후보 4개 추천"
                />
                {visibleMoodCandidates.length > 0 ? (
                  <div className="mt-3 grid grid-cols-4 gap-2">
                    {visibleMoodCandidates.map((mood) => {
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
                ) : (
                  <div className="mt-3 rounded-2xl border border-dashed border-ink/12 bg-[#fffdf8] px-4 py-3 text-sm font-semibold text-ink/42">
                    이동 요청을 입력하면 컨디션 후보가 나타납니다.
                  </div>
                )}
              </section>

              {error ? (
                <p className="rounded-2xl border border-coral/40 bg-[#fff7fb] p-3 text-sm text-coral">
                  {error}
                </p>
              ) : null}
            </div>
          </article>

          <div className="grid gap-4 lg:self-start">
            <PlanPreview
              customWaypoints={customWaypoints}
              deletedWaypoints={deletedWaypoints}
              destinationText={destinationText}
              editedWaypoints={editedWaypoints}
              editingWaypointKey={editingWaypointKey}
              insights={previewInsights}
              isLoading={isPreviewLoading}
              onCustomWaypointAdd={handleCustomWaypointAdd}
              onCustomWaypointCategoryChange={handleCustomWaypointCategoryChange}
              onCustomWaypointChange={handleCustomWaypointChange}
              onCustomWaypointDelete={handleCustomWaypointDelete}
              onWaypointChange={handleWaypointChange}
              onWaypointDelete={handleWaypointDelete}
              onWaypointEditToggle={handleWaypointEditToggle}
              originText={originText}
              source={previewSource}
            />
            <button
              className="hidden min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-ink px-4 font-semibold text-white shadow-[0_12px_30px_rgba(23,26,24,0.14)] transition hover:bg-tide disabled:cursor-not-allowed disabled:bg-ink/45 lg:flex"
              type="submit"
              disabled={isLoading}
            >
              {primaryLabel}
              <ArrowRight size={18} aria-hidden />
            </button>
          </div>
        </section>

        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-ink/10 bg-white/92 px-5 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3 shadow-[0_-8px_24px_rgba(23,26,24,0.08)] backdrop-blur lg:hidden">
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
        ) : activeView === "result" && plan ? (
          <RouteResultPage
            plan={plan}
            onBackToPlanner={() => setActiveView("planner")}
          />
        ) : activeView === "taste" ? (
          <TastePage
            activeIndex={poiPreferenceIndex}
            isLoading={isPreferenceLoading}
            points={preferencePoints}
            status={preferenceStatus}
            votes={poiVotes}
            canLoadMore={preferenceRadiusMeters < MAX_PREFERENCE_RADIUS_METERS}
            onLoadNearby={loadNearbyPreferencePoints}
            onLoadMore={loadMorePreferencePoints}
            onReset={handlePoiReset}
            onSkip={handlePoiSkip}
            onVote={handlePoiVote}
          />
        ) : (
          <ProfilePage
            authUser={authUser}
            plan={plan}
            savedPlaceDraft={savedPlaceDraft}
            savedPlaceNotice={savedPlaceNotice}
            savedPlaces={savedPlaces}
            onAddSavedPlace={handleAddSavedPlace}
            onRemoveSavedPlace={handleRemoveSavedPlace}
            onSavedPlaceDraftChange={handleSavedPlaceDraftChange}
            onLogout={handleLogout}
            onOpenPlanner={() => setActiveView("planner")}
            onUseSavedPlace={handleUseSavedPlace}
          />
        )}
      </form>
    </main>
  );
}

function AuthLoading() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#fff9ed] px-5 text-ink">
      <section className="w-full max-w-sm rounded-[28px] bg-white p-6 shadow-[0_18px_50px_rgba(23,26,24,0.07)] ring-1 ring-ink/8">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#fde2ef] text-tide">
            <Sparkles size={20} aria-hidden />
          </span>
          <div>
            <p className="text-xs font-semibold text-tide">How's Your Day</p>
            <h1 className="mt-1 text-xl font-semibold">로그인 확인 중</h1>
          </div>
        </div>
      </section>
    </main>
  );
}

function AuthPage({
  form,
  isLoading,
  mode,
  status,
  onChange,
  onModeChange,
  onSubmit
}: {
  form: { email: string; password: string; nickname: string };
  isLoading: boolean;
  mode: AuthMode;
  status: string;
  onChange: (field: "email" | "password" | "nickname", value: string) => void;
  onModeChange: (mode: AuthMode) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const isSignup = mode === "signup";

  return (
    <main className="auth-shell min-h-screen overflow-x-hidden bg-[#fff9ed] px-4 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-[max(1.25rem,env(safe-area-inset-top))] text-ink [min-height:100svh] sm:px-5 sm:py-8">
      <form
        className="mx-auto flex min-h-[calc(100svh-2.5rem)] w-full max-w-md min-w-0 flex-col justify-start pt-4 sm:min-h-[calc(100vh-4rem)] sm:justify-center sm:pt-0"
        onSubmit={onSubmit}
      >
        <section className="w-full max-w-full overflow-hidden rounded-[28px] bg-white shadow-[0_18px_50px_rgba(23,26,24,0.07)] ring-1 ring-ink/8">
          <div className="bg-[#eef8f2] px-5 py-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-moss">How's Your Day</p>
                <h1 className="mt-1 text-[28px] font-semibold leading-tight [word-break:keep-all] sm:text-[30px]">
                  계정으로 계속하기
                </h1>
                <p className="mt-2 text-sm font-medium leading-6 text-ink/55 [word-break:keep-all]">
                  저장 장소와 취향 데이터를 계정에 연결합니다.
                </p>
              </div>
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-moss shadow-sm ring-1 ring-ink/8">
                <UserRound size={23} aria-hidden />
              </span>
            </div>
          </div>

          <div className="grid min-w-0 gap-5 p-5 pt-0">
            <div className="relative -mx-5 grid grid-cols-2 border-b border-ink/8 bg-white px-5">
              {[
                { id: "login" as const, label: "로그인" },
                { id: "signup" as const, label: "회원가입" }
              ].map((item) => (
                <button
                  className={`relative min-h-14 text-sm font-semibold transition-colors duration-200 ${
                    mode === item.id
                      ? "text-ink"
                      : "text-ink/42 hover:text-ink/70"
                  }`}
                  key={item.id}
                  type="button"
                  onClick={() => onModeChange(item.id)}
                >
                  {item.label}
                </button>
              ))}
              <span
                className={`pointer-events-none absolute bottom-0 left-5 h-0.5 w-[calc(50%-1.25rem)] rounded-full bg-tide transition-transform duration-300 ease-out ${
                  isSignup ? "translate-x-full" : "translate-x-0"
                }`}
              />
            </div>

            <div className="grid gap-3">
              <div className="relative min-h-[82px] overflow-visible">
                <div
                  className={`pointer-events-none absolute inset-0 transition duration-200 ease-out ${
                    isSignup
                      ? "-translate-y-1 opacity-0"
                      : "translate-y-0 opacity-100"
                  }`}
                >
                  <div className="flex min-h-[82px] items-start justify-center pt-9">
                    <p className="text-sm font-semibold text-ink/35">
                      또 오셨네요. 반가워요!
                    </p>
                  </div>
                </div>
                <div
                  className={`absolute inset-0 transition duration-200 ease-out ${
                    isSignup
                      ? "translate-y-0 opacity-100"
                      : "pointer-events-none translate-y-1 opacity-0"
                  }`}
                >
                  <AuthField
                    disabled={!isSignup}
                    icon={<UserRound size={16} aria-hidden />}
                    label="닉네임"
                    placeholder="예: 균이"
                    value={form.nickname}
                    onChange={(value) => onChange("nickname", value)}
                  />
                </div>
              </div>
              <AuthField
                icon={<Mail size={16} aria-hidden />}
                label="이메일"
                placeholder="user@example.com"
                type="email"
                value={form.email}
                onChange={(value) => onChange("email", value)}
              />
              <AuthField
                icon={<LockKeyhole size={16} aria-hidden />}
                label="비밀번호"
                placeholder="8자 이상"
                type="password"
                value={form.password}
                onChange={(value) => onChange("password", value)}
              />
            </div>

            {status ? (
              <p className="rounded-2xl bg-[#fff7fb] p-3 text-sm font-medium leading-6 text-coral ring-1 ring-coral/20">
                {status}
              </p>
            ) : null}

            <button
              className="flex min-h-12 w-full min-w-0 items-center justify-center gap-2 rounded-xl bg-ink px-4 font-semibold text-white shadow-[0_12px_30px_rgba(23,26,24,0.12)] transition hover:bg-tide disabled:cursor-not-allowed disabled:bg-ink/45"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? "확인 중" : isSignup ? "회원가입" : "로그인"}
              <ArrowRight size={18} aria-hidden />
            </button>
          </div>
        </section>
      </form>
    </main>
  );
}

function AuthField({
  disabled = false,
  icon,
  label,
  placeholder,
  type = "text",
  value,
  onChange
}: {
  disabled?: boolean;
  icon: ReactNode;
  label: string;
  placeholder: string;
  type?: "email" | "password" | "text";
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid min-w-0 gap-2">
      <span className="text-sm font-semibold text-ink/68">{label}</span>
      <span className="flex min-h-12 w-full min-w-0 max-w-full items-center gap-3 overflow-hidden rounded-xl bg-[#fffdf8] px-3 ring-1 ring-ink/10 transition focus-within:ring-tide/45">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#f7e8f0] text-tide">
          {icon}
        </span>
        <input
          className="min-w-0 flex-1 bg-transparent text-base font-semibold outline-none placeholder:text-ink/32"
          placeholder={placeholder}
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          required
        />
      </span>
    </label>
  );
}

function getAuthErrorMessage(caught: unknown) {
  const message = caught instanceof Error ? caught.message : "";
  if (message.includes("409")) {
    return "이미 가입된 이메일입니다.";
  }
  if (message.includes("401")) {
    return "이메일 또는 비밀번호를 다시 확인해주세요.";
  }
  if (message.includes("503")) {
    return "DB 연결이 필요합니다. Postgres를 실행한 뒤 다시 시도해주세요.";
  }
  if (message.includes("422")) {
    return "이메일, 비밀번호, 닉네임을 형식에 맞게 입력해주세요.";
  }
  return "인증 요청에 실패했습니다. 잠시 후 다시 시도해주세요.";
}

function buildSignupNickname(email: string) {
  const name = email.split("@")[0]?.trim();
  return name || "사용자";
}

function ServiceTopBar({
  activeView,
  onChange
}: {
  activeView: AppView;
  onChange: (view: AppView) => void;
}) {
  const items: Array<{ id: AppView; label: string; icon: LucideIcon }> = [
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

        <div
          className="grid shrink-0 grid-cols-3 rounded-2xl bg-white p-1 shadow-sm ring-1 ring-ink/8"
        >
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
  canLoadMore,
  isLoading,
  points,
  status,
  votes,
  onLoadNearby,
  onLoadMore,
  onReset,
  onSkip,
  onVote
}: {
  activeIndex: number;
  canLoadMore: boolean;
  isLoading: boolean;
  points: PreferencePoint[];
  status: string;
  votes: Record<string, PreferenceVote>;
  onLoadNearby: () => void;
  onLoadMore: () => void;
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

        {isLoading ? (
          <PreferenceDeckSkeleton />
        ) : (
          <PreferenceDeck
            activeIndex={activeIndex}
            canLoadMore={canLoadMore}
            points={points}
            votes={votes}
            onLoadMore={onLoadMore}
            onReset={onReset}
            onSkip={onSkip}
            onVote={onVote}
          />
        )}
      </div>

      {isLoading ? (
        <PreferenceMapSkeleton />
      ) : (
        <PreferenceMap points={points} votes={votes} />
      )}
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

function PreferenceDeckSkeleton() {
  return (
    <article className="order-1 overflow-hidden rounded-[24px] border border-ink/8 bg-white p-4 shadow-[0_18px_48px_rgba(23,26,24,0.07)]">
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-2">
          <div className="h-4 w-20 animate-pulse rounded-full bg-ink/8" />
          <div className="h-3 w-12 animate-pulse rounded-full bg-ink/8" />
        </div>
        <div className="h-9 w-9 animate-pulse rounded-xl bg-[#fff9ed]" />
      </div>
      <div className="mt-4 h-[430px] animate-pulse rounded-[24px] bg-[#fff9ed] p-3">
        <div className="h-full rounded-[22px] bg-white ring-1 ring-ink/7">
          <div className="h-48 rounded-t-[22px] bg-gradient-to-br from-[#fde2ef] via-[#fff5cf] to-[#ddf3eb]" />
          <div className="space-y-3 p-4">
            <div className="h-4 w-16 rounded-full bg-ink/8" />
            <div className="h-7 w-3/4 rounded-full bg-ink/10" />
            <div className="h-4 w-full rounded-full bg-ink/7" />
            <div className="h-4 w-2/3 rounded-full bg-ink/7" />
          </div>
        </div>
      </div>
    </article>
  );
}

function PreferenceEmptyDeck() {
  return (
    <article className="order-1 rounded-[24px] border border-ink/8 bg-white p-5 text-center shadow-[0_18px_48px_rgba(23,26,24,0.07)]">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#ddf3eb] text-moss">
        <MapPin size={22} aria-hidden />
      </span>
      <h2 className="mt-4 text-xl font-semibold">가져온 장소가 없어요</h2>
      <p className="mt-2 text-sm leading-6 text-ink/54 [word-break:keep-all]">
        내 주변 실제 장소를 불러오면 바로 스와이프를 시작할 수 있어요.
      </p>
    </article>
  );
}

function PreferenceCompleteDeck({
  canLoadMore,
  judgedCount,
  onLoadMore
}: {
  canLoadMore: boolean;
  judgedCount: number;
  onLoadMore: () => void;
}) {
  return (
    <article className="order-1 rounded-[24px] border border-ink/8 bg-white p-5 text-center shadow-[0_18px_48px_rgba(23,26,24,0.07)]">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#fde2ef] text-tide">
        <CheckCircle2 size={22} aria-hidden />
      </span>
      <h2 className="mt-4 text-xl font-semibold">이번 장소는 다 골랐어요</h2>
      <p className="mt-2 text-sm leading-6 text-ink/54 [word-break:keep-all]">
        {judgedCount}개의 선택이 저장됐고, 지도와 경로 후보에 취향으로 반영됩니다.
      </p>
      <button
        className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-[#ddf3eb] px-4 text-sm font-semibold text-moss transition active:scale-[0.98] disabled:bg-[#fff9ed] disabled:text-ink/36"
        type="button"
        onClick={onLoadMore}
        disabled={!canLoadMore}
      >
        <Plus size={17} aria-hidden />
        {canLoadMore ? "범위 넓혀 더 보기" : "최대 범위까지 확인"}
      </button>
    </article>
  );
}

function PreferenceMapSkeleton() {
  return (
    <section className="overflow-hidden rounded-[24px] bg-white shadow-[0_14px_40px_rgba(23,26,24,0.055)] ring-1 ring-ink/8">
      <div className="flex items-start justify-between gap-3 px-5 py-4">
        <div className="grid gap-2">
          <div className="h-3 w-16 animate-pulse rounded-full bg-ink/8" />
          <div className="h-6 w-24 animate-pulse rounded-full bg-ink/10" />
        </div>
        <div className="h-7 w-24 animate-pulse rounded-xl bg-[#ddf3eb]" />
      </div>
      <div className="relative mx-5 h-[300px] overflow-hidden rounded-2xl bg-[#fff9ed] ring-1 ring-ink/8">
        <div className="absolute inset-0 animate-pulse bg-[linear-gradient(90deg,rgba(23,26,24,0.05)_1px,transparent_1px),linear-gradient(rgba(23,26,24,0.05)_1px,transparent_1px)] bg-[size:36px_36px]" />
        <div className="absolute left-[22%] top-[28%] h-7 w-7 animate-pulse rounded-full bg-[#ddf3eb]" />
        <div className="absolute left-[52%] top-[50%] h-8 w-8 animate-pulse rounded-full bg-[#fde2ef]" />
        <div className="absolute left-[70%] top-[62%] h-7 w-7 animate-pulse rounded-full bg-[#ddf3eb]" />
      </div>
      <div className="p-5">
        <div className="h-16 animate-pulse rounded-2xl bg-[#fffdf8] ring-1 ring-ink/7" />
      </div>
    </section>
  );
}

function PreferenceMapEmpty() {
  return (
    <section className="overflow-hidden rounded-[24px] bg-white p-5 text-center shadow-[0_14px_40px_rgba(23,26,24,0.055)] ring-1 ring-ink/8">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#fff9ed] text-tide">
        <MapPinned size={22} aria-hidden />
      </span>
      <h2 className="mt-4 text-xl font-semibold">선호 지도를 준비 중이에요</h2>
      <p className="mt-2 text-sm leading-6 text-ink/54 [word-break:keep-all]">
        실제 장소를 불러온 뒤 선호/비선호를 고르면 지도 색이 바뀝니다.
      </p>
    </section>
  );
}

function ProfilePage({
  authUser,
  onAddSavedPlace,
  onLogout,
  onOpenPlanner,
  onRemoveSavedPlace,
  onSavedPlaceDraftChange,
  onUseSavedPlace,
  plan,
  savedPlaceDraft,
  savedPlaceNotice,
  savedPlaces
}: {
  authUser: AuthUser;
  plan: DailyPlan | null;
  savedPlaceDraft: { name: string; address: string; kind: SavedPlaceKind };
  savedPlaceNotice: string;
  savedPlaces: SavedPlaceEntry[];
  onAddSavedPlace: () => void;
  onLogout: () => void;
  onOpenPlanner: () => void;
  onRemoveSavedPlace: (id: string) => void;
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
        <AccountCard user={authUser} onLogout={onLogout} />
      </div>

      <div className="grid gap-4">
        <SavedPlacesPanel
          draft={savedPlaceDraft}
          notice={savedPlaceNotice}
          places={savedPlaces}
          onAdd={onAddSavedPlace}
          onDraftChange={onSavedPlaceDraftChange}
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

function AccountCard({
  user,
  onLogout
}: {
  user: AuthUser;
  onLogout: () => void;
}) {
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
                {user.nickname}
              </span>
            </span>
          </div>
          <button
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/78 text-ink/48 transition active:scale-95"
            type="button"
            aria-label="로그아웃"
            onClick={onLogout}
          >
            <LogOut size={17} aria-hidden />
          </button>
        </div>
      </div>

      <div className="grid gap-2 p-4">
        <AccountRow
          icon={<Mail size={16} aria-hidden />}
          label="이메일"
          value={user.email}
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

function SavedPlacesPanel({
  draft,
  notice,
  places,
  onAdd,
  onDraftChange,
  onRemove,
  onUse
}: {
  draft: { name: string; address: string; kind: SavedPlaceKind };
  notice: string;
  places: SavedPlaceEntry[];
  onAdd: () => void;
  onDraftChange: (field: "name" | "address" | "kind", value: string) => void;
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

      <SavedPlaceAddCard
        draft={draft}
        notice={notice}
        onAdd={onAdd}
        onDraftChange={onDraftChange}
      />

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

function SavedPlaceAddCard({
  draft,
  notice,
  onAdd,
  onDraftChange
}: {
  draft: { name: string; address: string; kind: SavedPlaceKind };
  notice: string;
  onAdd: () => void;
  onDraftChange: (field: "name" | "address" | "kind", value: string) => void;
}) {
  return (
    <div className="mt-4 rounded-2xl bg-[#fff9ed] p-3 ring-1 ring-ink/7">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-tide">주소 추가하기</p>
          <p className="mt-0.5 text-sm font-semibold text-ink/78">
            자주 쓰는 장소를 저장
          </p>
        </div>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fde2ef] text-tide">
          <Plus size={17} aria-hidden />
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-[1fr_1.45fr_120px]">
        <label className="grid gap-1 text-xs font-semibold text-ink/48">
          이름
          <input
            className="min-h-10 rounded-xl border border-ink/10 bg-white px-3 text-sm font-semibold text-ink outline-none transition placeholder:text-ink/32 focus:border-tide"
            value={draft.name}
            onChange={(event) => onDraftChange("name", event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAdd();
              }
            }}
            placeholder="집, 학교"
          />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-ink/48">
          주소 또는 장소명
          <input
            className="min-h-10 rounded-xl border border-ink/10 bg-white px-3 text-sm font-semibold text-ink outline-none transition placeholder:text-ink/32 focus:border-tide"
            value={draft.address}
            onChange={(event) => onDraftChange("address", event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAdd();
              }
            }}
            placeholder="성균관대학교 서울캠퍼스"
          />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-ink/48">
          분류
          <select
            className="min-h-10 rounded-xl border border-ink/10 bg-white px-3 text-sm font-semibold text-ink outline-none transition focus:border-tide"
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

      <div className="mt-3">
        <button
          className="flex min-h-10 w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 text-sm font-semibold text-white transition active:scale-[0.98]"
          type="button"
          onClick={onAdd}
        >
          <Plus size={16} aria-hidden />
          저장
        </button>
      </div>

      {notice ? (
        <p className="mt-3 rounded-xl bg-white px-3 py-2 text-xs font-semibold text-ink/55 ring-1 ring-ink/7">
          {notice}
        </p>
      ) : null}
    </div>
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
    <label className="relative block min-w-0 overflow-visible" htmlFor={id}>
      <span className="text-xs font-semibold text-ink/46">{label}</span>
      <input
        autoComplete="off"
        className="mt-1 block min-h-11 w-full min-w-0 rounded-xl border border-ink/10 bg-white px-3 text-sm font-semibold outline-none transition placeholder:text-ink/35 focus:border-tide"
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
  support?: string;
}) {
  return (
    <div className="flex min-w-0 items-start gap-2.5">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#ddf3eb] text-moss">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink/72">{label}</span>
        {support ? (
          <span className="mt-0.5 block break-words text-xs leading-5 text-ink/45">
            {support}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function RouteResultPage({
  plan,
  onBackToPlanner
}: {
  plan: DailyPlan;
  onBackToPlanner: () => void;
}) {
  const [selectedRouteId, setSelectedRouteId] = useState(plan.selected_route.id);

  useEffect(() => {
    setSelectedRouteId(plan.selected_route.id);
  }, [plan.selected_route.id]);

  const selectedRoute = useMemo(
    () => plan.routes.find((route) => route.id === selectedRouteId) ?? plan.selected_route,
    [plan.routes, plan.selected_route, selectedRouteId]
  );
  const selectedScore = useMemo(
    () => scoreForRoute(plan, selectedRoute),
    [plan, selectedRoute]
  );
  const selectedMap = useMemo(
    () => mapForSelectedRoute(plan.map_overlays, selectedRoute),
    [plan.map_overlays, selectedRoute]
  );

  return (
    <section className="grid gap-5 px-5 pb-8 pt-5 lg:grid-cols-[360px_minmax(0,1fr)] lg:items-start lg:px-0">
      <header className="rounded-[28px] bg-[#eef8f2] p-5 shadow-[0_16px_42px_rgba(23,26,24,0.055)] ring-1 ring-ink/8 lg:sticky lg:top-20">
        <button
          className="mb-4 inline-flex min-h-10 items-center gap-2 rounded-xl bg-white px-3 text-sm font-semibold text-ink/58 shadow-sm ring-1 ring-ink/8 transition hover:text-moss active:scale-[0.98]"
          type="button"
          onClick={onBackToPlanner}
        >
          <ArrowLeft size={16} aria-hidden />
          입력으로 돌아가기
        </button>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-moss">경로 추천</p>
            <h1 className="mt-1 text-[28px] font-semibold leading-tight [word-break:keep-all]">
              추천 경로 확인
            </h1>
            <p className="mt-2 text-sm leading-6 text-ink/55 [word-break:keep-all]">
              이동 조건과 컨디션을 반영한 결과입니다.
            </p>
          </div>
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-tide shadow-sm ring-1 ring-ink/8">
            <Navigation size={23} aria-hidden />
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <MiniStat label="이동" value={durationLabel(selectedRoute)} />
          <MiniStat label="걷기" value={`${selectedRoute.walking_minutes}분`} />
          <MiniStat label="추천 점수" value={`${selectedScore.comfort_score}점`} />
        </div>

        <button
          className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-white px-4 text-sm font-semibold text-moss shadow-sm ring-1 ring-moss/15 transition hover:bg-[#ddf3eb] active:scale-[0.99]"
          type="button"
          onClick={onBackToPlanner}
        >
          조건 다시 입력
        </button>
      </header>

      <div className="grid gap-4">
        <MobilePlanResult
          onSelectRoute={setSelectedRouteId}
          plan={plan}
          selectedMap={selectedMap}
          selectedRoute={selectedRoute}
          selectedScore={selectedScore}
        />
      </div>
    </section>
  );
}

function PlanPreview({
  customWaypoints,
  deletedWaypoints,
  destinationText,
  editedWaypoints,
  editingWaypointKey,
  insights,
  isLoading,
  onCustomWaypointAdd,
  onCustomWaypointCategoryChange,
  onCustomWaypointChange,
  onCustomWaypointDelete,
  onWaypointChange,
  onWaypointDelete,
  onWaypointEditToggle,
  originText,
  source
}: {
  customWaypoints: CustomWaypoint[];
  deletedWaypoints: Record<string, boolean>;
  destinationText: string;
  editedWaypoints: Record<string, string>;
  editingWaypointKey: string | null;
  insights: PreviewInsight[];
  isLoading: boolean;
  onCustomWaypointAdd: () => void;
  onCustomWaypointCategoryChange: (
    id: string,
    category: WaypointCategoryValue
  ) => void;
  onCustomWaypointChange: (id: string, value: string) => void;
  onCustomWaypointDelete: (id: string) => void;
  onWaypointChange: (key: string, value: string) => void;
  onWaypointDelete: (key: string) => void;
  onWaypointEditToggle: (key: string, value: string) => void;
  originText: string;
  source: string;
}) {
  const routeLabel = previewRouteLabel(insights, originText, destinationText);
  const cueInsights = previewCueInsights(insights);
  const visibleCueInsights = cueInsights
    .map((insight, index) => ({ insight, index }))
    .filter(({ insight, index }) => {
      const waypointKey = previewWaypointKey(insight, index);
      return !isEditableWaypointInsight(insight) || !deletedWaypoints[waypointKey];
    });
  const contextCueInsights = visibleCueInsights.filter(
    ({ insight }) => !isEditableWaypointInsight(insight)
  );
  const waypointCueInsights = visibleCueInsights.filter(
    ({ insight }) => isEditableWaypointInsight(insight)
  );

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
          {isLoading ? "읽는 중" : previewSourceLabel(source)}
        </span>
      </div>

      <div className="mt-4 rounded-2xl bg-[#fffdf8] p-3 ring-1 ring-ink/8">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fde2ef] text-tide">
            <Navigation size={18} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-ink/40">경로</p>
            <p className="mt-0.5 text-base font-semibold leading-6 [overflow-wrap:anywhere] [word-break:keep-all]">
              {routeLabel}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-2">
        {contextCueInsights.map(({ insight, index }) => (
          <PlannerCue
            icon={previewInsightIcon(insight)}
            key={`${insight.label}-${insight.value}-${index}`}
            label={insight.label}
            value={insight.value}
          />
        ))}
        {waypointCueInsights.map(({ insight, index }) => {
          const waypointKey = previewWaypointKey(insight, index);
          const value = editedWaypoints[waypointKey] ?? insight.value;

          return (
            <PlannerCue
              editable
              icon={previewInsightIcon(insight)}
              isEditing={editingWaypointKey === waypointKey}
              key={`${insight.label}-${insight.value}-${index}`}
              label={insight.label}
              onDelete={() => onWaypointDelete(waypointKey)}
              onEditToggle={() => onWaypointEditToggle(waypointKey, insight.value)}
              onValueChange={(nextValue) => onWaypointChange(waypointKey, nextValue)}
              strength={previewWaypointStrength(insight)}
              value={value}
            />
          );
        })}
        {customWaypoints.map((waypoint) => {
          const waypointKey = customWaypointKey(waypoint.id);
          const category = waypointCategoryOption(waypoint.category);
          const CategoryIcon = category.icon;
          return (
            <PlannerCue
              categoryOptions={WAYPOINT_CATEGORY_OPTIONS}
              categoryValue={waypoint.category}
              editable
              icon={<CategoryIcon size={15} aria-hidden />}
              isEditing={editingWaypointKey === waypointKey}
              key={waypointKey}
              label={category.label}
              onCategoryChange={(nextCategory) =>
                onCustomWaypointCategoryChange(waypoint.id, nextCategory)
              }
              onDelete={() => onCustomWaypointDelete(waypoint.id)}
              onEditToggle={() => onWaypointEditToggle(waypointKey, waypoint.value)}
              onValueChange={(nextValue) =>
                onCustomWaypointChange(waypoint.id, nextValue)
              }
              placeholder={category.placeholder}
              strength="strong"
              value={waypoint.value}
            />
          );
        })}
        <button
          className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#ddf3eb] px-3 text-sm font-semibold text-moss transition hover:bg-[#d2eee4] active:scale-[0.98]"
          type="button"
          onClick={onCustomWaypointAdd}
        >
          <Plus size={16} aria-hidden />
          경유 추가
        </button>
      </div>
    </section>
  );
}

function MobilePlanResult({
  onSelectRoute,
  plan,
  selectedMap,
  selectedRoute,
  selectedScore
}: {
  onSelectRoute: (routeId: string) => void;
  plan: DailyPlan;
  selectedMap: MapViewModel;
  selectedRoute: RouteCandidate;
  selectedScore: EmotionCost;
}) {
  const isRecommendedRoute = selectedRoute.id === plan.selected_route.id;
  const firstTradeoff = isRecommendedRoute ? plan.tradeoffs[0] : null;
  const usesKakaoPoi = selectedRoute.stops.some((stop) => stop.source_confidence === "kakao");
  const [feedbackChoice, setFeedbackChoice] = useState<"liked" | "disliked" | null>(null);
  const [feedbackPending, setFeedbackPending] = useState(false);

  useEffect(() => {
    setFeedbackChoice(null);
    setFeedbackPending(false);
  }, [selectedRoute.id]);

  async function handleFeedback(liked: boolean) {
    const nextChoice = liked ? "liked" : "disliked";
    setFeedbackChoice(nextChoice);
    setFeedbackPending(true);
    try {
      await sendRouteFeedback({
        route_id: selectedRoute.id,
        liked,
        emotion_primary: plan.emotion.primary,
        provider: selectedRoute.provider,
        reason: firstTradeoff?.reason ?? plan.explanation
      });
    } catch {
      setFeedbackChoice(null);
    } finally {
      setFeedbackPending(false);
    }
  }

  return (
    <>
      {plan.routes.length > 1 ? (
        <RouteList
          onSelect={onSelectRoute}
          plan={plan}
          routes={plan.routes}
          selectedRouteId={selectedRoute.id}
        />
      ) : null}

      <section className="rounded-2xl bg-white p-4 shadow-[0_12px_34px_rgba(23,26,24,0.045)] ring-1 ring-ink/8">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-moss">추천 경로</p>
            <h2 className="mt-1 break-words text-2xl font-semibold leading-tight">
              {routeDisplayName(selectedRoute)}
            </h2>
          </div>
          <div className="flex min-h-14 min-w-[4.5rem] shrink-0 flex-col items-center justify-center rounded-2xl bg-tide px-3 py-2 text-white">
            <span className="whitespace-nowrap text-[11px] font-semibold leading-none text-white/75">
              추천
            </span>
            <span className="mt-1 whitespace-nowrap text-[1.45rem] font-semibold leading-none tabular-nums">
              {selectedScore.comfort_score}점
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <MiniStat label="이동" value={durationLabel(selectedRoute)} />
          <MiniStat label="걷기" value={`${selectedRoute.walking_minutes}분`} />
          <MiniStat label="출처" value={routeProviderLabel(selectedRoute)} />
        </div>

        <MoodImpactCard
          plan={plan}
          selectedRoute={selectedRoute}
          selectedScore={selectedScore}
        />

        <RouteXaiCard
          cost={selectedScore}
          route={selectedRoute}
          tradeoff={firstTradeoff}
        />

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold transition active:scale-[0.99] ${
              feedbackChoice === "liked"
                ? "bg-moss text-white"
                : "bg-[#ddf3eb] text-moss"
            }`}
            disabled={feedbackPending}
            type="button"
            onClick={() => handleFeedback(true)}
          >
            {feedbackChoice === "liked" ? <CheckCircle2 size={16} aria-hidden /> : null}
            {feedbackChoice === "liked" ? "저장됨" : "이 길 괜찮았어요"}
          </button>
          <button
            className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold transition active:scale-[0.99] ${
              feedbackChoice === "disliked"
                ? "bg-tide text-white"
                : "bg-[#fde2ef] text-coral"
            }`}
            disabled={feedbackPending}
            type="button"
            onClick={() => handleFeedback(false)}
          >
            {feedbackChoice === "disliked" ? <CheckCircle2 size={16} aria-hidden /> : null}
            {feedbackChoice === "disliked" ? "저장됨" : "별로였어요"}
          </button>
        </div>
      </section>

      <KakaoMapPreview map={selectedMap} usesKakaoPoi={usesKakaoPoi} />

      <section className="grid gap-3">
        <SectionTitle icon={<HeartPulse size={18} aria-hidden />} title="감정 비용" />
        <EmotionalCostCard cost={selectedScore} />
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
        <TimelineList route={selectedRoute} />
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

function MoodImpactCard({
  plan,
  selectedRoute,
  selectedScore
}: {
  plan: DailyPlan;
  selectedRoute: RouteCandidate;
  selectedScore: EmotionCost;
}) {
  const impact = moodImpactSummary(plan, selectedRoute, selectedScore);

  return (
    <div className="mt-4 rounded-2xl bg-[#eef9f4] px-3 py-3 ring-1 ring-moss/10">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white text-moss ring-1 ring-moss/10">
            <HeartPulse size={16} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-moss">컨디션 반영</p>
            <p className="truncate text-sm font-semibold">{impact.title}</p>
          </div>
        </div>
        <span className="shrink-0 rounded-xl bg-white px-2.5 py-1 text-xs font-semibold text-ink/58 ring-1 ring-ink/7">
          {impact.badge}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink/66">{impact.detail}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {impact.chips.map((chip) => (
          <span
            className="rounded-xl bg-white px-2.5 py-1 text-xs font-semibold text-ink/58 ring-1 ring-ink/7"
            key={chip}
          >
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}

function RouteXaiCard({
  cost,
  route,
  tradeoff
}: {
  cost: EmotionCost;
  route: RouteCandidate;
  tradeoff: Tradeoff | null;
}) {
  const chips = routeXaiChips(cost, route);

  return (
    <div className="mt-4 rounded-2xl bg-[#fff9ed] p-3 ring-1 ring-ink/6">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Zap className="text-coral" size={16} aria-hidden />
        왜 추천했나요
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {chips.map((chip) => (
          <span
            className="inline-flex min-h-8 items-center gap-1.5 rounded-xl bg-white px-2.5 text-xs font-semibold text-ink/64 ring-1 ring-ink/7"
            key={chip}
          >
            <CheckCircle2 size={13} aria-hidden className="text-moss" />
            {chip}
          </span>
        ))}
      </div>
      <p className="mt-3 text-sm leading-6 text-ink/68">
        {tradeoff?.reason ?? routeXaiFallbackSummary(cost, route)}
      </p>
    </div>
  );
}

function moodImpactSummary(
  plan: DailyPlan,
  selectedRoute: RouteCandidate,
  selectedScore: EmotionCost
) {
  const fastestRoute = plan.routes.reduce((best, route) =>
    routeDurationMinutes(route) < routeDurationMinutes(best) ? route : best
  , plan.routes[0] ?? selectedRoute);
  const fastestScore = scoreForRoute(plan, fastestRoute);
  const selectedDuration = routeDurationMinutes(selectedRoute);
  const fastestDuration = routeDurationMinutes(fastestRoute);
  const durationDelta = selectedDuration - fastestDuration;
  const emotionalDelta =
    selectedScore.total_emotional_cost - fastestScore.total_emotional_cost;
  const emphasis = emotionEmphasis(plan.emotion);
  const conditionName = emotionDisplayName(plan.emotion);
  const hasRecoveryStop = selectedRoute.stops.some(
    (stop) => stop.category === "recovery" || stop.emotion_tags.includes("recovery")
  );

  let detail = "현재 컨디션에서 시간과 감정 비용의 균형이 가장 안정적인 후보를 골랐어요.";
  if (plan.emotion.time_pressure_tolerance === "high") {
    detail =
      durationDelta <= 0
        ? "시간 압박이 높게 감지되어 우회와 회복 경유보다 빠른 도착을 더 크게 봤어요."
        : "시간 압박을 반영했지만, 필요한 경유와 감정 비용까지 함께 비교했어요.";
  } else if (durationDelta > 0 && emotionalDelta < 0) {
    detail = `${fastestDuration}분 후보보다 ${durationDelta}분 더 걸리지만 감정 비용을 ${Math.abs(
      emotionalDelta
    )}점 낮춰서 선택했어요.`;
  } else if (hasRecoveryStop) {
    detail = "회복 필요가 높게 잡혀서, 목적지까지 바로 가는 길뿐 아니라 쉬어갈 수 있는 후보도 함께 비교했어요.";
  } else if (selectedScore.crowd_cost >= 14) {
    detail = "혼잡 부담을 크게 계산해서 사람 많은 구간의 비용이 점수에 드러나도록 했어요.";
  } else if (selectedScore.walking_cost >= 12 || selectedScore.fatigue_cost >= 10) {
    detail = "피로와 보행 부담을 크게 계산해서 오래 걷는 후보가 불리해지도록 했어요.";
  }

  const chips = [
    ...emphasis,
    hasRecoveryStop ? "회복 경유 검토" : "직접 이동 비교",
    `감정 비용 ${selectedScore.total_emotional_cost}`
  ];

  return {
    badge: conditionName,
    chips: Array.from(new Set(chips)).slice(0, 4),
    detail,
    title: `${conditionName} 기준으로 점수 조정`
  };
}

function emotionDisplayName(emotion: DailyPlan["emotion"]) {
  if (emotion.time_pressure_tolerance === "high") {
    return "바쁨";
  }
  if (emotion.recovery_need === "high") {
    return emotion.primary === "tired" ? "피곤" : "휴식";
  }
  if (emotion.primary === "tired") {
    return "피곤";
  }
  if (emotion.primary === "anxious") {
    return "불안";
  }
  if (emotion.primary === "hurried") {
    return "바쁨";
  }
  return "안정";
}

function emotionEmphasis(emotion: DailyPlan["emotion"]) {
  const chips: string[] = [];
  if (emotion.time_pressure_tolerance === "high") {
    chips.push("시간 우선");
  }
  if (emotion.primary === "tired" || emotion.walking_tolerance === "low") {
    chips.push("피로/걷기 민감");
  }
  if (emotion.primary === "anxious" || emotion.crowd_tolerance === "low") {
    chips.push("혼잡 민감");
  }
  if (emotion.transfer_tolerance === "low") {
    chips.push("환승 부담");
  }
  if (emotion.recovery_need === "high") {
    chips.push("회복 필요");
  }
  return chips.length ? chips : ["균형 비교"];
}

function routeXaiChips(cost: EmotionCost, route: RouteCandidate) {
  const factors = [
    ["혼잡", cost.crowd_cost],
    ["피로", cost.fatigue_cost],
    ["걷기", cost.walking_cost],
    ["시간", cost.time_pressure_cost],
    ["환승", cost.transfer_cost]
  ] as const;
  const topFactors = factors
    .filter(([, value]) => value > 0)
    .sort(([, left], [, right]) => right - left)
    .slice(0, 2)
    .map(([label, value]) => `${label} +${value}`);
  const chips = [
    ...topFactors,
    route.stops.length > 0 ? `경유 ${route.stops.length}곳` : "직접 이동",
    routeProviderLabel(route)
  ];

  if (chips.length < 3) {
    chips.unshift(`감정 비용 ${cost.total_emotional_cost}`);
  }

  return chips.slice(0, 4);
}

function routeXaiFallbackSummary(cost: EmotionCost, route: RouteCandidate) {
  const topCost = Math.max(
    cost.crowd_cost,
    cost.fatigue_cost,
    cost.walking_cost,
    cost.time_pressure_cost,
    cost.transfer_cost
  );

  if (topCost === cost.crowd_cost && topCost > 0) {
    return "혼잡 부담을 계산에 넣고, 현재 조건에서 가장 무난한 이동을 골랐어요.";
  }
  if (topCost === cost.fatigue_cost && topCost > 0) {
    return "피로도를 반영해서 걷기와 이동 부담이 큰 경로를 피했어요.";
  }
  if (route.stops.length > 0) {
    return "필요한 경유지를 포함하면서 이동 부담이 커지지 않는 후보를 골랐어요.";
  }
  return "이동 시간과 감정 비용을 함께 비교해서 균형이 좋은 후보를 골랐어요.";
}

function scoreForRoute(plan: DailyPlan, route: RouteCandidate) {
  return (
    (plan.route_scores ?? []).find((score) => score.route_id === route.id) ??
    (route.id === plan.emotional_cost.route_id ? plan.emotional_cost : plan.score)
  );
}

function mapForSelectedRoute(map: MapViewModel, route: RouteCandidate): MapViewModel {
  return {
    ...map,
    selected_route_id: route.id,
    markers: route.stops.map((stop, index) => ({
      id: `marker-${route.id}-${stop.id}`,
      type: "stop",
      lat: stop.lat,
      lng: stop.lng,
      label: stop.name,
      badge: `${index + 1}`
    })),
    polylines: map.polylines.map((polyline) => ({
      ...polyline,
      selected: polyline.route_id === route.id
    }))
  };
}

function buildRouteTimeline(route: RouteCandidate): TimelineItem[] {
  const startMinutes = 14 * 60;
  const routeMinutes = routeDurationMinutes(route);
  const travelStep = Math.max(8, Math.floor(routeMinutes / Math.max(1, route.stops.length + 1)));
  let currentMinutes = startMinutes;
  const timeline: TimelineItem[] = [
    {
      time: formatTimelineMinutes(currentMinutes),
      label: `출발지에서 ${routeProviderLabel(route)} 경로로 이동을 시작해요.`,
      type: "depart"
    }
  ];

  route.stops.forEach((stop) => {
    currentMinutes += travelStep;
    timeline.push({
      time: formatTimelineMinutes(currentMinutes),
      label: stopTimelineLabel(stop),
      type: "task",
      required: stop.required
    });
    currentMinutes += 10;
  });

  currentMinutes += travelStep;
  timeline.push({
    time: formatTimelineMinutes(currentMinutes),
    label: "최종 목적지에 도착합니다.",
    type: "arrive"
  });

  return timeline;
}

function stopTimelineLabel(stop: PoiCandidate) {
  if (stop.category === "recovery") {
    return `${stop.name}에서 잠깐 회복할 수 있어요.`;
  }
  if (stop.category === "errand") {
    return `${stop.name}에 들러 필요한 일을 처리합니다.`;
  }
  if (stop.category === "print") {
    return `${stop.name}에서 인쇄 일을 처리합니다.`;
  }
  if (stop.category === "clinic") {
    return `${stop.name} 방문을 동선에 반영합니다.`;
  }
  return `${stop.name}에 들릅니다.`;
}

function formatTimelineMinutes(totalMinutes: number) {
  const hours = Math.floor(totalMinutes / 60) % 24;
  const minutes = totalMinutes % 60;
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;
}

function TimelineList({ route }: { route: RouteCandidate }) {
  const timeline = buildRouteTimeline(route);

  return (
    <ol className="grid gap-2">
      {timeline.map((item) => (
        <li
          className="grid grid-cols-[58px_1fr] gap-3 rounded-2xl bg-white p-3 shadow-[0_8px_22px_rgba(23,26,24,0.035)] ring-1 ring-ink/8"
          key={`${item.time}-${item.label}`}
        >
          <span className="rounded-xl bg-[#fde2ef] px-2 py-2 text-center text-sm font-semibold text-tide">
            {item.time}
          </span>
          <span className="min-w-0 text-sm leading-6 text-ink/72">
            <span className="mb-1 flex flex-wrap items-center gap-1.5">
              <span className="block text-xs font-semibold uppercase tracking-[0.1em] text-ink/38">
                {timelineTypeLabel(item.type)}
              </span>
              {item.type === "task" ? (
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    item.required === true
                      ? "bg-[#fde2ef] text-tide"
                      : "bg-[#ddf3eb] text-moss"
                  }`}
                >
                  {item.required === true ? "필수" : "참고"}
                </span>
              ) : null}
            </span>
            {item.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

function timelineTypeLabel(type: string) {
  if (type === "depart") {
    return "출발";
  }
  if (type === "arrive") {
    return "도착";
  }
  if (type === "task") {
    return "경유";
  }
  return userFacingCategoryLabel(type);
}

function RouteList({
  onSelect,
  plan,
  routes,
  selectedRouteId
}: {
  onSelect: (routeId: string) => void;
  plan: DailyPlan;
  routes: RouteCandidate[];
  selectedRouteId: string;
}) {
  return (
    <section className="rounded-2xl bg-white p-3 shadow-[0_12px_34px_rgba(23,26,24,0.04)] ring-1 ring-ink/8">
      <div className="mb-2 flex items-center gap-2 px-1">
        <Navigation size={16} aria-hidden className="text-moss" />
        <h2 className="text-sm font-semibold text-ink/68">경로 선택</h2>
      </div>
      <div className="grid gap-2">
        {routes.map((route, index) => {
          const selected = route.id === selectedRouteId;
          const title = routeOptionTitle(route, index);
          const score = scoreForRoute(plan, route);

          return (
            <button
              aria-pressed={selected}
              className={`flex min-h-14 w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left ring-1 transition active:scale-[0.99] ${
                selected
                  ? "bg-[#fff1f7] text-ink ring-tide/35"
                  : "bg-[#fffdf8] text-ink/70 ring-ink/7 hover:bg-[#fff9ed] hover:ring-moss/20"
              }`}
              key={route.id}
              onClick={() => onSelect(route.id)}
              type="button"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{title}</span>
                <span className="mt-0.5 block text-xs font-medium text-ink/42">
                  {score.comfort_score}점 · {durationLabel(route)} · 걷기 {route.walking_minutes}분
                </span>
              </span>
              <span
                className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-semibold ${
                  selected ? "bg-tide text-white" : "bg-[#ddf3eb] text-moss"
                }`}
              >
                {selected ? "선택됨" : "보기"}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function PlannerCue({
  categoryOptions,
  categoryValue,
  editable = false,
  icon,
  isEditing = false,
  label,
  onCategoryChange,
  onDelete,
  onEditToggle,
  onValueChange,
  placeholder = "예: 스타벅스, 조용한 카페",
  strength = "none",
  value
}: {
  categoryOptions?: typeof WAYPOINT_CATEGORY_OPTIONS;
  categoryValue?: WaypointCategoryValue;
  editable?: boolean;
  icon: ReactNode;
  isEditing?: boolean;
  label: string;
  onCategoryChange?: (category: WaypointCategoryValue) => void;
  onDelete?: () => void;
  onEditToggle?: () => void;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  strength?: "strong" | "weak" | "none";
  value?: string;
}) {
  const strengthMeta = waypointStrengthMeta(strength);
  return (
    <div
      className={`flex min-h-12 items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-ink/64 ring-1 ${strengthMeta.containerClass}`}
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#fde2ef] text-tide/80">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="block text-[11px] font-semibold text-ink/38">{label}</span>
          {strengthMeta.label ? (
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${strengthMeta.badgeClass}`}>
              {strengthMeta.label}
            </span>
          ) : null}
        </span>
        {isEditing ? (
          <span className="mt-2 grid gap-2">
            {categoryOptions && categoryValue && onCategoryChange ? (
              <span className="grid grid-cols-5 gap-1.5">
                {categoryOptions.map((option) => {
                  const selected = categoryValue === option.value;
                  const Icon = option.icon;
                  return (
                    <button
                      className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[10px] font-semibold transition active:scale-95 ${
                        selected
                          ? "bg-[#fde2ef] text-tide ring-1 ring-tide/35"
                          : "bg-white text-ink/52 ring-1 ring-ink/8 hover:bg-[#fff9ed]"
                      }`}
                      key={option.value}
                      type="button"
                      onClick={() => {
                        onCategoryChange(option.value);
                      }}
                    >
                      <Icon size={15} aria-hidden />
                      <span>{option.label}</span>
                    </button>
                  );
                })}
              </span>
            ) : null}
            <input
              className="block min-h-9 w-full min-w-0 rounded-xl border border-ink/10 bg-white px-3 text-xs font-semibold text-ink outline-none transition placeholder:text-ink/32 focus:border-tide"
              placeholder={placeholder}
              value={value ?? ""}
              onChange={(event) => onValueChange?.(event.target.value)}
            />
          </span>
        ) : (
          <span className="block text-sm font-semibold leading-5 text-ink/72 [overflow-wrap:anywhere]">
            {value ?? label}
          </span>
        )}
      </span>
      {editable ? (
        <span className="flex shrink-0 gap-1">
          <button
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#ddf3eb] text-moss transition hover:bg-[#d2eee4] active:scale-95"
            type="button"
            onClick={onEditToggle}
            aria-label={`${label} 수정`}
          >
            {isEditing ? (
              <CheckCircle2 size={15} aria-hidden />
            ) : (
              <PencilLine size={15} aria-hidden />
            )}
          </button>
          <button
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#fde2ef] text-tide transition hover:bg-[#f7d4e7] active:scale-95"
            type="button"
            onClick={onDelete}
            aria-label={`${label} 삭제`}
          >
            <Trash2 size={15} aria-hidden />
          </button>
        </span>
      ) : null}
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
  if (points.length === 0) {
    return <PreferenceMapEmpty />;
  }

  const visiblePoints = points;
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
  canLoadMore,
  points,
  votes,
  onLoadMore,
  onReset,
  onSkip,
  onVote
}: {
  activeIndex: number;
  canLoadMore: boolean;
  points: PreferencePoint[];
  votes: Record<string, PreferenceVote>;
  onLoadMore: () => void;
  onReset: () => void;
  onSkip: () => void;
  onVote: (id: string, vote: PreferenceVote) => void;
}) {
  const visiblePoints = points.filter((point) => !votes[point.id]);
  const active = visiblePoints[activeIndex % Math.max(1, visiblePoints.length)];
  const judgedPoints = points.filter(
    (item) => votes[item.id] === "like" || votes[item.id] === "dislike"
  );
  const liked = points.filter((item) => votes[item.id] === "like");
  const disliked = points.filter((item) => votes[item.id] === "dislike");
  const affected = points.filter(
    (item) => resolvePreferenceSignal(item, points, votes) !== null
  );
  const [dragStartX, setDragStartX] = useState<number | null>(null);
  const [dragX, setDragX] = useState(0);
  const [leavingVote, setLeavingVote] = useState<PreferenceVote | null>(null);

  useEffect(() => {
    setDragStartX(null);
    setDragX(0);
    setLeavingVote(null);
  }, [active?.id]);

  if (points.length === 0) {
    return <PreferenceEmptyDeck />;
  }

  if (!active) {
    return (
      <PreferenceCompleteDeck
        canLoadMore={canLoadMore}
        judgedCount={judgedPoints.length}
        onLoadMore={onLoadMore}
      />
    );
  }

  const Icon = active.icon;

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
          {active.placeUrl ? (
            <a
              className="absolute right-4 top-[124px] z-20 flex h-9 w-9 items-center justify-center rounded-xl bg-white/95 text-tide shadow-[0_8px_20px_rgba(23,26,24,0.10)] ring-1 ring-tide/20 transition hover:bg-[#fff7fb] active:scale-95"
              href={active.placeUrl}
              rel="noreferrer"
              target="_blank"
              aria-label={`${active.name} 자세히 보기`}
              onClick={(event) => event.stopPropagation()}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <ExternalLink size={16} aria-hidden />
            </a>
          ) : null}
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
          <div className="flex items-start gap-3 p-4 pb-3">
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

          <div className="space-y-2 px-4 pb-3">
            {preferenceInfoRows(active).map((row) => (
              <div
                className="flex items-start justify-between gap-3 rounded-xl bg-[#fffdf8] px-3 py-2 text-xs leading-5 text-ink/58 ring-1 ring-ink/6"
                key={row.label}
              >
                <span className="shrink-0 font-semibold text-ink/42">{row.label}</span>
                <span className="min-w-0 text-right [word-break:keep-all]">{row.value}</span>
              </div>
            ))}
          </div>

          <div className="px-4 pb-2">
            <p className="line-clamp-2 rounded-xl bg-[#eef8f4] px-3 py-2 text-xs font-medium leading-5 text-moss [word-break:keep-all]">
              {preferenceLearningHint(active)}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 px-4 pb-3">
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

      <div className="mt-3 grid justify-items-center gap-2">
        <div className="flex justify-center gap-1">
          {visiblePoints.map((item, index) => (
            <span
              className={`h-1.5 rounded-full transition-all ${
                index === activeIndex % visiblePoints.length ? "w-5 bg-tide" : "w-1.5 bg-ink/14"
              }`}
              key={item.id}
            />
          ))}
        </div>
        <div className="flex flex-wrap justify-center gap-1.5 text-[11px] font-semibold text-ink/48">
          <span className="whitespace-nowrap rounded-full bg-[#ddf3eb] px-2 py-1 text-moss">
            선호 {liked.length}
          </span>
          <span className="whitespace-nowrap rounded-full bg-[#fde2ef] px-2 py-1 text-tide">
            비선호 {disliked.length}
          </span>
          <span className="whitespace-nowrap rounded-full bg-[#fff9ed] px-2 py-1">
            반영 {affected.length}
          </span>
        </div>
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
      className={`relative h-28 overflow-hidden ${preferenceVisualTone(point)} text-white`}
    >
      <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.20),transparent_45%),radial-gradient(circle_at_78%_22%,rgba(255,255,255,0.30),transparent_28%)]" />
      <div className="absolute -bottom-12 -right-10 h-36 w-36 rounded-full bg-white/18" />
      <div className="absolute left-5 top-5 flex items-center gap-2 rounded-2xl bg-white/22 px-3 py-2 text-xs font-semibold backdrop-blur">
        <Icon size={16} aria-hidden />
        {point.kind}
      </div>
      <div className="absolute bottom-5 left-5 text-xs font-semibold text-white/72">
        내 주변 실제 장소
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

function savedPlaceRecordToEntry(record: SavedPlaceRecord): SavedPlaceEntry {
  return {
    id: record.id,
    name: record.name,
    address: record.address,
    kind: isSavedPlaceKind(record.kind) ? record.kind : "favorite",
    lat: record.lat,
    lng: record.lng,
    updatedAt: record.updated_at
  };
}

function placePreferenceRecordsToVotes(
  records: PlacePreferenceRecord[]
): Record<string, PreferenceVote> {
  return records.reduce<Record<string, PreferenceVote>>((votes, record) => {
    if (record.preference === "like" || record.preference === "dislike") {
      votes[placePreferenceRecordKey(record)] = record.preference;
    }
    return votes;
  }, {});
}

function placePreferenceRecordKey(record: PlacePreferenceRecord) {
  if (record.poi_provider_id) {
    return record.poi_provider_id;
  }
  const lat = typeof record.lat === "number" ? record.lat.toFixed(5) : "na";
  const lng = typeof record.lng === "number" ? record.lng.toFixed(5) : "na";
  return `poi-${record.name}-${lat}-${lng}`;
}

function normalizePlaceText(value: string) {
  return value.toLowerCase().replace(/\s+/g, "");
}

function resetPlannerScroll() {
  if (document.scrollingElement) {
    document.scrollingElement.scrollLeft = 0;
  }
  document.documentElement.scrollLeft = 0;
  document.body.scrollLeft = 0;
  window.scrollTo({
    left: 0,
    top: 0,
    behavior: "auto"
  });

  window.requestAnimationFrame(() => {
    if (document.scrollingElement) {
      document.scrollingElement.scrollLeft = 0;
    }
    document.documentElement.scrollLeft = 0;
    document.body.scrollLeft = 0;
  });
}

function buildQuickSavedPlaces(places: SavedPlaceEntry[]) {
  const order: SavedPlaceKind[] = ["home", "school", "work", "favorite"];
  const usedAddresses = new Set<string>();
  const sorted = [...places].sort((a, b) => {
    const kindDelta = order.indexOf(a.kind) - order.indexOf(b.kind);
    if (kindDelta !== 0) {
      return kindDelta;
    }
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });

  return sorted
    .filter((place) => {
      const key = normalizePlaceText(place.address);
      if (!key || usedAddresses.has(key)) {
        return false;
      }
      usedAddresses.add(key);
      return true;
    })
    .slice(0, 5);
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
    address: candidate.address ?? null,
    categoryName: candidate.category_name ?? null,
    categoryGroupName: candidate.category_group_name ?? null,
    phone: candidate.phone ?? null,
    placeUrl: candidate.place_url ?? null,
    distanceMeters: candidate.distance_meters,
    icon: iconForLandmark(candidate.landmark_type, candidate.category),
    tags: pointTags(candidate),
    lat: candidate.lat,
    lng: candidate.lng,
    source: sourceLabel(candidate.source_confidence)
  };
}

function mergePreferencePoints(
  current: PreferencePoint[],
  next: PreferencePoint[]
) {
  const pointsById = new Map(current.map((point) => [point.id, point]));
  for (const point of next) {
    pointsById.set(point.id, point);
  }
  return Array.from(pointsById.values());
}

function formatDistanceMeters(distanceMeters: number) {
  if (distanceMeters >= 1000) {
    return `${(distanceMeters / 1000).toFixed(1)}km`;
  }
  return `${distanceMeters}m`;
}

function createPointId(candidate: PoiCandidate) {
  return candidate.provider_id
    ? `poi-${candidate.provider_id}`
    : `poi-${candidate.id}-${candidate.lat.toFixed(5)}-${candidate.lng.toFixed(5)}`;
}

function iconForLandmark(landmarkType: string, category: string): LucideIcon {
  const normalized = `${landmarkType} ${category}`.toLowerCase();
  if (
    normalized.includes("cafe") ||
    normalized.includes("coffee") ||
    normalized.includes("bakery")
  ) {
    return Coffee;
  }
  if (
    normalized.includes("park") ||
    normalized.includes("green") ||
    normalized.includes("walk")
  ) {
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
  if (normalized.includes("bakery")) {
    return "빵집";
  }
  if (normalized.includes("culture")) {
    return "문화";
  }
  if (normalized.includes("food") || normalized.includes("restaurant")) {
    return "음식점";
  }
  if (normalized.includes("walk")) {
    return "산책";
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
  if (normalized.includes("errand")) {
    return "들를 곳";
  }
  if (normalized.includes("print")) {
    return "인쇄";
  }
  if (normalized.includes("clinic")) {
    return "병원";
  }
  if (normalized.includes("commercial")) {
    return "상점";
  }
  return userFacingCategoryLabel(candidate.category || candidate.landmark_type);
}

function userFacingCategoryLabel(value: string | null | undefined) {
  if (!value) {
    return "장소";
  }
  const normalized = value.toLowerCase();
  const labels: Record<string, string> = {
    errand: "들를 곳",
    recovery: "쉴 곳",
    print: "인쇄",
    clinic: "병원",
    commercial: "상점",
    medical: "의료",
    cafe: "카페",
    bakery: "빵집",
    bookstore: "서점",
    culture: "문화",
    library: "도서관",
    park: "공원",
    walk: "산책",
    transit_hub: "교통",
    university: "학교",
    school: "학교",
    restaurant: "음식점",
    depart: "출발",
    arrive: "도착",
    task: "경유"
  };
  return labels[normalized] ?? value;
}

function pointDetail(candidate: PoiCandidate) {
  const source = sourceLabel(candidate.source_confidence);
  const distance =
    candidate.distance_meters === null
      ? "주변 후보"
      : `약 ${Math.round(candidate.distance_meters)}m`;

  return `${source} · ${distance}`;
}

function preferenceInfoRows(point: PreferencePoint) {
  return [
    { label: "분류", value: compactCategoryPath(point) },
    { label: "위치", value: compactAddress(point.address) }
  ].filter(Boolean) as Array<{ label: string; value: string }>;
}

function compactCategoryPath(point: PreferencePoint) {
  const category = point.categoryName || point.categoryGroupName || point.kind;
  const parts = category
    .split(">")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length >= 2) {
    return parts.slice(-2).join(" · ");
  }
  return parts[0] || point.kind;
}

function compactAddress(address: string | null) {
  if (!address) {
    return "주소 정보 없음";
  }
  const parts = address.split(/\s+/).filter(Boolean);
  return parts.length > 4 ? parts.slice(0, 4).join(" ") : address;
}

function preferenceLearningHint(point: PreferencePoint) {
  const distance =
    point.distanceMeters === null ? "내 주변 후보" : `현재 위치에서 약 ${Math.round(point.distanceMeters)}m`;
  return `${distance}. 선택하면 비슷한 ${point.kind} 장소를 경로 후보에 더 잘 반영해요.`;
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
  if (tag === "errand" || tag === "practical") {
    return "실용";
  }
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

  const nearbyCandidate = await searchFirstLocationCandidate(
    rawText.trim(),
    currentLocation
  );
  if (nearbyCandidate) {
    return {
      location: locationFromCandidate(nearbyCandidate),
      source: "nearby-search"
    };
  }

  return geocodeLocation(rawText.trim());
}

function locationFromCandidate(candidate: LocationCandidate): Location {
  return {
    label: candidate.label,
    lat: candidate.lat,
    lng: candidate.lng
  };
}

async function searchFirstLocationCandidate(
  query: string,
  currentLocation: Location | null = null
) {
  const trimmed = query.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const result = await searchLocations(trimmed, 3, currentLocation);
    return result.candidates[0] ?? null;
  } catch {
    return null;
  }
}

function shouldSearchLocationInput(query: string) {
  return query.length >= 2 || ["집", "학교", "회사"].includes(query);
}

function buildMoodCandidates(input: string, suggestedLabels: string[] = []) {
  const normalized = input.toLowerCase();
  const suggestedSet = new Set(
    suggestedLabels.filter((label) => MOOD_PRESETS.some((mood) => mood.label === label))
  );
  const suggestedIsOnlyDefault =
    suggestedSet.size > 0 &&
    Array.from(suggestedSet).every((label) => DEFAULT_MOOD_LABELS.includes(label));
  const scored = MOOD_PRESETS.map((mood, index) => {
    const keywordScore = mood.keywords.reduce(
      (score, keyword) => score + (normalized.includes(keyword.toLowerCase()) ? 4 : 0),
      0
    );
    const suggestedIndex = suggestedLabels.indexOf(mood.label);
    const suggestedScore = suggestedIndex >= 0 ? 40 - suggestedIndex : 0;
    return {
      mood,
      score: suggestedScore + keywordScore,
      keywordScore,
      index
    };
  });
  const hasKeywordSignal = scored.some((item) => item.keywordScore > 0);
  const hasLlmSignal = suggestedSet.size > 0 && !suggestedIsOnlyDefault;

  if (!hasKeywordSignal && !hasLlmSignal) {
    return [];
  }

  const selected = scored
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, 4)
    .map((item) => item.mood);
  const labels = selected.map((mood) => mood.label);

  DEFAULT_MOOD_LABELS.forEach((label) => {
    if (labels.length < 4 && !labels.includes(label)) {
      const mood = MOOD_PRESETS.find((item) => item.label === label);
      if (mood) {
        selected.push(mood);
        labels.push(label);
      }
    }
  });

  return selected.slice(0, 4);
}

function buildLocalMoodLabels(input: string) {
  const normalized = input.toLowerCase();
  const scored = MOOD_PRESETS.map((mood, index) => ({
    label: mood.label,
    score: mood.keywords.reduce(
      (score, keyword) => score + (normalized.includes(keyword.toLowerCase()) ? 1 : 0),
      0
    ),
    index
  })).filter((item) => item.score > 0);
  const labels = scored
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((item) => item.label);

  if (labels.length === 0) {
    return [];
  }

  DEFAULT_MOOD_LABELS.forEach((label) => {
    if (!labels.includes(label)) {
      labels.push(label);
    }
  });
  return labels.slice(0, 4);
}

function ensureActiveMoodCandidate(
  candidates: typeof MOOD_PRESETS,
  activeMood: string
) {
  if (candidates.some((mood) => mood.label === activeMood)) {
    return candidates;
  }

  const selected = MOOD_PRESETS.find((mood) => mood.label === activeMood);
  if (!selected) {
    return candidates;
  }

  return [...candidates.slice(0, 3), selected];
}

function defaultPreviewInsights(): PreviewInsight[] {
  return [
    { label: "이동", value: "출발지와 도착지 확인", kind: "route", strength: "none" },
    { label: "시간", value: "감지된 시간 조건 없음", kind: "time", strength: "none" },
    { label: "컨디션", value: "컨디션 조건 없음", kind: "mood", strength: "none" }
  ];
}

function previewRouteLabel(
  insights: PreviewInsight[],
  originText: string,
  destinationText: string
) {
  const formRouteLabel = buildFormRouteLabel(originText, destinationText);
  if (formRouteLabel) {
    return formRouteLabel;
  }

  const routeInsight = insights.find(
    (insight) => insight.kind === "route" && insight.value.includes("→")
  );
  return routeInsight?.value ?? `${originText || "출발지"} → ${destinationText || "도착지"}`;
}

function buildFormRouteLabel(originText: string, destinationText: string) {
  const origin = originText.trim();
  const destination = destinationText.trim();
  if (!origin && !destination) {
    return "";
  }
  return `${origin || "출발지"} → ${destination || "도착지"}`;
}

function previewCueInsights(insights: PreviewInsight[]) {
  const cues = ensurePreviewMoodCue(insights).filter((insight) => insight.kind !== "route");
  const seen = new Set<string>();

  return cues.filter((insight) => {
    const key = `${insight.label}:${insight.value}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function previewWaypointKey(insight: PreviewInsight, index: number) {
  return `${insight.kind}:${insight.label}:${insight.value}:${index}`;
}

function isEditableWaypointInsight(insight: PreviewInsight) {
  if (!["stop", "task"].includes(insight.kind)) {
    return false;
  }
  return !isWaypointPlaceholder(insight.value);
}

function collectPreviewWaypointHints(
  insights: PreviewInsight[],
  edits: Record<string, string>,
  deleted: Record<string, boolean> = {}
) {
  return previewCueInsights(insights)
    .flatMap((insight, index) => {
      if (!isEditableWaypointInsight(insight)) {
        return [];
      }
      const key = previewWaypointKey(insight, index);
      if (deleted[key]) {
        return [];
      }
      const value = (edits[key] ?? insight.value).trim();
      if (!value || isWaypointPlaceholder(value)) {
        return [];
      }
      return [previewWaypointHint(value, insight)];
    })
    .slice(0, 5);
}

function customWaypointKey(id: string) {
  return `custom:${id}`;
}

function waypointCategoryOption(value: WaypointCategoryValue) {
  return (
    WAYPOINT_CATEGORY_OPTIONS.find((option) => option.value === value) ??
    WAYPOINT_CATEGORY_OPTIONS[0]
  );
}

function customWaypointToHint(waypoint: CustomWaypoint) {
  const value = waypoint.value.trim();
  if (!value) {
    return "";
  }

  const category = waypointCategoryOption(waypoint.category);
  return `필수 경유: [${category.label}] ${value}`;
}

function previewWaypointHint(value: string, insight: PreviewInsight) {
  const strength = previewWaypointStrength(insight);
  if (strength === "strong") {
    return `필수 경유: ${value}`;
  }
  if (strength === "weak") {
    return `참고 경유: ${value}`;
  }
  return value;
}

function previewWaypointStrength(insight: PreviewInsight): "strong" | "weak" | "none" {
  if (insight.strength === "strong" || insight.strength === "weak") {
    return insight.strength;
  }
  if (insight.kind === "task") {
    return "strong";
  }
  if (insight.kind === "stop") {
    return "weak";
  }
  return "none";
}

function waypointStrengthMeta(strength: "strong" | "weak" | "none") {
  if (strength === "strong") {
    return {
      label: "필수",
      containerClass: "bg-[#fff7fb] ring-tide/18",
      badgeClass: "bg-[#fde2ef] text-tide"
    };
  }
  if (strength === "weak") {
    return {
      label: "참고",
      containerClass: "bg-[#fffdf8] ring-moss/14",
      badgeClass: "bg-[#ddf3eb] text-moss"
    };
  }
  return {
    label: "",
    containerClass: "bg-[#fffdf8] ring-ink/7",
    badgeClass: ""
  };
}

function isWaypointPlaceholder(value: string) {
  return [
    "선호 장소 후보 확인",
    "쉴 만한 장소 후보 확인",
    "경유 후보 확인"
  ].includes(value.trim());
}

function ensurePreviewMoodCue(insights: PreviewInsight[]) {
  if (insights.some((insight) => insight.kind === "mood")) {
    return insights;
  }

  const fallbackMood = previewMoodFallback(insights);
  if (!fallbackMood) {
    return [
      ...insights,
      { label: "컨디션", value: "컨디션 조건 없음", kind: "mood" as const, strength: "none" }
    ];
  }

  return [...insights, fallbackMood];
}

function previewMoodFallback(insights: PreviewInsight[]): PreviewInsight | null {
  if (insights.some((insight) => insight.kind === "time" && insight.value.includes("도착"))) {
    return { label: "컨디션", value: "시간 압박 기준으로 경로 비교", kind: "mood", strength: "none" };
  }
  if (insights.some((insight) => insight.value.includes("조용"))) {
    return { label: "컨디션", value: "조용 기준으로 경로 비교", kind: "mood", strength: "none" };
  }
  if (insights.some((insight) => insight.value.includes("카페") || insight.value.includes("쉬"))) {
    return { label: "컨디션", value: "휴식 기준으로 경로 비교", kind: "mood", strength: "none" };
  }
  return null;
}

function buildLocalPreviewInsights(
  text: string,
  originText: string,
  destinationText: string,
  activeMood: string
): PreviewInsight[] {
  const normalized = text.toLowerCase();
  const route = extractLocalPreviewRoute(text, originText, destinationText);
  const insights: PreviewInsight[] = [
    {
      label: "이동",
      value: `${route.origin || "출발지"} → ${route.destination || "도착지"}`,
      kind: "route",
      strength: "none"
    }
  ];

  if (hasLocalTimeHint(normalized)) {
    insights.push({ label: "시간", value: "도착 시간 조건 반영", kind: "time", strength: "none" });
  } else {
    insights.push({ label: "시간", value: "감지된 시간 조건 없음", kind: "time", strength: "none" });
  }
  insights.push(...buildLocalStopInsights(text));
  if (/(피곤|지쳐|tired|exhausted)/.test(normalized)) {
    insights.push({ label: "상태", value: "피로 낮은 길 우선", kind: "mood", strength: "none" });
  }

  if (activeMood) {
    insights.push({
      label: "컨디션",
      value: `${activeMood} 기준으로 경로 비교`,
      kind: "mood",
      strength: "none"
    });
  } else {
    insights.push({
      label: "컨디션",
      value: "컨디션 조건 없음",
      kind: "mood",
      strength: "none"
    });
  }

  return insights;
}

function hasLocalTimeHint(normalized: string) {
  return (
    /\d+\s*(시|분)\s*(까지|전|안에)?/.test(normalized) ||
    /(오전|오후)\s*\d+/.test(normalized) ||
    /\d+\s*시간\s*안/.test(normalized) ||
    /(deadline|마감|늦지|촉박)/.test(normalized)
  );
}

function buildLocalStopInsights(text: string): PreviewInsight[] {
  const area = extractLocalAreaHint(text);
  const insights: PreviewInsight[] = [];
  const explicitWaypoint = extractLocalWaypointHint(text);

  if (explicitWaypoint) {
    insights.push({
      label: "거쳐 갈 곳",
      value: `${explicitWaypoint} 주변`,
      kind: "stop",
      strength: "strong"
    });
  }

  if (/(걷|걸을|산책|돌아다니|주변|근처|선선)/.test(text)) {
    insights.push({
      label: "경유 후보",
      value: area ? `${area} 주변 산책` : "주변 산책 후보",
      kind: "stop",
      strength: "weak"
    });
  }
  if (/(카페|커피|과제|공부|작업|cafe|coffee|study|work)/i.test(text)) {
    insights.push({
      label: "경유 후보",
      value: area ? `${area} 카페 작업` : "카페 작업 후보",
      kind: "stop",
      strength: /있으면|괜찮으면|들러도|가능하면/.test(text) ? "weak" : "strong"
    });
  }
  if (/(쉬|휴식|조용|rest|quiet)/i.test(text)) {
    insights.push({
      label: "경유 후보",
      value: area ? `${area} 휴식 장소` : "쉴 만한 장소 후보",
      kind: "stop",
      strength: /있으면|괜찮으면|들러도|가능하면/.test(text) ? "weak" : "strong"
    });
  }
  if (/(다이소|살거|살 것|사야|구매|장보기|마트|편의점|약국|올리브영|픽업|찾으러)/.test(text)) {
    insights.push({
      label: "들를 곳",
      value: localErrandValue(text),
      kind: "task",
      strength: /있으면|괜찮으면|들러도|가능하면/.test(text) ? "weak" : "strong"
    });
  }

  const seen = new Set<string>();
  return insights
    .filter((insight) => {
      if (seen.has(insight.value)) {
        return false;
      }
      seen.add(insight.value);
      return true;
    })
    .slice(0, 3);
}

function localErrandValue(text: string) {
  for (const keyword of ["다이소", "올리브영", "약국", "편의점", "마트"]) {
    if (text.includes(keyword)) {
      return `${keyword} 들르기`;
    }
  }
  if (/(픽업|찾으러)/.test(text)) {
    return "물건 픽업";
  }
  if (text.includes("장보기")) {
    return "장보기";
  }
  return "살 것 사기";
}

function extractLocalAreaHint(text: string) {
  const direct = text.match(/([가-힣A-Za-z0-9]+)\s*(?:주변|근처)/);
  if (direct?.[1]) {
    return direct[1];
  }

  const destination = text.match(
    /([가-힣A-Za-z0-9]+)\s*(?:까지|으로|로)\s*(?:갈|가고|가야|도착|이동)/
  );
  return destination?.[1] ?? "";
}

function collectTextWaypointHints(text: string) {
  const waypoint = extractLocalWaypointHint(text);
  return waypoint ? [`필수 경유: ${waypoint} 주변`] : [];
}

function uniqueWaypointHints(hints: string[]) {
  const seen = new Set<string>();
  return hints.filter((hint) => {
    const key = hint.replace(/\s+/g, "").toLowerCase();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function extractLocalWaypointHint(text: string) {
  const patterns = [
    /(?:에서|부터)\s*([가-힣A-Za-z0-9\s]+?)\s*(?:지나서|지나|거쳐서|거쳐|들러서|들러|경유)\s*[가-힣A-Za-z0-9\s]+?(?:까지|으로|로|에)/,
    /([가-힣A-Za-z0-9\s]+?)\s*(?:지나서|지나|거쳐서|거쳐|들러서|들러|경유)\s*[가-힣A-Za-z0-9\s]+?(?:까지|으로|로|에)/,
    /(?:에서|부터)\s*([가-힣A-Za-z0-9\s]+?)(?:까지|으로|로|에)\s*(?:가서|간\s*뒤|갔다가|들러|들렀다가|경유)/,
    /([가-힣A-Za-z0-9\s]+?)(?:까지|으로|로|에)\s*(?:가서|간\s*뒤|갔다가|들러|들렀다가|경유)/
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    const waypoint = cleanLocalLocationHint(match?.[1] ?? "");
    if (waypoint) {
      return waypoint;
    }
  }

  return "";
}

function extractLocalPreviewRoute(
  text: string,
  originText: string,
  destinationText: string
) {
  const compact = text.replace(/\s+/g, " ").trim();
  const destinationFirstMatch = compact.match(
    /(.+?)(?:까지|으로|로)\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동)/
  );
  const originAfterDestinationMatch = compact.match(
    /(?:가고\s*싶어|가고싶어|싶어)\s+(.+?)(?:에서|부터)/
  );

  if (destinationFirstMatch && originAfterDestinationMatch) {
    return {
      origin: cleanLocalLocationHint(originAfterDestinationMatch[1]) || originText,
      destination: cleanLocalLocationHint(destinationFirstMatch[1]) || destinationText
    };
  }

  const fromToMatch = compact.match(
    /(.+?)(?:에서|부터)\s*(.+?)(?:까지|으로|로)(?=\s|,|\.|;|$)/
  ) ?? compact.match(
    /(.+?)(?:에서|부터)\s*(.+?)\s*(?:가고\s*싶|가야|갈|가기|가려고|도착|이동|가서)/
  );

  if (fromToMatch) {
    return {
      origin: cleanLocalLocationHint(fromToMatch[1]) || originText,
      destination: cleanLocalLocationHint(fromToMatch[2]) || destinationText
    };
  }

  const destinationMatch = compact.match(
    /(.+?)(?:까지|으로|로|에)\s*(?:가야|갈|가기|가려고|도착|이동)/
  );

  return {
    origin: originText,
    destination: cleanLocalLocationHint(destinationMatch?.[1]) || destinationText
  };
}

function cleanLocalLocationHint(value?: string) {
  if (!value) {
    return "";
  }

  return value
    .replace(/^.*(?:가고\s*싶어|가고싶어|싶어)\s+/, "")
    .replace(/^(오늘|내일|지금|일단|그리고|나는|나|제가|저는)\s+/, "")
    .replace(/\s*(에서|부터|으로|로|까지|에)$/, "")
    .trim();
}

function previewSourceLabel(source: string) {
  if (source === "llm") {
    return "분석됨";
  }
  if (source === "local") {
    return "입력 반영";
  }
  return "준비";
}

function previewInsightIcon(insight: PreviewInsight) {
  const text = `${insight.label} ${insight.value}`;
  if (insight.kind === "route") {
    return <Navigation size={15} aria-hidden />;
  }
  if (insight.kind === "time") {
    return <Clock3 size={15} aria-hidden />;
  }
  if (insight.kind === "stop" && /(카페|커피|과제|작업)/.test(text)) {
    return <Coffee size={15} aria-hidden />;
  }
  if (insight.kind === "stop" && /(산책|공원|걷|걸)/.test(text)) {
    return <Leaf size={15} aria-hidden />;
  }
  if (insight.kind === "stop") {
    return <MapPin size={15} aria-hidden />;
  }
  if (insight.kind === "task") {
    return <MapPinned size={15} aria-hidden />;
  }
  return <HeartPulse size={15} aria-hidden />;
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
  const additions = moodPreset ? [`컨디션 기준: ${moodPreset.sentence}`] : [];

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
  const recoveryStop = route.stops.find((stop) => stop.category === "recovery");
  if (recoveryStop) {
    return `${recoveryStop.name} 경유 경로`;
  }
  const errandStop = route.stops.find((stop) => stop.category === "errand");
  if (errandStop) {
    return `${errandStop.name} 경유 경로`;
  }
  if (route.provider === "tmap-pedestrian") {
    return "Tmap 도보 경로";
  }
  if (route.provider === "tmap-transit") {
    return "Tmap 대중교통 경로";
  }
  if (route.provider === "tmap-mixed") {
    return "Tmap 혼합 경로";
  }
  if (route.provider === "osrm") {
    return "직접 이동 경로";
  }
  return routeLabel(route.id);
}

function routeOptionTitle(route: RouteCandidate, index: number) {
  const recoveryStop = route.stops.find((stop) => stop.category === "recovery");
  if (recoveryStop) {
    return `${recoveryStop.name} 들르는 경로`;
  }
  const errandStop = route.stops.find((stop) => stop.category === "errand");
  if (errandStop) {
    return `${errandStop.name} 들르는 경로`;
  }
  if (route.stops.length > 0) {
    return `${route.stops[0].name} 경유 경로`;
  }
  if (index === 0) {
    return "추천 경로";
  }
  if (route.walking_minutes <= 5) {
    return "걷기 적은 경로";
  }
  if (routeDurationMinutes(route) <= 10) {
    return "짧은 이동 경로";
  }
  return `후보 ${index + 1}`;
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
  if (route.provider === "osrm") {
    return "도로망 기준";
  }
  return "추정 경로";
}

function routeDurationMinutes(route: RouteCandidate) {
  return (
    route.real_duration_minutes ??
    route.estimated_duration_minutes ??
    route.estimated_minutes
  );
}

function durationLabel(route: RouteCandidate) {
  if (route.real_duration_minutes) {
    return `${route.real_duration_minutes}분`;
  }
  return `${routeDurationMinutes(route)}분 추정`;
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
