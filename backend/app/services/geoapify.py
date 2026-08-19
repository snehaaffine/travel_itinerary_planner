from typing import Any

import httpx

from app.config import Settings, get_settings
from app.constants import DEFAULT_POI_CATEGORIES, INTEREST_CATEGORIES

GEOCODE_AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
GEOCODE_SEARCH_URL = "https://api.geoapify.com/v1/geocode/search"
PLACES_URL = "https://api.geoapify.com/v2/places"


class GeoapifyError(Exception):
    pass


def _require_key(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.geoapify_api_key:
        raise GeoapifyError("GEOAPIFY_API_KEY is not configured")
    return settings.geoapify_api_key


def _feature_to_place(feature: dict[str, Any]) -> dict[str, Any] | None:
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    lon = props.get("lon")
    lat = props.get("lat")
    if lon is None and len(coords) >= 2:
        lon, lat = coords[0], coords[1]
    if lat is None or lon is None:
        return None
    name = props.get("city") or props.get("name") or props.get("formatted") or "Unknown"
    return {
        "name": name,
        "formatted": props.get("formatted") or name,
        "country": props.get("country"),
        "place_id": props.get("place_id") or "",
        "lat": float(lat),
        "lon": float(lon),
        "categories": props.get("categories") or [],
    }


def _result_to_place(result: dict[str, Any]) -> dict[str, Any] | None:
    lat = result.get("lat")
    lon = result.get("lon")
    if lat is None or lon is None:
        return None
    name = result.get("city") or result.get("name") or result.get("formatted") or "Unknown"
    return {
        "name": name,
        "formatted": result.get("formatted") or name,
        "country": result.get("country"),
        "place_id": result.get("place_id") or "",
        "lat": float(lat),
        "lon": float(lon),
        "categories": result.get("categories") or [],
    }


def autocomplete_cities(
    query: str,
    *,
    limit: int = 6,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    api_key = _require_key(settings)
    response = httpx.get(
        GEOCODE_AUTOCOMPLETE_URL,
        params={"text": query, "type": "city", "format": "json", "limit": limit, "apiKey": api_key},
        timeout=15.0,
    )
    if response.is_error:
        raise GeoapifyError(f"Autocomplete failed: {response.status_code}")
    data = response.json()
    places: list[dict[str, Any]] = []
    for item in data.get("results") or data.get("features") or []:
        parsed = _result_to_place(item) if "lat" in item else _feature_to_place(item)
        if parsed:
            places.append(parsed)
    return places


def geocode_destination(
    text: str,
    *,
    place_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    api_key = _require_key(settings)
    params: dict[str, Any] = {
        "text": text,
        "type": "city",
        "format": "json",
        "limit": 1,
        "apiKey": api_key,
    }
    response = httpx.get(GEOCODE_SEARCH_URL, params=params, timeout=15.0)
    if response.is_error:
        raise GeoapifyError(f"Geocode failed: {response.status_code}")
    data = response.json()
    results = data.get("results") or []
    if not results and data.get("features"):
        parsed = _feature_to_place(data["features"][0])
        if parsed:
            if place_id:
                parsed["place_id"] = place_id
            return parsed
        raise GeoapifyError("No geocoding results")
    if not results:
        raise GeoapifyError("No geocoding results")
    parsed = _result_to_place(results[0])
    if not parsed:
        raise GeoapifyError("No geocoding results")
    if place_id:
        parsed["place_id"] = place_id
    return parsed


def categories_for_interests(interests: list[str] | None) -> str:
    if not interests:
        return DEFAULT_POI_CATEGORIES
    cats: list[str] = []
    for interest in interests:
        mapped = INTEREST_CATEGORIES.get(interest.strip().lower())
        if mapped:
            cats.extend(mapped.split(","))
    unique = list(dict.fromkeys(cats))
    return ",".join(unique) if unique else DEFAULT_POI_CATEGORIES


def search_places(
    *,
    lat: float,
    lon: float,
    place_id: str | None,
    interests: list[str] | None,
    pets: bool = False,
    limit: int = 20,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    api_key = _require_key(settings)
    categories = categories_for_interests(interests)
    params: dict[str, Any] = {
        "categories": categories,
        "limit": limit,
        "lang": "en",
        "apiKey": api_key,
        "bias": f"proximity:{lon},{lat}",
    }
    if place_id:
        params["filter"] = f"place:{place_id}"
    else:
        params["filter"] = f"circle:{lon},{lat},15000"
    if pets:
        params["conditions"] = "dogs.yes"

    response = httpx.get(PLACES_URL, params=params, timeout=20.0)
    if response.is_error:
        raise GeoapifyError(f"Places failed: {response.status_code}")
    data = response.json()
    places: list[dict[str, Any]] = []
    for feature in data.get("features") or []:
        props = feature.get("properties") or {}
        cats = props.get("categories") or []
        if any(str(cat).startswith("accommodation") for cat in cats):
            continue
        parsed = _feature_to_place(feature)
        if parsed:
            parsed["name"] = props.get("name") or parsed["name"]
            parsed["formatted"] = props.get("formatted") or parsed["formatted"]
            places.append(parsed)
    return places
