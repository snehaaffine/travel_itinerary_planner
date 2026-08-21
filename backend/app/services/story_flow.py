from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import DetachedInstanceError

from app.config import get_settings
from app.constants import (
    ITINERARY_RATE_WINDOW_SECONDS,
    STORY_FIELD_ALIASES,
    STORY_INTEREST_CODES,
    STORY_RATE_LIMIT,
    STORY_TRIP_TYPE_CODES,
)
from app.db.models import StorySession, TripPath, TripState
from app.services.story import (
    STORY_TURNS,
    HolidayProfile,
    StoryError,
    StoryEvent,
    generate_holiday_profile_events,
    maybe_summarize_story_context,
    resolve_genre,
)
from app.services.story_bank import beat_for, is_stocked


def check_story_rate_limit(trip_id: UUID, client_ip: str) -> bool:
    if not get_settings().rate_limits_enabled:
        return True
    from app.cache.redis import get_redis

    redis = get_redis()
    keys = [f"ratelimit:story:trip:{trip_id}", f"ratelimit:story:ip:{client_ip}"]
    for key in keys:
        current = redis.incr(key)
        if current == 1:
            redis.expire(key, ITINERARY_RATE_WINDOW_SECONDS)
        if current > STORY_RATE_LIMIT:
            return False
    return True


def beats_document(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        beats = list(raw.get("beats") or [])
        return {
            "beats": beats,
            "holiday_profile": raw.get("holiday_profile"),
            "profile_feedback": raw.get("profile_feedback"),
            "context_summary": raw.get("context_summary"),
        }
    if isinstance(raw, list):
        return {
            "beats": list(raw),
            "holiday_profile": None,
            "profile_feedback": None,
            "context_summary": None,
        }
    return {
        "beats": [],
        "holiday_profile": None,
        "profile_feedback": None,
        "context_summary": None,
    }


def holiday_profile_from_trip(trip: TripState) -> dict[str, Any] | None:
    try:
        sessions = list(trip.story_sessions or [])
    except (DetachedInstanceError, TypeError):
        return None
    for session in reversed(sessions):
        document = beats_document(session.beats)
        summary = document.get("context_summary")
        if isinstance(summary, dict) and summary:
            return summary
        profile = document.get("holiday_profile")
        if isinstance(profile, dict) and profile:
            return profile
    return None


def apply_canonical_values(trip: TripState, field: str, values: list[str]) -> None:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return
    field_name = STORY_FIELD_ALIASES.get(field, field)
    if field_name == "trip_type":
        types: list[str] = []
        pets = False
        for value in cleaned:
            for part in value.split("|"):
                piece = part.strip()
                if not piece:
                    continue
                lower = piece.lower()
                if lower.startswith("pets="):
                    pets = lower.split("=", 1)[1] in {"true", "1", "yes"}
                    continue
                mapped = STORY_TRIP_TYPE_CODES.get(lower)
                if mapped:
                    types.append(mapped)
                    if lower == "family_pet":
                        pets = True
                    continue
                if "pet" in lower:
                    pets = True
                else:
                    types.append(piece)
        for candidate in ("Family", "Friends", "Couple", "Solo"):
            if any(item.lower() == candidate.lower() for item in types):
                trip.trip_type = candidate
                break
        else:
            if types:
                trip.trip_type = types[0][:50]
        trip.pets = pets
    elif field_name == "interests":
        mapped: list[str] = []
        seen: set[str] = set()
        for value in cleaned:
            label = STORY_INTEREST_CODES.get(value.lower(), value)
            if label.lower() in seen:
                continue
            seen.add(label.lower())
            mapped.append(label)
        trip.interests = mapped
    elif field_name == "pace":
        trip.pace = ", ".join(cleaned)[:50]
    elif field_name == "food_preference":
        trip.food_preference = ", ".join(cleaned)[:255]
    elif field_name == "flavor_preference":
        trip.flavor_preference = ", ".join(cleaned)[:255]


def _latest_session(db: Session, trip: TripState) -> StorySession | None:
    try:
        attached = list(trip.story_sessions or [])
    except (DetachedInstanceError, TypeError):
        attached = []
    if attached:
        return attached[-1]
    return (
        db.query(StorySession)
        .filter(StorySession.trip_state_id == trip.id)
        .order_by(StorySession.created_at.desc())
        .first()
    )


def _save_document(db: Session, session: StorySession, document: dict[str, Any]) -> None:
    session.beats = document
    try:
        flag_modified(session, "beats")
    except Exception:
        pass
    db.add(session)


def _history_from_beats(beats: list[dict[str, Any]]) -> list[StoryEvent]:
    history: list[StoryEvent] = []
    for beat in beats:
        chosen = beat.get("chosen_value")
        if not chosen:
            continue
        labels = [str(item) for item in chosen]
        options = beat.get("options") or []
        values: list[str] = []
        if isinstance(options, list):
            by_label = {
                str(option.get("label") or ""): str(
                    option.get("value") or option.get("label") or ""
                )
                for option in options
                if isinstance(option, dict)
            }
            by_value = {
                str(option.get("value") or ""): str(option.get("value") or "")
                for option in options
                if isinstance(option, dict)
            }
            for label in labels:
                values.append(by_label.get(label) or by_value.get(label) or label)
        history.append(
            StoryEvent(
                scene=str(beat.get("narrative_text") or ""),
                field=str(beat.get("field") or ""),
                selected=labels,
                values=values or labels,
            )
        )
    return history


def _options_by_id(beat: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for option in beat.get("options") or []:
        if isinstance(option, dict) and option.get("id") is not None:
            mapping[str(option["id"])] = option
    return mapping


def _beat_payload(beat: dict[str, Any]) -> dict[str, Any]:
    return {
        "beat_number": beat.get("beat_number"),
        "narrative_text": beat.get("narrative_text") or "",
        "field": beat.get("field") or "",
        "options": beat.get("options") or [],
    }


def record_profile_feedback(db: Session, trip: TripState, vote: Literal["up", "down"]) -> None:
    session = _latest_session(db, trip)
    if session is None:
        raise StoryError("Start with a genre")
    document = beats_document(session.beats)
    if not document.get("holiday_profile"):
        raise StoryError("Holiday profile is not ready")
    document["profile_feedback"] = vote
    _save_document(db, session, document)
    db.commit()


def iter_story_events(
    db: Session,
    trip: TripState,
    *,
    tone: str | None = None,
    choice_ids: list[str] | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    if tone:
        genre = resolve_genre(tone)
        if not genre:
            raise StoryError("Pick a genre from the PRD list")
        if not is_stocked(genre):
            raise StoryError("That genre does not have a story yet")
        trip.path = TripPath.STORY
        session = StorySession(trip_state_id=trip.id, tone=genre, beats={"beats": []})
        db.add(session)
        try:
            trip.story_sessions.append(session)
        except (DetachedInstanceError, TypeError, AttributeError):
            pass
        beat = beat_for(genre, 1, trip.destination)
        yield "status", {"stage": "beat", "beat_number": 1, "tone": genre}
        yield "narrative", {"text": beat["narrative_text"]}
        document = {"beats": [beat], "holiday_profile": None}
        _save_document(db, session, document)
        db.commit()
        db.refresh(session)
        yield "beat", _beat_payload(document["beats"][0])
        yield "done", {"ended": False, "tone": genre, "path": "story", "beat_number": 1}
        return

    session = _latest_session(db, trip)
    if session is None:
        raise StoryError("Start with a genre")
    if not choice_ids:
        raise StoryError("Pick at least one option")

    document = beats_document(session.beats)
    beats = document["beats"]
    open_beats = [beat for beat in beats if not beat.get("chosen_value")]
    if not open_beats:
        if document.get("holiday_profile"):
            yield "profile", document["holiday_profile"]
            yield "done", {
                "ended": True,
                "tone": session.tone,
                "path": "story",
                "beat_number": STORY_TURNS,
            }
            return
        raise StoryError("No open story beat")
    current = open_beats[-1]
    options = _options_by_id(current)
    picked = []
    for ident in choice_ids:
        option = options.get(str(ident))
        if option is None:
            raise StoryError(f"Unknown choice: {ident}")
        picked.append(option)
    if not (1 <= len(picked) <= 4):
        raise StoryError("Pick between 1 and 4 options")
    values = [str(item.get("value") or item.get("label") or "") for item in picked]
    current["chosen_value"] = values
    apply_canonical_values(trip, str(current.get("field") or ""), values)
    _save_document(db, session, document)
    db.commit()

    beat_number = int(current.get("beat_number") or len(beats))
    history = _history_from_beats(document["beats"])
    if beat_number >= STORY_TURNS:
        yield "status", {"stage": "profile", "tone": session.tone}
        profile: HolidayProfile | None = None
        for event in generate_holiday_profile_events(
            session.tone,
            history,
            llm_factory=llm_factory,
            destination=trip.destination,
            dates=trip.dates if isinstance(trip.dates, dict) else None,
        ):
            if event.kind == "holiday":
                yield "holiday", {"text": event.text}
            elif event.kind == "profile":
                profile = event.profile
        if profile is None:
            raise StoryError("Holiday profile missing summary")
        document["holiday_profile"] = profile.to_dict()
        summary = maybe_summarize_story_context(history, profile, llm_factory=llm_factory)
        if summary:
            document["context_summary"] = summary
        _save_document(db, session, document)
        db.commit()
        yield "profile", document["holiday_profile"]
        yield "done", {
            "ended": True,
            "tone": session.tone,
            "path": "story",
            "beat_number": beat_number,
        }
        return

    next_number = beat_number + 1
    next_beat = beat_for(session.tone, next_number, trip.destination)
    yield "status", {"stage": "beat", "beat_number": next_number, "tone": session.tone}
    yield "narrative", {"text": next_beat["narrative_text"]}
    document["beats"].append(next_beat)
    _save_document(db, session, document)
    db.commit()
    yield "beat", _beat_payload(document["beats"][-1])
    yield "done", {
        "ended": False,
        "tone": session.tone,
        "path": "story",
        "beat_number": next_number,
    }
