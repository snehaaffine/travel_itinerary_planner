import json
import re
from collections.abc import Callable
from datetime import date
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    DEFAULT_ITINERARY_DAYS,
    ITINERARY_RATE_LIMIT,
    ITINERARY_RATE_WINDOW_SECONDS,
    MAX_ACTIVITIES_PER_DAY,
    MAX_ITINERARY_DAYS,
    ORCHESTRATOR_AGENT_ROUNDS,
)
from app.db.models import Itinerary, TripState
from app.llm.provider import get_llm_client
from app.services.agents import AgentError, message_text, run_specialist, run_tool_agent
from app.services.geo_store import cache_places, cache_trip_geo, get_cached_places, get_trip_geo
from app.services.geoapify import GeoapifyError, geocode_destination, search_places
from app.services.interests import interest_sentence
from app.services.weather import fetch_weather


class ItineraryError(Exception):
    pass


USER_GENERATION_ERROR = "We couldn't put this trip together just now. Go back and try again."

WEATHER_SPECIALIST_PROMPT = """You are the weather specialist for a travel planner.
Call weather_tool, then write a short briefing for the itinerary orchestrator.
Cover temperature, rain risk, and outdoor vs indoor implications.
English only. No itinerary JSON."""

POI_SPECIALIST_PROMPT = """You are the points-of-interest specialist for a travel planner.
Call poi_tool, then write a short briefing of real places grouped by interest.
Prefer venues that fit the traveler budget and diet constraints.
Use venue names from the tool. English only. No hotels, bookings, or itinerary JSON."""

SEARCH_SPECIALIST_PROMPT = """You are the search specialist for a travel planner.
Call search_tool if extra context would help, then report what you found.
If the tool is unavailable, say so briefly. English only. No itinerary JSON."""

ORCHESTRATOR_PROMPT = """You are the itinerary orchestrator.
You do not call weather, places, or search APIs yourself.
You have specialist agents that make those calls and return briefings:
- weather_agent: forecast/climate for the destination and dates
- poi_agent: real points of interest matching traveler interests
- search_agent: extra web context (may be unavailable)

Call weather_agent and poi_agent before writing the itinerary.
Use search_agent only if a briefing is thin.
Then compile the specialist briefings into ONE itinerary.
Return ONLY valid JSON with this shape:
{"days":[{"day":1,"dayLabel":"Day 1","date":null,"city":"","country":"",
"summary":"","activities":[{"title":"","description":"","location":"",
"notes":""}],"meals":[{"type":"Lunch","venue":"","notes":""}]}],"notes":""}
Rules:
- English only
- At most 3 activities per day — a focused day, not a packed schedule
- Do not include times, clock hours, or morning/afternoon/evening labels
- Do not tell the traveler when to do each activity
- No visa, booking, hotels, flights, accommodation names, or regenerate language
- Fit activities and dining to the stated budget without listing prices
- Honor diet constraints in meals and food-related stops
- Use real POI names from poi_agent in location and dining venues
- Match the requested number of days
- Only include a meal when poi_agent gave a real venue name; omit meals with no place
"""


def _day_count(dates: dict | None) -> int:
    if not dates:
        return DEFAULT_ITINERARY_DAYS
    try:
        start = date.fromisoformat(dates["start"])
        end = date.fromisoformat(dates["end"])
    except (KeyError, TypeError, ValueError):
        return DEFAULT_ITINERARY_DAYS
    days = (end - start).days + 1
    return max(1, min(days, MAX_ITINERARY_DAYS))


def _resolve_geo(trip: TripState) -> dict[str, Any]:
    geo = get_trip_geo(trip.id)
    if geo:
        return geo
    geo = geocode_destination(trip.destination)
    cache_trip_geo(trip.id, geo)
    return geo


def _trip_brief(trip: TripState) -> str:
    days = _day_count(trip.dates)
    date_note = json.dumps(trip.dates) if trip.dates else "flexible / no dates yet"
    diets = trip.food_preference or "No restrictions"
    budget = trip.flavor_preference or "Not specified"
    return (
        f"Destination: {trip.destination}\n"
        f"Dates: {date_note}\n"
        f"Days to plan: {days}\n"
        f"Trip type: {trip.trip_type}\n"
        f"Pets: {trip.pets}\n"
        f"Interests: {', '.join(trip.interests or [])}\n"
        f"Budget: {budget}\n"
        f"Diet: {diets}\n"
        f"Max activities per day: {MAX_ACTIVITIES_PER_DAY}\n"
    )


def _weather_tool(trip: TripState, geo: dict[str, Any]) -> StructuredTool:
    lat = float(geo["lat"])
    lon = float(geo["lon"])
    dates = trip.dates or {}
    start = dates.get("start") if isinstance(dates, dict) else None
    end = dates.get("end") if isinstance(dates, dict) else None

    def weather_tool() -> str:
        return fetch_weather(lat, lon, start, end)

    return StructuredTool.from_function(
        name="weather_tool",
        description="Get weather or climate for the trip destination and dates.",
        func=weather_tool,
    )


def _poi_tool(trip: TripState, geo: dict[str, Any]) -> StructuredTool:
    lat = float(geo["lat"])
    lon = float(geo["lon"])
    place_id = geo.get("place_id")
    interests = list(trip.interests or [])

    def poi_tool() -> str:
        cache_key = f"{place_id or trip.destination}:{','.join(interests)}:{trip.pets}"
        cached = get_cached_places(cache_key)
        if cached is not None:
            places = cached
        else:
            try:
                places = search_places(
                    lat=lat,
                    lon=lon,
                    place_id=place_id,
                    interests=interests,
                    pets=trip.pets,
                )
            except GeoapifyError as exc:
                return json.dumps({"error": str(exc), "places": []})
            cache_places(cache_key, places)
        compact = [
            {
                "name": place["name"],
                "formatted": place["formatted"],
                "categories": place.get("categories", []),
            }
            for place in places[:20]
        ]
        return json.dumps(compact)

    return StructuredTool.from_function(
        name="poi_tool",
        description="Get points of interest for the destination matching traveler interests.",
        func=poi_tool,
    )


def _search_tool() -> StructuredTool:
    def search_tool(query: str = "") -> str:
        return "Search tool unavailable in this phase."

    return StructuredTool.from_function(
        name="search_tool",
        description="General web search fallback. Currently a no-op stub.",
        func=search_tool,
    )


def _build_orchestrator_tools(
    trip: TripState,
    geo: dict[str, Any],
    llm_factory: Callable[[], Any] | None = None,
) -> list[StructuredTool]:
    brief = _trip_brief(trip)
    weather = _weather_tool(trip, geo)
    poi = _poi_tool(trip, geo)
    search = _search_tool()

    def weather_agent(task: str = "") -> str:
        return run_specialist(
            name="weather_agent",
            system=WEATHER_SPECIALIST_PROMPT,
            task=task or brief,
            tools=[weather],
            llm_factory=llm_factory,
        )

    def poi_agent(task: str = "") -> str:
        return run_specialist(
            name="poi_agent",
            system=POI_SPECIALIST_PROMPT,
            task=task or brief,
            tools=[poi],
            llm_factory=llm_factory,
        )

    def search_agent(task: str = "") -> str:
        return run_specialist(
            name="search_agent",
            system=SEARCH_SPECIALIST_PROMPT,
            task=task or brief,
            tools=[search],
            llm_factory=llm_factory,
        )

    return [
        StructuredTool.from_function(
            name="weather_agent",
            description="Ask the weather specialist to fetch forecast/climate and brief you.",
            func=weather_agent,
        ),
        StructuredTool.from_function(
            name="poi_agent",
            description="Ask the POI specialist to fetch places matching interests and brief you.",
            func=poi_agent,
        ),
        StructuredTool.from_function(
            name="search_agent",
            description="Ask the search specialist for extra web context. May be unavailable.",
            func=search_agent,
        ),
    ]


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ItineraryError("Model did not return JSON")
    snippet = cleaned[start : end + 1]
    candidates = [snippet, re.sub(r",\s*([}\]])", r"\1", snippet)]
    parsed: dict[str, Any] | None = None
    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            parsed = loaded
            break
    if parsed is None:
        raise ItineraryError("Model JSON was invalid")
    if "days" not in parsed:
        raise ItineraryError("Itinerary JSON missing days")
    return _normalize_itinerary(parsed)


def _has_meal_venue(meal: dict[str, Any]) -> bool:
    venue = str(meal.get("venue") or "").strip()
    if not venue:
        return False
    return venue.lower() not in {"n/a", "na", "none", "tbd", "unknown", "-", "—"}


def _normalize_itinerary(parsed: dict[str, Any]) -> dict[str, Any]:
    days = parsed.get("days")
    if not isinstance(days, list):
        return parsed
    for day in days:
        if not isinstance(day, dict):
            continue
        activities = day.get("activities") or day.get("items") or []
        if not isinstance(activities, list):
            activities = []
        trimmed: list[dict[str, Any]] = []
        for activity in activities[:MAX_ACTIVITIES_PER_DAY]:
            if not isinstance(activity, dict):
                continue
            item = dict(activity)
            item.pop("time", None)
            trimmed.append(item)
        day["activities"] = trimmed
        day.pop("items", None)
        meals = day.get("meals")
        if isinstance(meals, list):
            day["meals"] = [
                meal
                for meal in meals
                if isinstance(meal, dict) and _has_meal_venue(meal)
            ]
        else:
            day.pop("meals", None)
    return parsed


def generate_itinerary_content(
    trip: TripState,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    geo = _resolve_geo(trip)
    tools = _build_orchestrator_tools(trip, geo, llm_factory=llm_factory)
    factory = llm_factory or (lambda: get_llm_client(get_settings()))
    llm = factory()
    brief = _trip_brief(trip)

    try:
        run = run_tool_agent(
            system=ORCHESTRATOR_PROMPT,
            user=brief,
            tools=tools,
            max_rounds=ORCHESTRATOR_AGENT_ROUNDS,
            llm=llm,
        )
    except AgentError as exc:
        raise ItineraryError("Itinerary generation did not complete") from exc

    try:
        parsed = _extract_json(run.text)
    except ItineraryError:
        run.messages.append(
            HumanMessage(
                content=(
                    "Return only the itinerary JSON object compiled from the specialist "
                    "briefings. No markdown, no explanation."
                )
            )
        )
        retry = run.llm.invoke(run.messages)
        parsed = _extract_json(message_text(retry.content))
    parsed["interestSummary"] = interest_sentence(trip.destination, trip.interests)
    return parsed


def check_rate_limit(trip_id: UUID, client_ip: str) -> bool:
    from app.cache.redis import get_redis

    redis = get_redis()
    keys = [f"ratelimit:itinerary:trip:{trip_id}", f"ratelimit:itinerary:ip:{client_ip}"]
    for key in keys:
        current = redis.incr(key)
        if current == 1:
            redis.expire(key, ITINERARY_RATE_WINDOW_SECONDS)
        if current > ITINERARY_RATE_LIMIT:
            return False
    return True


def trip_is_complete(trip: TripState) -> bool:
    return bool(trip.destination and trip.trip_type and trip.flavor_preference)


def create_itinerary(db: Session, trip: TripState) -> Itinerary:
    existing = db.query(Itinerary).filter(Itinerary.trip_state_id == trip.id).first()
    if existing:
        raise ItineraryError("Itinerary already exists for this trip")
    if not trip_is_complete(trip):
        raise ItineraryError("Template details are incomplete")
    content = generate_itinerary_content(trip)
    itinerary = Itinerary(trip_state_id=trip.id, content=content)
    db.add(itinerary)
    db.commit()
    db.refresh(itinerary)
    return itinerary
