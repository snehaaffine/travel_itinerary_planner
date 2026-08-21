import json
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.constants import STORY_CONTEXT_SUMMARIZE_TOKENS
from app.llm.provider import get_llm_client
from app.services.agents import message_text

# PRD Phase 2: user-picked genre (does not count against the 5-beat budget).
STORY_GENRES = (
    "Fantasy",
    "Mystery",
    "Fairytale",
    "Sci-Fi",
    "Western",
    "Adventure/Pirate",
    "Heist/Thriller",
    "Noir Detective",
    "Epic/Mythic",
    "Spy Thriller",
    "Comedy",
)

# PRD Phase 2: backend-controlled field order. Model only phrases the scene.
BEAT_SPECS = (
    {
        "field": "trip_type",
        "collects": "who is traveling, and whether a pet comes along",
        "fallback_question": "Who walks with you?",
        "fallback_options": (
            {"label": "Just me", "value": "Solo"},
            {"label": "Me and one other person", "value": "Couple"},
            {"label": "A group of friends", "value": "Friends"},
            {"label": "Family, and maybe a pet", "value": "Family|pets=true"},
        ),
    },
    {
        "field": "interests",
        "collects": "interests and vibe — what draws them",
        "fallback_question": "What pulls you forward?",
        "fallback_options": (
            {"label": "Food, markets, and kitchens", "value": "Street Food"},
            {"label": "Museums, ruins, and old stories", "value": "Historic Sites"},
            {"label": "Wild land, water, and weather", "value": "Parks"},
            {"label": "Music, night, and crowded rooms", "value": "Nightlife"},
        ),
    },
    {
        "field": "pace",
        "collects": "pace and intensity",
        "fallback_question": "How fast does the day move?",
        "fallback_options": (
            {"label": "Linger. Leave hours empty.", "value": "Unhurried"},
            {"label": "A mix of rest and a few plans", "value": "Balanced"},
            {"label": "Keep moving. Fill the hours.", "value": "Packed"},
            {"label": "Push hard. Chase the edge.", "value": "Intense"},
        ),
    },
    {
        "field": "food_preference",
        "collects": "food preference",
        "fallback_question": "What do you eat when you can choose?",
        "fallback_options": (
            {"label": "Stall food and busy markets", "value": "Street food"},
            {"label": "Simple neighborhood kitchens", "value": "Local home cooking"},
            {"label": "Whatever the table is serving", "value": "No restrictions"},
            {"label": "A special meal worth dressing for", "value": "Fine dining"},
        ),
    },
    {
        "field": "flavor_preference",
        "collects": "one wildcard flavor for the holiday",
        "fallback_question": "What flavor should the whole trip carry?",
        "fallback_options": (
            {"label": "Quiet and a little tender", "value": "Soft and unhurried"},
            {"label": "Strange, playful, a bit chaotic", "value": "Playful chaos"},
            {"label": "Grand, cinematic, larger than life", "value": "Epic"},
            {"label": "Sharp, clever, a little dangerous", "value": "Thriller"},
        ),
    },
)

STORY_TURNS = len(BEAT_SPECS)
MIN_CHOICES = 2
MAX_CHOICES = 4

STORY_AGENT_PROMPT = """You are a choose-your-own-adventure narrator.
The player picked a GENRE. Write this beat in that genre.
Do not write a travel itinerary, hotel list, or day-by-day plan.
Do not ask "what kind of holiday do you want?"

This beat collects ONE trip field. Invent a short scene, then up to 4
choices that are story actions AND answers to that field.
The player may pick more than one choice. If they do, later beats should
honor all of them.

Return ONLY valid JSON:
{"narrative_text":"","field":"","options":[{"label":"","value":""}]}

Rules:
- English only
- narrative_text: 2-5 sentences
- 2-4 options
- label: what the player reads (concrete action in-genre)
- value: short canonical answer for the field (not a sentence)
- field must equal the field you were given
- No markdown, no images, no audio
"""

SUMMARIZE_AGENT_PROMPT = """Condense story-path context for an itinerary brief.
Return ONLY valid JSON:
{"pace":"","company":"","setting":"","comfort":"","food":"","adventure":"","assumptions":[],"holiday":""}
Keep the six phrases short. Keep 2-4 assumptions. English only. No markdown.
Do not invent hotels, flights, bookings, or a day-by-day itinerary.
"""

PROFILE_AGENT_PROMPT = """You infer the holiday this player would enjoy.
You see a genre and the five story choices they made (companions, vibe,
pace, food, flavor). Make assumptions. Do not invent hotels, flights,
bookings, or a day-by-day itinerary.

Return ONLY valid JSON in this exact shape and style:
{
  "pace": "Unhurried",
  "company": "Alone or with one other person",
  "setting": "Quiet countryside and small towns",
  "comfort": "Simple, local, not polished",
  "food": "Markets and neighborhood kitchens",
  "adventure": "Gentle walks, not extreme sports",
  "assumptions": [
    "They linger rather than rush.",
    "They avoid crowds."
  ],
  "holiday": "A slow week in the countryside, walking between villages and eating simply."
}

Rules:
- English only
- pace, company, setting, comfort, food, adventure: short phrases like the example
- assumptions: 2-6 specific claims tied to what they picked
- holiday: one or two sentences, same tone as the example
- If choices conflict, say so in assumptions and keep the stronger pattern
- Destination and dates may be provided; still no hotels, flights, or a day-by-day itinerary
- No markdown
"""


class StoryError(Exception):
    pass


@dataclass
class StoryChoice:
    id: str
    text: str
    value: str = ""


@dataclass
class StoryTurn:
    scene: str
    field: str
    choices: list[StoryChoice] = field(default_factory=list)
    ended: bool = False


@dataclass
class StoryEvent:
    scene: str
    field: str
    selected: list[str]
    values: list[str] = field(default_factory=list)


@dataclass
class HolidayProfile:
    pace: str
    company: str
    setting: str
    comfort: str
    food: str
    adventure: str
    assumptions: list[str]
    holiday: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_genre(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip().lower()
    for genre in STORY_GENRES:
        if text == genre.lower() or text == str(STORY_GENRES.index(genre) + 1):
            return genre
    for genre in STORY_GENRES:
        short = genre.split("/")[0].lower()
        if text == short or short.startswith(text) or text in genre.lower():
            return genre
    return None


def beat_spec(turn_number: int) -> dict[str, Any]:
    index = max(1, min(turn_number, STORY_TURNS)) - 1
    return BEAT_SPECS[index]


def _extract_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise StoryError("Model did not return JSON")
    snippet = cleaned[start : end + 1]
    candidates = [snippet, re.sub(r",\s*([}\]])", r"\1", snippet)]
    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    raise StoryError("Model JSON was invalid")


def _option_from_item(item: Any, index: int) -> StoryChoice | None:
    ident = str(index + 1)
    if isinstance(item, str):
        text = item.strip()
        return StoryChoice(id=ident, text=text, value=text) if text else None
    if not isinstance(item, dict):
        return None
    text = str(item.get("label") or item.get("text") or "").strip()
    value = str(item.get("value") or text).strip()
    ident = str(item.get("id") or ident).strip() or ident
    if not text:
        return None
    return StoryChoice(id=ident, text=text, value=value or text)


def fallback_turn(turn_number: int) -> StoryTurn:
    spec = beat_spec(turn_number)
    choices = [
        StoryChoice(id=str(index + 1), text=str(option["label"]), value=str(option["value"]))
        for index, option in enumerate(spec["fallback_options"][:MAX_CHOICES])
    ]
    return StoryTurn(
        scene=str(spec["fallback_question"]),
        field=str(spec["field"]),
        choices=choices,
    )


def normalize_turn(parsed: dict[str, Any], turn_number: int = 1) -> StoryTurn:
    spec = beat_spec(turn_number)
    scene = str(parsed.get("narrative_text") or parsed.get("scene") or "").strip()
    field_name = str(parsed.get("field") or spec["field"]).strip() or str(spec["field"])
    raw_options = parsed.get("options")
    if not isinstance(raw_options, list):
        raw_options = parsed.get("choices")
    if not isinstance(raw_options, list):
        raw_options = []
    choices: list[StoryChoice] = []
    for index, item in enumerate(raw_options[:MAX_CHOICES]):
        option = _option_from_item(item, index)
        if option:
            choices.append(option)
    if not scene or len(choices) < MIN_CHOICES:
        raise StoryError("Story JSON missing narrative or choices")
    return StoryTurn(scene=scene, field=field_name, choices=choices)


def parse_story_turn(text: str, turn_number: int = 1) -> StoryTurn:
    return normalize_turn(_extract_object(text), turn_number=turn_number)


def parse_choice_input(raw: str, choices: list[StoryChoice]) -> list[StoryChoice]:
    text = raw.strip().lower()
    if not text:
        raise StoryError("Pick at least one option")
    parts = [part.strip() for part in re.split(r"[,\s]+", text) if part.strip()]
    by_id = {choice.id.lower(): choice for choice in choices}
    selected: list[StoryChoice] = []
    seen: set[str] = set()
    for part in parts:
        choice = by_id.get(part)
        if choice is None and part.isdigit():
            index = int(part) - 1
            if 0 <= index < len(choices):
                choice = choices[index]
        if choice is None:
            raise StoryError(f"Unknown choice: {part}")
        if choice.id in seen:
            continue
        seen.add(choice.id)
        selected.append(choice)
    if not selected:
        raise StoryError("Pick at least one option")
    return selected


def _phrase(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def normalize_profile(parsed: dict[str, Any]) -> HolidayProfile:
    raw_assumptions = parsed.get("assumptions")
    assumptions: list[str] = []
    if isinstance(raw_assumptions, list):
        for item in raw_assumptions:
            text = str(item or "").strip()
            if text:
                assumptions.append(text)
    holiday = _phrase(parsed.get("holiday"), "")
    if not holiday:
        raise StoryError("Holiday profile missing summary")
    if not assumptions:
        assumptions = [holiday]
    return HolidayProfile(
        pace=_phrase(parsed.get("pace"), "Unclear"),
        company=_phrase(parsed.get("company"), "Unclear"),
        setting=_phrase(parsed.get("setting"), "Unclear"),
        comfort=_phrase(parsed.get("comfort"), "Unclear"),
        food=_phrase(parsed.get("food"), "Unclear"),
        adventure=_phrase(parsed.get("adventure"), "Unclear"),
        assumptions=assumptions,
        holiday=holiday,
    )


def parse_holiday_profile(text: str) -> HolidayProfile:
    return normalize_profile(_extract_object(text))


def _history_prompt(
    genre: str,
    history: list[StoryEvent],
    selected: list[str] | None,
    turn_number: int,
) -> str:
    spec = beat_spec(turn_number)
    lines = [
        f"Genre: {genre}",
        f"Beat {turn_number} of {STORY_TURNS}.",
        f"Field to collect (backend-controlled): {spec['field']}",
        f"This beat must collect: {spec['collects']}",
        "Write in-genre fiction. Options must map to that field.",
    ]
    if not history:
        lines.append("Start the story. Offer the first choice-point.")
        return "\n".join(lines)
    lines.append("Story so far:")
    for event in history:
        lines.append(f"Beat {event.field} scene: {event.scene}")
        if event.selected:
            lines.append("Player chose: " + "; ".join(event.selected))
            if event.values:
                lines.append("Canonical values: " + "; ".join(event.values))
    if selected:
        lines.append("Player now chooses (honor ALL of these):")
        for item in selected:
            lines.append(f"- {item}")
    lines.append("Continue with the next field only.")
    return "\n".join(lines)


def _choice_log(
    genre: str,
    history: list[StoryEvent],
    destination: str | None = None,
    dates: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"Genre: {genre}",
        "Match the example JSON shape exactly.",
        "Choices the player made:",
    ]
    if not history:
        lines.append("(none yet)")
    else:
        for event in history:
            labels = "; ".join(event.selected) or "(no pick)"
            values = "; ".join(event.values) or labels
            lines.append(f"{event.field}: {labels} (value: {values})")
    if destination:
        lines.append(f"Destination: {destination}")
    if dates:
        lines.append(f"Dates: {json.dumps(dates)}")
    else:
        lines.append("Dates: unknown (not collected)")
    lines.append(
        "Infer the holiday they want in that destination when known. "
        "Be specific, like the example. Do not invent hotels, flights, or a day-by-day itinerary."
    )
    return "\n".join(lines)


StreamKind = Literal["narrative", "holiday", "turn", "profile"]


@dataclass
class StoryStreamEvent:
    kind: StreamKind
    text: str = ""
    turn: StoryTurn | None = None
    profile: HolidayProfile | None = None


def extract_partial_json_string(text: str, field_name: str) -> str | None:
    """Best-effort string value for a JSON field from a possibly incomplete object."""
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"', text)
    if not match:
        return None
    chars: list[str] = []
    index = match.end()
    escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            chars.append(escapes.get(text[index + 1], text[index + 1]))
            index += 2
            continue
        if char == '"':
            return "".join(chars)
        chars.append(char)
        index += 1
    return "".join(chars)


def _chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", None)
    if content is None and isinstance(chunk, str):
        return chunk
    return message_text(content)


def iter_llm_text(llm: Any, messages: list) -> Iterator[str]:
    stream_fn = getattr(llm, "stream", None)
    used_stream = False
    if callable(stream_fn):
        try:
            for chunk in stream_fn(messages):
                used_stream = True
                text = _chunk_text(chunk)
                if text:
                    yield text
        except NotImplementedError:
            used_stream = False
    if not used_stream:
        result = llm.invoke(messages)
        text = message_text(result.content)
        if text:
            yield text


def _finalize_turn(turn: StoryTurn, turn_number: int) -> StoryTurn:
    if len(turn.choices) < MIN_CHOICES:
        return fallback_turn(turn_number)
    turn.field = str(beat_spec(turn_number)["field"])
    return turn


def generate_turn_events(
    theme: str,
    history: list[StoryEvent] | None = None,
    selected: list[str] | None = None,
    llm_factory: Callable[[], Any] | None = None,
    turn_number: int = 1,
) -> Iterator[StoryStreamEvent]:
    genre = resolve_genre(theme)
    if not genre:
        raise StoryError("Pick a genre from the PRD list")
    factory = llm_factory or (lambda: get_llm_client(get_settings()))
    llm = factory()
    user = _history_prompt(genre, history or [], selected, turn_number)
    messages: list = [SystemMessage(content=STORY_AGENT_PROMPT), HumanMessage(content=user)]
    accumulated = ""
    last_narrative = ""
    for piece in iter_llm_text(llm, messages):
        accumulated += piece
        narrative = extract_partial_json_string(
            accumulated, "narrative_text"
        ) or extract_partial_json_string(accumulated, "scene")
        if narrative is not None and narrative != last_narrative:
            last_narrative = narrative
            yield StoryStreamEvent(kind="narrative", text=narrative)
    try:
        turn = parse_story_turn(accumulated, turn_number=turn_number)
    except StoryError:
        retry = llm.invoke(
            [
                *messages,
                HumanMessage(content="Return only the JSON object. No markdown, no explanation."),
            ]
        )
        try:
            turn = parse_story_turn(message_text(retry.content), turn_number=turn_number)
        except StoryError:
            turn = fallback_turn(turn_number)
    turn = _finalize_turn(turn, turn_number)
    if not last_narrative and turn.scene:
        yield StoryStreamEvent(kind="narrative", text=turn.scene)
    yield StoryStreamEvent(kind="turn", turn=turn)


def generate_turn(
    theme: str,
    history: list[StoryEvent] | None = None,
    selected: list[str] | None = None,
    llm_factory: Callable[[], Any] | None = None,
    turn_number: int = 1,
) -> StoryTurn:
    turn: StoryTurn | None = None
    for event in generate_turn_events(
        theme,
        history=history,
        selected=selected,
        llm_factory=llm_factory,
        turn_number=turn_number,
    ):
        if event.kind == "turn" and event.turn is not None:
            turn = event.turn
    if turn is None:
        return fallback_turn(turn_number)
    return turn


def generate_holiday_profile_events(
    theme: str,
    history: list[StoryEvent],
    llm_factory: Callable[[], Any] | None = None,
    destination: str | None = None,
    dates: dict[str, Any] | None = None,
) -> Iterator[StoryStreamEvent]:
    genre = resolve_genre(theme) or (theme.strip() if theme else "Fantasy")
    factory = llm_factory or (lambda: get_llm_client(get_settings()))
    llm = factory()
    user = _choice_log(genre, history, destination=destination, dates=dates)
    messages: list = [SystemMessage(content=PROFILE_AGENT_PROMPT), HumanMessage(content=user)]
    accumulated = ""
    last_holiday = ""
    for piece in iter_llm_text(llm, messages):
        accumulated += piece
        holiday = extract_partial_json_string(accumulated, "holiday")
        if holiday is not None and holiday != last_holiday:
            last_holiday = holiday
            yield StoryStreamEvent(kind="holiday", text=holiday)
    try:
        profile = parse_holiday_profile(accumulated)
    except StoryError:
        retry = llm.invoke(
            [
                *messages,
                HumanMessage(content="Return only the JSON object. No markdown, no explanation."),
            ]
        )
        profile = parse_holiday_profile(message_text(retry.content))
    if not last_holiday and profile.holiday:
        yield StoryStreamEvent(kind="holiday", text=profile.holiday)
    yield StoryStreamEvent(kind="profile", profile=profile)


def generate_holiday_profile(
    theme: str,
    history: list[StoryEvent],
    llm_factory: Callable[[], Any] | None = None,
    destination: str | None = None,
    dates: dict[str, Any] | None = None,
) -> HolidayProfile:
    profile: HolidayProfile | None = None
    for event in generate_holiday_profile_events(
        theme,
        history,
        llm_factory=llm_factory,
        destination=destination,
        dates=dates,
    ):
        if event.kind == "profile" and event.profile is not None:
            profile = event.profile
    if profile is None:
        raise StoryError("Holiday profile missing summary")
    return profile


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def story_context_payload(
    history: list[StoryEvent], profile: HolidayProfile | dict[str, Any]
) -> dict[str, Any]:
    profile_data = profile.to_dict() if isinstance(profile, HolidayProfile) else dict(profile)
    return {
        "answers": [
            {
                "field": event.field,
                "selected": event.selected,
                "values": event.values or event.selected,
            }
            for event in history
        ],
        "profile": profile_data,
    }


def maybe_summarize_story_context(
    history: list[StoryEvent],
    profile: HolidayProfile | dict[str, Any],
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any] | None:
    payload = story_context_payload(history, profile)
    raw = json.dumps(payload)
    if estimate_tokens(raw) <= STORY_CONTEXT_SUMMARIZE_TOKENS:
        return None
    factory = llm_factory or (lambda: get_llm_client(get_settings()))
    llm = factory()
    messages: list = [
        SystemMessage(content=SUMMARIZE_AGENT_PROMPT),
        HumanMessage(content=raw),
    ]
    result = llm.invoke(messages)
    return parse_holiday_profile(message_text(result.content)).to_dict()
