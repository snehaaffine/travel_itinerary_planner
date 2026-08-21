import { useState } from "react";
import { STORY_GENRES, STOCKED_STORY_GENRES, STORY_STEPS } from "../data";
import type { HolidayProfile, StoryBeat } from "../types";
import { Screen } from "./Screen";

const PROFILE_FIELDS: { key: keyof HolidayProfile; label: string }[] = [
  { key: "pace", label: "Pace" },
  { key: "company", label: "Company" },
  { key: "setting", label: "Setting" },
  { key: "comfort", label: "Comfort" },
  { key: "food", label: "Food" },
  { key: "adventure", label: "Adventure" },
];

export function PathForkScreen({
  onBack,
  onTemplate,
  onStory,
}: {
  onBack: () => void;
  onTemplate: () => void;
  onStory: () => void;
}) {
  const [picked, setPicked] = useState<"template" | "story" | null>(null);
  return (
    <Screen
      step="calendar"
      title="How should we plan?"
      subtitle="A short template, or a five-beat story that finds the holiday."
      onBack={onBack}
      onNext={() => (picked === "story" ? onStory() : onTemplate())}
      nextLabel={picked === "story" ? "Start the story" : "Continue"}
      nextDisabled={!picked}
    >
      <div className="grid grid-cols-1 gap-3 fade-up">
        {(
          [
            {
              id: "template" as const,
              title: "Quick template",
              desc: "Travel type, budget, diet, and interests — the usual path.",
            },
            {
              id: "story" as const,
              title: "Tell me a story",
              desc: "Pick a genre, play five beats, then we read the holiday.",
            },
          ] as const
        ).map((card) => {
          const selected = picked === card.id;
          return (
            <button
              key={card.id}
              type="button"
              onClick={() => setPicked(card.id)}
              className="text-left p-6 rounded-2xl"
              style={{
                background: selected ? "rgba(51,61,41,0.12)" : "var(--surface)",
                border: selected ? "2px solid #333d29" : "2px solid var(--border)",
              }}
            >
              <p
                style={{
                  fontFamily: "Fraunces, serif",
                  fontSize: 20,
                  fontWeight: 700,
                  color: selected ? "#333d29" : "var(--cream)",
                }}
              >
                {card.title}
              </p>
              <p className="mt-2 text-sm" style={{ color: "var(--cream-muted)" }}>
                {card.desc}
              </p>
            </button>
          );
        })}
      </div>
    </Screen>
  );
}

export function GenreScreen({
  onBack,
  onNext,
}: {
  onBack: () => void;
  onNext: (genre: string) => void;
}) {
  const [genre, setGenre] = useState<string | null>(null);
  return (
    <Screen
      step="genre"
      steps={STORY_STEPS}
      title="Pick a genre"
      subtitle="The story follows this tone. It is fiction, not a travel quiz."
      onBack={onBack}
      onNext={() => genre && onNext(genre)}
      nextLabel="Begin beat 1"
      nextDisabled={!genre}
    >
      <div className="flex flex-wrap gap-2.5 fade-up">
        {STORY_GENRES.map((name) => {
          const selected = genre === name;
          const stocked = (STOCKED_STORY_GENRES as readonly string[]).includes(name);
          return (
            <button
              key={name}
              type="button"
              disabled={!stocked}
              onClick={() => stocked && setGenre(name)}
              className="px-4 py-2 rounded-full text-sm font-medium"
              style={{
                background: selected ? "#333d29" : "var(--surface)",
                color: selected ? "#ffffff" : stocked ? "var(--cream)" : "var(--cream-muted)",
                border: selected ? "1.5px solid #333d29" : "1.5px solid var(--border)",
                opacity: stocked ? 1 : 0.45,
                cursor: stocked ? "pointer" : "not-allowed",
              }}
            >
              {name}
            </button>
          );
        })}
      </div>
    </Screen>
  );
}

export function BeatScreen({
  beat,
  narrative,
  loading,
  error,
  selectedIds,
  onToggle,
  onBack,
  onNext,
}: {
  beat: StoryBeat | null;
  narrative: string;
  loading: boolean;
  error: string | null;
  selectedIds: string[];
  onToggle: (id: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const number = beat?.beat_number ?? 1;
  const selected = new Set(selectedIds);
  return (
    <Screen
      step={`beat${number}`}
      steps={STORY_STEPS}
      title={`Beat ${number} of 5`}
      subtitle="Choose one or more. The story will honor all of them."
      onBack={onBack}
      onNext={loading ? undefined : onNext}
      nextLabel="Continue"
      nextDisabled={loading || selectedIds.length < 1}
    >
      {loading && !narrative && (
        <p className="fade-up mb-4" style={{ color: "var(--cream-muted)" }}>
          Writing the scene…
        </p>
      )}
      {narrative && (
        <p
          className="fade-up mb-5"
          style={{
            fontFamily: "Fraunces, serif",
            fontSize: 18,
            lineHeight: 1.45,
            color: "#1e2d4a",
            whiteSpace: "pre-wrap",
          }}
        >
          {narrative}
        </p>
      )}
      {error && (
        <p className="text-sm mb-4" style={{ color: "#991b1b" }}>
          {error}
        </p>
      )}
      {beat && (
        <div className="flex flex-wrap gap-2.5 fade-up">
          {beat.options.map((option) => {
            const isSelected = selected.has(option.id);
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onToggle(option.id)}
                className="px-4 py-2 rounded-full text-sm font-medium"
                style={{
                  background: isSelected ? "#333d29" : "var(--surface)",
                  color: isSelected ? "#ffffff" : "var(--cream)",
                  border: isSelected ? "1.5px solid #333d29" : "1.5px solid var(--border)",
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </Screen>
  );
}

export function ProfileScreen({
  profile,
  holiday,
  loading,
  error,
  vote,
  onVote,
  onBack,
  onNext,
}: {
  profile: HolidayProfile | null;
  holiday: string;
  loading: boolean;
  error: string | null;
  vote: "up" | "down" | null;
  onVote: (vote: "up" | "down") => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <Screen
      step="profile"
      steps={STORY_STEPS}
      title="Your holiday"
      subtitle="A reading of the five beats — then we build the days."
      onBack={onBack}
      onNext={profile ? onNext : undefined}
      nextLabel="Build itinerary"
      nextDisabled={!profile}
    >
      {loading && !holiday && (
        <p className="fade-up mb-4" style={{ color: "var(--cream-muted)" }}>
          Reading the choices you made…
        </p>
      )}
      {holiday && (
        <p
          className="fade-up mb-5"
          style={{
            fontFamily: "Fraunces, serif",
            fontSize: 18,
            lineHeight: 1.45,
            color: "#1e2d4a",
            whiteSpace: "pre-wrap",
          }}
        >
          {holiday}
        </p>
      )}
      {error && (
        <p className="text-sm mb-4" style={{ color: "#991b1b" }}>
          {error}
        </p>
      )}
      {profile && (
        <>
          <div className="grid grid-cols-2 gap-3 fade-up mb-5">
            {PROFILE_FIELDS.map((field) => (
              <div
                key={field.key}
                className="p-4 rounded-2xl"
                style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
              >
                <p
                  className="text-xs font-semibold uppercase tracking-widest mb-1"
                  style={{ color: "var(--cream-muted)" }}
                >
                  {field.label}
                </p>
                <p className="text-sm" style={{ color: "var(--cream)" }}>
                  {String(profile[field.key] ?? "")}
                </p>
              </div>
            ))}
          </div>
          {profile.assumptions?.length > 0 && (
            <div className="fade-up">
              <p
                className="text-xs font-semibold uppercase tracking-widest mb-2"
                style={{ color: "var(--cream-muted)" }}
              >
                Assumptions
              </p>
              <ul className="space-y-1">
                {profile.assumptions.map((item) => (
                  <li key={item} className="text-sm" style={{ color: "var(--cream-muted)" }}>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="fade-up mt-5">
            <p
              className="text-xs font-semibold uppercase tracking-widest mb-2"
              style={{ color: "var(--cream-muted)" }}
            >
              Does this reading fit?
            </p>
            <div className="flex gap-2">
              {(
                [
                  { id: "up" as const, label: "Thumbs up" },
                  { id: "down" as const, label: "Thumbs down" },
                ]
              ).map((option) => {
                const selected = vote === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => onVote(option.id)}
                    className="px-4 py-2 rounded-full text-sm font-medium"
                    style={{
                      background: selected ? "#333d29" : "var(--surface)",
                      color: selected ? "#ffffff" : "var(--cream)",
                      border: selected ? "1.5px solid #333d29" : "1.5px solid var(--border)",
                    }}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </Screen>
  );
}
