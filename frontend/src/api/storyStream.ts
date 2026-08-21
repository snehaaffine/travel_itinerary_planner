import type { HolidayProfile, StoryBeat } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const APP_API_TOKEN = import.meta.env.VITE_APP_API_TOKEN || "dev-app-token";

export type StoryDone = {
  ended: boolean;
  tone: string;
  path: string;
  beat_number: number;
};

export type StoryStreamHandlers = {
  onNarrative?: (text: string) => void;
  onHoliday?: (text: string) => void;
  onBeat?: (beat: StoryBeat) => void;
  onProfile?: (profile: HolidayProfile) => void;
};

function parseSse(buffer: string): { events: { event: string; data: string }[]; rest: string } {
  const events: { event: string; data: string }[] = [];
  const parts = buffer.split(/\n\n/);
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length) events.push({ event, data: dataLines.join("\n") });
  }
  return { events, rest };
}

export async function streamStoryBeat(
  body: { tone?: string; choice_ids?: string[] },
  handlers: StoryStreamHandlers = {},
): Promise<StoryDone> {
  const response = await fetch(`${API_BASE_URL}/story/beat`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-App-Token": APP_API_TOKEN,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = typeof payload.detail === "string" ? payload.detail : response.statusText;
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Story stream was empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done: StoryDone | null = null;

  while (true) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    for (const item of parsed.events) {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(item.data) as Record<string, unknown>;
      } catch {
        continue;
      }
      if (item.event === "error") {
        throw new Error(String(payload.detail || "The narrator stalled. Try again."));
      }
      if (item.event === "narrative" && typeof payload.text === "string") {
        handlers.onNarrative?.(payload.text);
      } else if (item.event === "holiday" && typeof payload.text === "string") {
        handlers.onHoliday?.(payload.text);
      } else if (item.event === "beat") {
        handlers.onBeat?.(payload as unknown as StoryBeat);
      } else if (item.event === "profile") {
        handlers.onProfile?.(payload as unknown as HolidayProfile);
      } else if (item.event === "done") {
        done = payload as unknown as StoryDone;
      }
    }
  }

  if (!done) {
    throw new Error("Story stream ended early");
  }
  return done;
}
