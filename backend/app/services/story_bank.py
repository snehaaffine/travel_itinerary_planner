from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.story import STORY_GENRES, StoryError

STORY_BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "story_bank.json"

REQUIRED_FIELDS = ("trip_type", "interests", "pace", "food_style", "wildcard_flavor")
MIN_OPTIONS = 1
MAX_OPTIONS = 4


class StoryBankError(StoryError):
    pass


def interpolate_destination(text: str, destination: str | None) -> str:
    place = (destination or "your destination").strip() or "your destination"
    return text.replace("{{destination}}", place)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StoryBankError(message)


def _validate_beat(beat: dict[str, Any], expected_number: int, expected_field: str) -> None:
    _require(isinstance(beat, dict), f"Beat {expected_number} must be an object")
    _require(
        int(beat.get("beat_number") or 0) == expected_number,
        f"Beat {expected_number} has the wrong beat_number",
    )
    _require(
        beat.get("field") == expected_field,
        f"Beat {expected_number} field must be {expected_field}",
    )
    narrative = beat.get("narrative_text")
    _require(
        isinstance(narrative, str) and narrative.strip(),
        f"Beat {expected_number} missing narrative",
    )
    options = beat.get("options")
    _require(isinstance(options, list), f"Beat {expected_number} options must be a list")
    _require(
        MIN_OPTIONS <= len(options) <= MAX_OPTIONS,
        f"Beat {expected_number} must have 1–4 options",
    )
    values: list[str] = []
    for option in options:
        _require(isinstance(option, dict), f"Beat {expected_number} has a malformed option")
        label = str(option.get("label") or "").strip()
        value = str(option.get("value") or "").strip()
        _require(label and value, f"Beat {expected_number} option missing label or value")
        values.append(value)
    _require(len(values) == len(set(values)), f"Beat {expected_number} has duplicate option values")


def _validate_story(story: dict[str, Any], field_order: tuple[str, ...]) -> None:
    tone = story.get("tone")
    _require(isinstance(tone, str) and tone in STORY_GENRES, f"Unknown story tone: {tone}")
    beats = story.get("beats")
    _require(
        isinstance(beats, list) and len(beats) == len(field_order),
        f"{tone} must have 5 beats",
    )
    for index, field_name in enumerate(field_order, start=1):
        _validate_beat(beats[index - 1], index, field_name)


def validate_bank(raw: dict[str, Any]) -> dict[str, Any]:
    _require(
        isinstance(raw, dict) and isinstance(raw.get("stories"), list),
        "Story bank missing stories",
    )
    notes = raw.get("_notes") if isinstance(raw.get("_notes"), dict) else {}
    field_order = tuple(notes.get("field_order") or REQUIRED_FIELDS)
    _require(field_order == REQUIRED_FIELDS, "Story bank field_order does not match the PRD")
    tones: list[str] = []
    for story in raw["stories"]:
        _require(isinstance(story, dict), "Each story must be an object")
        _validate_story(story, field_order)
        tones.append(str(story["tone"]))
    _require(len(tones) == len(set(tones)), "Story bank has duplicate tones")
    return raw


@lru_cache(maxsize=1)
def load_story_bank() -> dict[str, Any]:
    if not STORY_BANK_PATH.is_file():
        raise StoryBankError(f"Story bank not found: {STORY_BANK_PATH}")
    try:
        raw = json.loads(STORY_BANK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryBankError("Story bank JSON is invalid") from exc
    return validate_bank(raw)


def stocked_genres() -> tuple[str, ...]:
    return tuple(str(story["tone"]) for story in load_story_bank()["stories"])


def is_stocked(tone: str) -> bool:
    return tone in stocked_genres()


def story_for_tone(tone: str) -> dict[str, Any]:
    for story in load_story_bank()["stories"]:
        if story["tone"] == tone:
            return story
    raise StoryBankError(f"No story content for {tone}")


def beat_for(tone: str, beat_number: int, destination: str | None = None) -> dict[str, Any]:
    story = story_for_tone(tone)
    beats = story["beats"]
    if beat_number < 1 or beat_number > len(beats):
        raise StoryBankError("That story beat does not exist")
    raw = beats[beat_number - 1]
    options = []
    for index, option in enumerate(raw["options"], start=1):
        options.append(
            {
                "id": str(index),
                "label": str(option["label"]),
                "value": str(option["value"]),
                "image_url": option.get("image_url"),
            }
        )
    return {
        "beat_number": beat_number,
        "narrative_text": interpolate_destination(str(raw["narrative_text"]), destination),
        "audio_url": raw.get("audio_url"),
        "field": str(raw["field"]),
        "options": options,
        "chosen_value": None,
    }
