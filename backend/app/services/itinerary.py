import base64
import json
import logging
import re
from collections.abc import Callable
from datetime import date
from typing import Any
from uuid import UUID

import httpx
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app.cache.redis import get_redis
from app.config import get_settings
from app.constants import (
    DEFAULT_ITINERARY_DAYS,
    GEOCODE_TTL_SECONDS,
    ITINERARY_RATE_LIMIT,
    ITINERARY_RATE_WINDOW_SECONDS,
    MAX_ACTIVITIES_PER_DAY,
    MAX_ITINERARY_DAYS,
    ORCHESTRATOR_AGENT_ROUNDS,
)
from app.db.models import Itinerary, TripPath, TripState
from app.llm.provider import get_llm_client
from app.services.agents import AgentError, message_text, run_specialist, run_tool_agent
from app.services.geo_store import (
    cache_geocode,
    cache_places,
    cache_trip_geo,
    get_cached_geocode,
    get_cached_places,
    get_trip_geo,
)
from app.services.geoapify.common import GeoapifyError
from app.services.geoapify.map import fetch_static_map
from app.services.geoapify.poi import geocode_destination, geocode_place, search_places
from app.services.interests import interest_sentence
from app.services.weather import fetch_weather

logger = logging.getLogger(__name__)


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
Call search_tool to find (1) extra context for the destination and (2) nearby
towns, palaces, parks, or landmarks reachable by road in about 90 minutes
or less — for example Paris → Versailles, not a flight to another country.
If the tool is unavailable, say so briefly. English only. No itinerary JSON."""

NEARBY_ROAD_RULES = """
Nearby by road:
- Keep the trip based at the chosen destination.
- Include nearby places that can be reached by road, train, or local transit
  in about 90 minutes (day trips). Example: Paris → Versailles.
- Do not send the traveler to a far city that needs a flight.
- Put those nearby stops on their own day or as a day's location/city when
  they are worth the trip. Name the real place in location and city fields
  so it can be pinned on a map.
- Call search_agent for nearby road-trip ideas if poi_agent only covers the
  main destination.
"""

ORCHESTRATOR_PROMPT = """You are the itinerary orchestrator.
You do not call weather, places, or search APIs yourself.
You have specialist agents that make those calls and return briefings:
- weather_agent: forecast/climate for the destination and dates
- poi_agent: real points of interest matching traveler interests
- search_agent: extra web context and nearby places reachable by road

Call weather_agent and poi_agent before writing the itinerary.
Use search_agent for nearby day-trip towns if the briefing is thin or only
covers the main city.
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
""" + NEARBY_ROAD_RULES

ORCHESTRATOR_PROMPT_STORY = """You are the itinerary orchestrator.
You do not call weather, places, or search APIs yourself.
You have specialist agents that make those calls and return briefings:
- weather_agent: forecast/climate for the destination and dates
- poi_agent: real points of interest matching traveler interests
- search_agent: extra web context for the holiday profile, including nearby
  places reachable by road and the news (for safety reasons)

Call weather_agent and poi_agent before writing the itinerary.
Call search_agent for places that fit the holiday profile in the destination
and for nearby towns reachable by road (for example Paris → Versailles).
Budget and diet were not collected — stay neutral. Do not assume luxury or
budget travel, and do not invent dietary restrictions.
Then compile the specialist briefings into ONE itinerary.
Return ONLY valid JSON with this shape:
{"days":[{"day":1,"dayLabel":"Day 1","date":null,"city":"","country":"",
"summary":"","activities":[{"title":"","description":"","location":"",
"notes":""}],"meals":[{"type":"Lunch","venue":"","notes":""}]}],"notes":""}
Rules:
- English only
- At most 4 activities per day — a focused day, not a packed schedule
- Do not include times, clock hours, or morning/afternoon/evening labels
- Do not tell the traveler when to do each activity
- No visa, booking, hotels, flights, accommodation names, or regenerate language
- Use real POI names from poi_agent in location and dining venues
- Match the requested number of days
- Only include a meal when poi_agent gave a real venue name; omit meals with no place
""" + NEARBY_ROAD_RULES


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
    if trip.path == TripPath.STORY:
        lines = [
            "Path: story",
            f"Destination: {trip.destination}",
            f"Dates: {date_note}",
            f"Days to plan: {days}",
            f"Companions / trip type: {trip.trip_type}",
            f"Pets: {trip.pets}",
            f"Interests: {', '.join(trip.interests or [])}",
            f"Pace: {trip.pace or 'Not specified'}",
            f"Food style: {trip.food_preference or 'Not specified'}",
            f"Flavor: {trip.flavor_preference or 'Not specified'}",
            "Budget: not collected — stay neutral; do not assume luxury or budget.",
            "Diet: not collected — do not invent dietary restrictions.",
            "Call search_agent for places that fit the holiday profile, including "
            "nearby towns reachable by road (for example Paris → Versailles).",
            "Do not send the traveler somewhere that needs a flight.",
            f"Max activities per day: {MAX_ACTIVITIES_PER_DAY}",
        ]
        from app.services.story_flow import holiday_profile_from_trip

        profile = holiday_profile_from_trip(trip)
        if profile:
            lines.append("Holiday profile JSON:")
            lines.append(json.dumps(profile))
        return "\n".join(lines) + "\n"
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
        "Include nearby places reachable by road in about 90 minutes "
        "(for example Paris → Versailles). Do not plan a flight to another city.\n"
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
        cache_key = _places_cache_key(trip, geo)
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
                "lat": place.get("lat"),
                "lon": place.get("lon"),
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
        settings = get_settings()
        api_key = settings.tavily_api_key
        if not api_key:
            return "Search tool unavailable in this phase."
        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query, "max_results": 5, "search_depth": "basic"},
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return "Search tool unavailable in this phase."
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return json.dumps({"results": []})
        compact = [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
            }
            for item in results[:5]
            if isinstance(item, dict)
        ]
        return json.dumps(compact)

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
            description="Ask the search specialist for nearby road-trip places.",
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
    system = ORCHESTRATOR_PROMPT_STORY if trip.path == TripPath.STORY else ORCHESTRATOR_PROMPT

    try:
        run = run_tool_agent(
            system=system,
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


def _places_cache_key(trip: TripState, geo: dict[str, Any]) -> str:
    interests = list(trip.interests or [])
    return f"{geo.get('place_id') or trip.destination}:{','.join(interests)}:{trip.pets}"


def _day_location_labels(day: dict[str, Any]) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    activities = day.get("activities") or day.get("items") or []
    if isinstance(activities, list):
        for activity in activities[:MAX_ACTIVITIES_PER_DAY]:
            if not isinstance(activity, dict):
                continue
            text = str(
                activity.get("location")
                or activity.get("place_name")
                or activity.get("title")
                or ""
            ).strip()
            if text:
                labels.append((text, "activity"))
    meals = day.get("meals") or []
    if isinstance(meals, list):
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            venue = str(meal.get("venue") or "").strip()
            if venue:
                labels.append((venue, "meal"))
    return labels


def _match_place_coords(
    label: str, places: list[dict[str, Any]]
) -> tuple[float, float] | None:
    needle = label.strip().lower()
    if not needle:
        return None
    for place in places:
        name = str(place.get("name") or "").lower()
        formatted = str(place.get("formatted") or "").lower()
        if name and (name in needle or needle in name):
            try:
                return float(place["lon"]), float(place["lat"])
            except (KeyError, TypeError, ValueError):
                continue
        if formatted and (formatted in needle or needle in formatted):
            try:
                return float(place["lon"]), float(place["lat"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def _geocode_label(label: str, geo: dict[str, Any]) -> tuple[float, float] | None:
    cache_key = (
        f"{label.strip().lower()}:"
        f"{round(float(geo['lat']), 3)}:{round(float(geo['lon']), 3)}"
    )
    cached = get_cached_geocode(cache_key)
    if cached:
        try:
            return float(cached["lon"]), float(cached["lat"])
        except (KeyError, TypeError, ValueError):
            pass
    parsed = geocode_place(label, lat=float(geo["lat"]), lon=float(geo["lon"]))
    if not parsed:
        return None
    cache_geocode(cache_key, parsed)
    try:
        return float(parsed["lon"]), float(parsed["lat"])
    except (KeyError, TypeError, ValueError):
        return None


def _markers_for_day(
    day: dict[str, Any],
    geo: dict[str, Any],
    places: list[dict[str, Any]],
) -> list[tuple[float, float, str]]:
    try:
        fallback = (float(geo["lon"]), float(geo["lat"]))
    except (KeyError, TypeError, ValueError):
        fallback = None
    markers: list[tuple[float, float, str]] = []
    seen: set[tuple[float, float]] = set()
    for index, (label, kind) in enumerate(_day_location_labels(day)):
        point = _match_place_coords(label, places) or _geocode_label(label, geo) or fallback
        if not point:
            continue
        key = (round(point[0], 5), round(point[1], 5))
        if key in seen:
            point = (point[0] + 0.00022 * (index + 1), point[1] + 0.00014 * (index + 1))
            key = (round(point[0], 5), round(point[1], 5))
        seen.add(key)
        markers.append((point[0], point[1], kind))
    if markers:
        return markers
    return [(fallback[0], fallback[1], "activity")] if fallback else []


def _map_markers(
    places: list[dict[str, Any]], content: dict[str, Any]
) -> list[tuple[float, float, str]]:
    days = content.get("days") or []
    if not days or not isinstance(days[0], dict):
        return []
    geo = {"lat": 0.0, "lon": 0.0}
    for place in places:
        try:
            geo = {"lat": float(place["lat"]), "lon": float(place["lon"])}
            break
        except (KeyError, TypeError, ValueError):
            continue
    return _markers_for_day(days[0], geo, places)


def _store_map_image(itinerary_id: UUID, day_number: int, png: bytes) -> None:
    get_redis().setex(
        f"itinerary:{itinerary_id}:map:v4:{day_number}",
        GEOCODE_TTL_SECONDS,
        base64.b64encode(png).decode("ascii"),
    )


def render_day_map(itinerary: Itinerary, trip: TripState, day_number: int) -> bytes | None:
    try:
        geo = _resolve_geo(trip)
        lat = float(geo["lat"])
        lon = float(geo["lon"])
    except (KeyError, TypeError, ValueError, ItineraryError):
        return None
    content = itinerary.content if isinstance(itinerary.content, dict) else {}
    day = next(
        (
            item
            for item in content.get("days") or []
            if isinstance(item, dict) and int(item.get("day") or 0) == day_number
        ),
        None,
    )
    if day is None:
        return None
    places = get_cached_places(_places_cache_key(trip, geo)) or []
    markers = _markers_for_day(day, geo, places)
    return fetch_static_map(lat=lat, lon=lon, markers=markers, width=420, height=620)


def get_or_create_map_image(
    itinerary: Itinerary, trip: TripState, day_number: int
) -> bytes | None:
    cached = get_cached_map_image(itinerary.id, day_number)
    if cached:
        return cached
    png = render_day_map(itinerary, trip, day_number)
    if not png:
        logger.warning("No static map image for itinerary day %s", day_number)
        return None
    _store_map_image(itinerary.id, day_number, png)
    return png


def get_cached_map_image(itinerary_id: UUID, day_number: int = 1) -> bytes | None:
    raw = get_redis().get(f"itinerary:{itinerary_id}:map:v4:{day_number}")
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except (TypeError, ValueError):
        return None


def check_rate_limit(trip_id: UUID, client_ip: str) -> bool:
    if not get_settings().rate_limits_enabled:
        return True
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
