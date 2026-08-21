import { useEffect, useRef, useState } from "react";
import { apiClient } from "./api/client";
import { streamStoryBeat } from "./api/storyStream";
import { CalendarMonth, addMonths, isCurrentMonth } from "./components/Calendar";
import { ItineraryDocument } from "./components/ItineraryDocument";
import { Screen } from "./components/Screen";
import { BeatScreen, GenreScreen, PathForkScreen, ProfileScreen } from "./components/StoryFlow";
import { BUDGET_LEVELS, DIET_OPTIONS, POPULAR, STORY_STEPS, TRAVEL_TYPES } from "./data";
import type { DateRange, DestinationChoice, HolidayProfile, ItineraryContent, Step, StoryBeat } from "./types";

const CARD_W = 220;
const CARD_GAP = 12;

function SearchScreen({
  onNext,
}: {
  onNext: (dest: DestinationChoice) => void;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<DestinationChoice | null>(null);
  const [suggestions, setSuggestions] = useState<DestinationChoice[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [carouselIdx, setCarouselIdx] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocClick = (event: MouseEvent) => {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setSuggestions([]);
      setSearching(false);
      setSearchError(null);
      return;
    }
    if (selected && term === selected.formatted) {
      setOpen(false);
      return;
    }
    setSearching(true);
    setOpen(true);
    const handle = setTimeout(() => {
      apiClient<DestinationChoice[]>(`/destinations/suggest?q=${encodeURIComponent(term)}`)
        .then((places) => {
          setSuggestions(places);
          setSearchError(null);
        })
        .catch((err: Error) => {
          setSuggestions([]);
          setSearchError(err.message || "Could not search destinations");
        })
        .finally(() => setSearching(false));
    }, 200);
    return () => clearTimeout(handle);
  }, [query, selected]);

  const maxIdx = Math.max(0, POPULAR.length - 1);

  const scrollTo = (idx: number) => {
    const clamped = Math.max(0, Math.min(idx, maxIdx));
    setCarouselIdx(clamped);
    scrollRef.current?.scrollTo({ left: clamped * (CARD_W + CARD_GAP), behavior: "smooth" });
  };

  const pickSuggestion = (place: DestinationChoice) => {
    setSelected(place);
    setQuery(place.formatted);
    setSuggestions([]);
    setOpen(false);
  };

  const choosePopular = (name: string, country: string) => {
    const choice: DestinationChoice = {
      name,
      formatted: `${name}, ${country}`,
      country,
      place_id: "",
      lat: 0,
      lon: 0,
    };
    setSelected(choice);
    setQuery(choice.formatted);
    setOpen(false);
  };

  const showMenu =
    open && query.trim().length >= 2 && !(selected && query.trim() === selected.formatted);

  return (
    <Screen
      step="search"
      title="Where would you like to travel?"
      subtitle="Search a destination or pick from popular spots below."
      onNext={() => selected && onNext(selected)}
      nextLabel="Find My Dates"
      nextDisabled={!selected}
    >
      <div className="relative mb-6 fade-up z-20" ref={boxRef}>
        <span className="absolute left-4 top-5 text-lg" style={{ color: "var(--cream-muted)" }}>
          🔍
        </span>
        <input
          type="text"
          value={query}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(null);
            setOpen(true);
          }}
          onFocus={() => {
            if (query.trim().length >= 2) setOpen(true);
          }}
          placeholder="Search destinations…"
          className="w-full pl-12 pr-4 py-4 rounded-2xl text-base outline-none"
          style={{
            background: "var(--surface)",
            border: selected ? "1.5px solid #333d29" : "1px solid var(--border)",
            color: "var(--cream)",
            fontFamily: "Outfit, sans-serif",
            caretColor: "var(--gold)",
          }}
        />
        {showMenu && (
          <div
            className="absolute left-0 right-0 mt-2 rounded-2xl overflow-hidden z-30"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              boxShadow: "0 12px 32px rgba(30,45,74,0.12)",
              maxHeight: 280,
              overflowY: "auto",
            }}
          >
            {searching && (
              <p className="px-4 py-3 text-sm" style={{ color: "var(--cream-muted)" }}>
                Searching…
              </p>
            )}
            {!searching && searchError && (
              <p className="px-4 py-3 text-sm" style={{ color: "#991b1b" }}>
                {searchError}
              </p>
            )}
            {!searching && !searchError && suggestions.length === 0 && (
              <p className="px-4 py-3 text-sm" style={{ color: "var(--cream-muted)" }}>
                No matching destinations
              </p>
            )}
            {!searching &&
              suggestions.map((s) => (
                <button
                  key={s.place_id || s.formatted}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pickSuggestion(s)}
                  className="w-full text-left px-4 py-3 text-sm"
                  style={{
                    color: "var(--cream)",
                    borderBottom: "1px solid var(--border)",
                    fontFamily: "Outfit, sans-serif",
                  }}
                >
                  {s.formatted}
                </button>
              ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--cream-muted)" }}>
          Popular Destinations
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => scrollTo(carouselIdx - 1)}
            disabled={carouselIdx === 0}
            className="w-8 h-8 rounded-full"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "#1e2d4a" }}
          >
            ←
          </button>
          <button
            onClick={() => scrollTo(carouselIdx + 1)}
            disabled={carouselIdx >= maxIdx}
            className="w-8 h-8 rounded-full"
            style={{ background: "#333d29", color: "#fff" }}
          >
            →
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex gap-3 overflow-x-auto pb-3"
        style={{ scrollbarWidth: "none", marginLeft: -24, marginRight: -24, paddingLeft: 24, paddingRight: 24 }}
      >
        {POPULAR.map((dest) => {
          const isSelected = selected?.name === dest.name;
          return (
            <button
              key={dest.name}
              onClick={() => choosePopular(dest.name, dest.country)}
              className="relative overflow-hidden rounded-2xl text-left flex-shrink-0"
              style={{
                width: CARD_W,
                height: 280,
                border: isSelected ? "2px solid var(--gold)" : "2px solid transparent",
              }}
            >
              <img
                src={`https://images.unsplash.com/photo-${dest.imgId}?w=440&h=560&fit=crop&auto=format`}
                alt={dest.name}
                className="absolute inset-0 w-full h-full object-cover"
              />
              <div className="absolute inset-0" style={{ background: "linear-gradient(to top, rgba(10,22,40,0.9) 0%, rgba(10,22,40,0.1) 55%)" }} />
              <div className="absolute bottom-0 left-0 p-4">
                <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-full mb-2" style={{ background: "rgba(255,252,242,0.9)", color: "#333d29" }}>
                  {dest.tag}
                </span>
                <p style={{ fontFamily: "Fraunces, serif", fontSize: 20, fontWeight: 700, color: "#ffffff" }}>{dest.name}</p>
                <p style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>{dest.country}</p>
              </div>
            </button>
          );
        })}
      </div>
    </Screen>
  );
}

function CalendarScreen({
  onBack,
  onNext,
}: {
  onBack: () => void;
  onNext: (dates: DateRange, skip: boolean) => void;
}) {
  const now = new Date();
  const [left, setLeft] = useState({ year: now.getFullYear(), month: now.getMonth() });
  const [rangeStart, setRangeStart] = useState<string | null>(null);
  const [rangeEnd, setRangeEnd] = useState<string | null>(null);
  const [skipDates, setSkipDates] = useState(false);
  const right = addMonths(left.year, left.month, 1);

  const onSelect = (iso: string) => {
    setSkipDates(false);
    if (!rangeStart || (rangeStart && rangeEnd)) {
      setRangeStart(iso);
      setRangeEnd(null);
      return;
    }
    if (iso < rangeStart) {
      setRangeEnd(rangeStart);
      setRangeStart(iso);
      return;
    }
    setRangeEnd(iso);
  };

  const canContinue = skipDates || Boolean(rangeStart && rangeEnd);
  const dayCount =
    rangeStart && rangeEnd
      ? Math.round((new Date(rangeEnd).getTime() - new Date(rangeStart).getTime()) / 86400000) + 1
      : 0;

  return (
    <Screen
      step="calendar"
      title="When are you travelling?"
      subtitle="Pick your travel dates or choose to stay flexible."
      onBack={onBack}
      onNext={() =>
        onNext(skipDates || !rangeStart || !rangeEnd ? null : { start: rangeStart, end: rangeEnd }, skipDates)
      }
      nextLabel={skipDates ? "I'll decide later" : dayCount > 0 ? `Continue with ${dayCount} day${dayCount > 1 ? "s" : ""}` : "Continue"}
      nextDisabled={!canContinue}
      wide
    >
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setLeft(addMonths(left.year, left.month, -1))}
          disabled={isCurrentMonth(left.year, left.month)}
          className="w-10 h-10 rounded-full"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            color: isCurrentMonth(left.year, left.month) ? "rgba(30,45,74,0.25)" : "#333d29",
          }}
        >
          ←
        </button>
        <p className="text-xs uppercase tracking-widest" style={{ color: "var(--cream-muted)" }}>
          Upcoming months
        </p>
        <button
          onClick={() => setLeft(addMonths(left.year, left.month, 1))}
          className="w-10 h-10 rounded-full"
          style={{ background: "#333d29", color: "#fff" }}
        >
          →
        </button>
      </div>
      <div className="grid grid-cols-2 gap-4 fade-up">
        <CalendarMonth year={left.year} month={left.month} rangeStart={rangeStart} rangeEnd={rangeEnd} onSelect={onSelect} />
        <CalendarMonth year={right.year} month={right.month} rangeStart={rangeStart} rangeEnd={rangeEnd} onSelect={onSelect} />
      </div>
      <button
        onClick={() => {
          setSkipDates(!skipDates);
          setRangeStart(null);
          setRangeEnd(null);
        }}
        className="flex items-center gap-3 p-4 rounded-2xl mt-4 w-full"
        style={{
          background: skipDates ? "rgba(51,61,41,0.12)" : "var(--surface)",
          border: skipDates ? "1px solid #333d29" : "1px solid var(--border)",
        }}
      >
        <div
          className="w-5 h-5 rounded flex items-center justify-center"
          style={{ background: skipDates ? "#333d29" : "transparent", border: skipDates ? "none" : "1.5px solid rgba(30,45,74,0.3)" }}
        >
          {skipDates && <span className="text-white text-xs font-bold">✓</span>}
        </div>
        <div className="text-left">
          <p className="text-sm font-semibold">I don't have dates yet</p>
          <p className="text-xs" style={{ color: "var(--cream-muted)" }}>
            Stay flexible — we'll help you plan later
          </p>
        </div>
      </button>
    </Screen>
  );
}

function TravelTypeScreen({
  onBack,
  onNext,
}: {
  onBack: () => void;
  onNext: (tripType: string, pets: boolean) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [pets, setPets] = useState(false);
  return (
    <Screen
      step="travelType"
      title="Kind of travel?"
      subtitle="How you travel shapes everything. Tell us your vibe."
      onBack={onBack}
      onNext={() => selected && onNext(selected, pets)}
      nextLabel="Set My Budget"
      nextDisabled={!selected}
    >
      <div className="grid grid-cols-2 gap-3 fade-up">
        {TRAVEL_TYPES.map((t) => {
          const isSelected = selected === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setSelected(t.id)}
              className="flex flex-col items-center justify-center gap-3 p-6 rounded-2xl"
              style={{
                background: isSelected ? "rgba(51,61,41,0.12)" : "var(--surface)",
                border: isSelected ? "2px solid #333d29" : "2px solid var(--border)",
              }}
            >
              <span style={{ fontSize: 38 }}>{t.icon}</span>
              <p style={{ fontFamily: "Fraunces, serif", fontSize: 18, fontWeight: 700, color: isSelected ? "#333d29" : "var(--cream)" }}>
                {t.label}
              </p>
              <p style={{ fontSize: 12, color: "var(--cream-muted)" }}>{t.desc}</p>
            </button>
          );
        })}
      </div>
      <button
        onClick={() => setPets((v) => !v)}
        className="flex items-center gap-3 p-4 rounded-2xl mt-4 w-full"
        style={{
          background: pets ? "rgba(51,61,41,0.12)" : "var(--surface)",
          border: pets ? "1px solid #333d29" : "1px solid var(--border)",
        }}
      >
        <span>🐾</span>
        <div className="text-left">
          <p className="text-sm font-semibold">Traveling with pets</p>
          <p className="text-xs" style={{ color: "var(--cream-muted)" }}>
            We'll prefer pet-friendly places
          </p>
        </div>
      </button>
    </Screen>
  );
}

function formatInterestLabel(raw: string): string | null {
  const words = raw
    .replace(/\band\b/gi, " ")
    .replace(/[&/,+|]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
  return words.length ? words.join(" ") : null;
}

function isFineDining(tag: string): boolean {
  const key = tag.trim().toLowerCase();
  return key === "fine dining" || key === "fine dine" || key === "luxury dining" || key === "haute cuisine";
}

function InterestsScreen({
  tags,
  loading,
  allowFineDining,
  onBack,
  onNext,
}: {
  tags: string[];
  loading: boolean;
  allowFineDining: boolean;
  onBack: () => void;
  onNext: (interests: string[]) => void;
}) {
  const [localTags, setLocalTags] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const nextTags = allowFineDining ? tags : tags.filter((tag) => !isFineDining(tag));
    setLocalTags(nextTags);
    setSelected((prev) => {
      const next = new Set([...prev].filter((tag) => nextTags.includes(tag) && (allowFineDining || !isFineDining(tag))));
      return next;
    });
  }, [tags, allowFineDining]);

  useEffect(() => {
    if (adding) inputRef.current?.focus();
  }, [adding]);

  const toggle = (tag: string) => {
    if (!allowFineDining && isFineDining(tag)) return;
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(tag) ? next.delete(tag) : next.add(tag);
      return next;
    });
  };

  const addCustom = () => {
    const label = formatInterestLabel(inputVal);
    if (!label || (!allowFineDining && isFineDining(label))) {
      setInputVal("");
      setAdding(false);
      return;
    }
    const exists = localTags.some((tag) => tag.toLowerCase() === label.toLowerCase());
    if (!exists) {
      setLocalTags((prev) => [...prev, label]);
      setSelected((prev) => new Set([...prev, label]));
    }
    setInputVal("");
    setAdding(false);
  };

  const count = selected.size;

  return (
    <Screen
      step="interests"
      title="What are your interests?"
      subtitle="Pick what fits this destination and budget — chips stay short and unique."
      onBack={onBack}
      onNext={() => onNext([...selected])}
      nextLabel={count > 0 ? `Build itinerary · ${count}` : "Skip for now"}
    >
      {loading && localTags.length === 0 && (
        <p className="fade-up mb-4" style={{ color: "var(--cream-muted)" }}>
          Matching interests to this place…
        </p>
      )}
      <div className="flex flex-wrap gap-2.5 fade-up">
        {localTags.map((tag) => {
          const isSelected = selected.has(tag);
          return (
            <button
              key={tag}
              onClick={() => toggle(tag)}
              className="px-4 py-2 rounded-full text-sm font-medium"
              style={{
                background: isSelected ? "#333d29" : "var(--surface)",
                color: isSelected ? "#ffffff" : "var(--cream)",
                border: isSelected ? "1.5px solid #333d29" : "1.5px solid var(--border)",
              }}
            >
              {tag}
            </button>
          );
        })}
        {adding ? (
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") addCustom();
                if (e.key === "Escape") setAdding(false);
              }}
              placeholder="Type interest…"
              className="px-4 py-2 rounded-full text-sm outline-none"
              style={{ background: "var(--surface2)", border: "1.5px solid #333d29", color: "var(--cream)", width: 150 }}
            />
            <button onClick={addCustom} className="px-3 py-2 rounded-full text-sm font-semibold" style={{ background: "#333d29", color: "#fff" }}>
              Add
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="px-4 py-2 rounded-full text-sm font-medium"
            style={{ color: "#333d29", border: "1.5px dashed #333d29" }}
          >
            Add interests +
          </button>
        )}
      </div>
    </Screen>
  );
}

function BudgetScreen({
  onBack,
  onNext,
}: {
  onBack: () => void;
  onNext: (budget: string, diets: string[]) => void;
}) {
  const [budget, setBudget] = useState<string | null>(null);
  const [diets, setDiets] = useState<Set<string>>(new Set());

  const toggleDiet = (tag: string) => {
    setDiets((prev) => {
      const next = new Set(prev);
      next.has(tag) ? next.delete(tag) : next.add(tag);
      return next;
    });
  };

  return (
    <Screen
      step="budget"
      title="Budget and diet?"
      subtitle="We'll keep the plan in range and skip food that doesn't work for you."
      onBack={onBack}
      onNext={() => budget && onNext(budget, [...diets])}
      nextLabel="Set My Interests"
      nextDisabled={!budget}
    >
      <div className="grid grid-cols-2 gap-3 fade-up">
        {BUDGET_LEVELS.map((level) => {
          const isSelected = budget === level.id;
          return (
            <button
              key={level.id}
              type="button"
              onClick={() => setBudget(level.id)}
              className="flex flex-col items-center justify-center gap-2 p-5 rounded-2xl"
              style={{
                background: isSelected ? "rgba(51,61,41,0.12)" : "var(--surface)",
                border: isSelected ? "2px solid #333d29" : "2px solid var(--border)",
              }}
            >
              <span style={{ fontSize: 28 }}>{level.icon}</span>
              <p
                style={{
                  fontFamily: "Fraunces, serif",
                  fontSize: 16,
                  fontWeight: 700,
                  color: isSelected ? "#333d29" : "var(--cream)",
                }}
              >
                {level.label}
              </p>
              <p style={{ fontSize: 12, color: "var(--cream-muted)", textAlign: "center" }}>{level.desc}</p>
            </button>
          );
        })}
      </div>
      <p
        className="text-xs font-semibold uppercase tracking-widest mt-6 mb-3"
        style={{ color: "var(--cream-muted)" }}
      >
        Diet constraints
      </p>
      <div className="flex flex-wrap gap-2.5">
        {DIET_OPTIONS.map((tag) => {
          const isSelected = diets.has(tag);
          return (
            <button
              key={tag}
              type="button"
              onClick={() => toggleDiet(tag)}
              className="px-4 py-2 rounded-full text-sm font-medium"
              style={{
                background: isSelected ? "#333d29" : "var(--surface)",
                color: isSelected ? "#ffffff" : "var(--cream)",
                border: isSelected ? "1.5px solid #333d29" : "1.5px solid var(--border)",
              }}
            >
              {tag}
            </button>
          );
        })}
      </div>
      <p className="text-xs mt-3" style={{ color: "var(--cream-muted)" }}>
        Leave blank if you have no restrictions.
      </p>
    </Screen>
  );
}

function ItineraryScreen({
  content,
  error,
  loading,
  destination,
  onNext,
  onBack,
  progressSteps,
}: {
  content: ItineraryContent | null;
  error: string | null;
  loading: boolean;
  destination: DestinationChoice | null;
  onNext: () => void;
  onBack: () => void;
  progressSteps?: readonly string[];
}) {
  const failed = Boolean(error) && !loading && !content;
  return (
    <Screen
      step="itinerary"
      steps={progressSteps}
      title={loading ? "Crafting your days…" : failed ? "Almost there" : "Your Itinerary"}
      subtitle={
        loading
          ? "Checking weather and places for your trip."
          : failed
            ? "Something went wrong while building the plan."
            : "This plan is final — no edits or regenerates."
      }
      onBack={failed ? onBack : undefined}
      onNext={content ? onNext : undefined}
      nextLabel="Share feedback"
      nextDisabled={!content}
      wide
    >
      {loading && (
        <p className="fade-up" style={{ color: "var(--cream-muted)" }}>
          This can take a minute.
        </p>
      )}
      {failed && (
        <p className="fade-up" style={{ color: "var(--cream-muted)" }}>
          We couldn't put this trip together just now. Go back and try again.
        </p>
      )}
      {content && <ItineraryDocument content={content} destination={destination} />}
    </Screen>
  );
}

function FeedbackScreen({
  onSubmit,
  progressSteps,
}: {
  onSubmit: (rating: number, comment: string) => Promise<void>;
  progressSteps?: readonly string[];
}) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (done) {
    return (
      <Screen step="feedback" steps={progressSteps} title="Thank you." subtitle="Your notes help us improve the next trip.">
        <p className="fade-up" style={{ color: "var(--cream-muted)" }}>
          Safe travels.
        </p>
      </Screen>
    );
  }

  return (
    <Screen
      step="feedback"
      steps={progressSteps}
      title="How was this plan?"
      subtitle="A rating is enough. A comment is optional."
      onNext={async () => {
        try {
          await onSubmit(rating, comment);
          setDone(true);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Could not save feedback");
        }
      }}
      nextLabel="Submit"
      nextDisabled={rating < 1}
    >
      <div className="flex gap-2 mb-4">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => setRating(n)}
            className="w-12 h-12 rounded-xl font-semibold"
            style={{
              background: rating >= n ? "#333d29" : "var(--surface)",
              color: rating >= n ? "#fff" : "var(--cream)",
              border: "1px solid var(--border)",
            }}
          >
            {n}
          </button>
        ))}
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Anything we should know? (optional)"
        className="w-full rounded-2xl p-4 outline-none min-h-28"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--cream)" }}
      />
      {error && <p className="text-sm mt-3" style={{ color: "#991b1b" }}>{error}</p>}
    </Screen>
  );
}

export default function App() {
  const [step, setStep] = useState<Step>("search");
  const [path, setPath] = useState<"template" | "story" | null>(null);
  const [destination, setDestination] = useState<DestinationChoice | null>(null);
  const [tripType, setTripType] = useState<string | null>(null);
  const [pets, setPets] = useState(false);
  const [budget, setBudget] = useState<string | null>(null);
  const [diets, setDiets] = useState<string[]>([]);
  const [interestTags, setInterestTags] = useState<string[]>([]);
  const [interestTagsLoading, setInterestTagsLoading] = useState(false);
  const [itinerary, setItinerary] = useState<ItineraryContent | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [storyBeats, setStoryBeats] = useState<StoryBeat[]>([]);
  const [beatIndex, setBeatIndex] = useState(0);
  const [narrative, setNarrative] = useState("");
  const [selectedChoiceIds, setSelectedChoiceIds] = useState<string[]>([]);
  const [storyLoading, setStoryLoading] = useState(false);
  const [storyError, setStoryError] = useState<string | null>(null);
  const [holidayProfile, setHolidayProfile] = useState<HolidayProfile | null>(null);
  const [holidayText, setHolidayText] = useState("");
  const [profileVote, setProfileVote] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (!destination || !budget) {
      setInterestTags([]);
      return;
    }
    let cancelled = false;
    setInterestTagsLoading(true);
    const params = new URLSearchParams({
      destination: destination.formatted,
      budget,
    });
    apiClient<{ tags: string[] }>(`/template/interests?${params.toString()}`)
      .then((data) => {
        if (!cancelled) setInterestTags(data.tags);
      })
      .catch(() => {
        if (!cancelled) setInterestTags([]);
      })
      .finally(() => {
        if (!cancelled) setInterestTagsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [destination, budget]);

  const createTrip = async (nextDates: DateRange, skipped: boolean) => {
    if (!destination) return;
    await apiClient("/trip", {
      method: "POST",
      body: JSON.stringify({
        destination: destination.formatted,
        place_id: destination.place_id || undefined,
        lat: destination.lat || undefined,
        lon: destination.lon || undefined,
        dates: skipped ? null : nextDates,
      }),
    });
  };

  const generate = async (picked: string[]) => {
    if (!budget) return;
    setGenerating(true);
    setGenError(null);
    setStep("itinerary");
    try {
      await apiClient("/template", {
        method: "POST",
        body: JSON.stringify({ trip_type: tripType, pets, interests: picked, budget, diets }),
      });
      const result = await apiClient<{ content: ItineraryContent; map_image_url?: string | null }>(
        "/itinerary",
        { method: "POST" },
      );
      setItinerary({ ...result.content, map_image_url: result.map_image_url });
    } catch {
      setGenError("failed");
    } finally {
      setGenerating(false);
    }
  };

  const generateFromStory = async () => {
    if (profileVote) {
      try {
        await apiClient("/story/profile-feedback", {
          method: "POST",
          body: JSON.stringify({ vote: profileVote }),
        });
      } catch {
        // Vote is a training signal only; generation still proceeds.
      }
    }
    setGenerating(true);
    setGenError(null);
    setStep("itinerary");
    try {
      const result = await apiClient<{ content: ItineraryContent; map_image_url?: string | null }>(
        "/itinerary",
        { method: "POST" },
      );
      setItinerary({ ...result.content, map_image_url: result.map_image_url });
    } catch {
      setGenError("failed");
    } finally {
      setGenerating(false);
    }
  };

  const startStory = async (genre: string) => {
    setPath("story");
    setStoryBeats([]);
    setBeatIndex(0);
    setNarrative("");
    setSelectedChoiceIds([]);
    setHolidayProfile(null);
    setHolidayText("");
    setProfileVote(null);
    setStoryError(null);
    setStoryLoading(true);
    setStep("beat");
    try {
      await streamStoryBeat(
        { tone: genre },
        {
          onNarrative: setNarrative,
          onBeat: (beat) => {
            setStoryBeats([beat]);
            setBeatIndex(0);
            setNarrative(beat.narrative_text);
          },
        },
      );
    } catch (err) {
      setStoryError(err instanceof Error ? err.message : "The narrator stalled. Try again.");
    } finally {
      setStoryLoading(false);
    }
  };

  const continueStory = async () => {
    const current = storyBeats[beatIndex];
    if (!current || selectedChoiceIds.length < 1) return;
    const submittingLast = current.beat_number === 5;
    setStoryError(null);
    setStoryLoading(true);
    if (submittingLast) {
      setHolidayProfile(null);
      setHolidayText("");
      setStep("profile");
    } else {
      setNarrative("");
    }
    try {
      const nextBeats = [...storyBeats];
      await streamStoryBeat(
        { choice_ids: selectedChoiceIds },
        {
          onNarrative: (text) => {
            if (!submittingLast) setNarrative(text);
          },
          onHoliday: setHolidayText,
          onBeat: (beat) => {
            nextBeats.push(beat);
            setStoryBeats(nextBeats);
            setBeatIndex(nextBeats.length - 1);
            setNarrative(beat.narrative_text);
            setSelectedChoiceIds([]);
          },
          onProfile: (profile) => {
            setHolidayProfile(profile);
            setHolidayText(profile.holiday);
          },
        },
      );
    } catch (err) {
      setStoryError(err instanceof Error ? err.message : "The narrator stalled. Try again.");
      if (submittingLast) setStep("beat");
    } finally {
      setStoryLoading(false);
    }
  };

  const storyProgress = path === "story" ? STORY_STEPS : undefined;

  return (
    <div style={{ maxWidth: step === "calendar" || step === "itinerary" ? 920 : 480, margin: "0 auto", minHeight: "100vh" }}>
      {step === "search" && (
        <SearchScreen
          onNext={(dest) => {
            setDestination(dest);
            setStep("calendar");
          }}
        />
      )}
      {step === "calendar" && (
        <CalendarScreen
          onBack={() => setStep("search")}
          onNext={async (nextDates, skipped) => {
            await createTrip(nextDates, skipped);
            setStep("path");
          }}
        />
      )}
      {step === "path" && (
        <PathForkScreen
          onBack={() => setStep("calendar")}
          onTemplate={() => {
            setPath("template");
            setStep("travelType");
          }}
          onStory={() => setStep("genre")}
        />
      )}
      {step === "genre" && (
        <GenreScreen onBack={() => setStep("path")} onNext={startStory} />
      )}
      {step === "beat" && (
        <BeatScreen
          beat={storyBeats[beatIndex] ?? null}
          narrative={narrative}
          loading={storyLoading}
          error={storyError}
          selectedIds={selectedChoiceIds}
          onToggle={(id) => {
            setSelectedChoiceIds((prev) =>
              prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
            );
          }}
          onBack={() => {
            if (beatIndex > 0) {
              const previous = storyBeats[beatIndex - 1];
              setBeatIndex(beatIndex - 1);
              setNarrative(previous?.narrative_text ?? "");
              setSelectedChoiceIds([]);
              return;
            }
            setStep("genre");
          }}
          onNext={() => {
            if (beatIndex < storyBeats.length - 1) {
              const next = storyBeats[beatIndex + 1];
              setBeatIndex(beatIndex + 1);
              setNarrative(next.narrative_text);
              setSelectedChoiceIds([]);
              return;
            }
            continueStory();
          }}
        />
      )}
      {step === "profile" && (
        <ProfileScreen
          profile={holidayProfile}
          holiday={holidayText}
          loading={storyLoading}
          error={storyError}
          vote={profileVote}
          onVote={setProfileVote}
          onBack={() => setStep("beat")}
          onNext={generateFromStory}
        />
      )}
      {step === "travelType" && (
        <TravelTypeScreen
          onBack={() => setStep("path")}
          onNext={(type, withPets) => {
            setTripType(type);
            setPets(withPets);
            setStep("budget");
          }}
        />
      )}
      {step === "budget" && (
        <BudgetScreen
          onBack={() => setStep("travelType")}
          onNext={(nextBudget, nextDiets) => {
            setBudget(nextBudget);
            setDiets(nextDiets);
            setStep("interests");
          }}
        />
      )}
      {step === "interests" && destination && (
        <InterestsScreen
          tags={interestTags}
          loading={interestTagsLoading}
          allowFineDining={budget === "Comfortable" || budget === "Luxury"}
          onBack={() => setStep("budget")}
          onNext={generate}
        />
      )}
      {step === "itinerary" && (
        <ItineraryScreen
          content={itinerary}
          error={genError}
          loading={generating}
          destination={destination}
          progressSteps={storyProgress}
          onNext={() => setStep("feedback")}
          onBack={() => {
            setGenError(null);
            setStep(path === "story" ? "profile" : "interests");
          }}
        />
      )}
      {step === "feedback" && (
        <FeedbackScreen
          progressSteps={storyProgress}
          onSubmit={async (rating, comment) => {
            await apiClient("/feedback", {
              method: "POST",
              body: JSON.stringify({ rating, comment: comment || null }),
            });
          }}
        />
      )}
    </div>
  );
}
