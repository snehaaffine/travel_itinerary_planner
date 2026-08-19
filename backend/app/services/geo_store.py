import json
from uuid import UUID

from app.cache.redis import get_redis
from app.constants import GEOCODE_TTL_SECONDS, INTEREST_TTL_SECONDS, PLACES_TTL_SECONDS


def cache_trip_geo(trip_id: UUID, geo: dict) -> None:
    get_redis().setex(f"trip:{trip_id}:geo", GEOCODE_TTL_SECONDS, json.dumps(geo))


def get_trip_geo(trip_id: UUID) -> dict | None:
    raw = get_redis().get(f"trip:{trip_id}:geo")
    if not raw:
        return None
    return json.loads(raw)


def cache_geocode(key: str, geo: dict) -> None:
    get_redis().setex(f"geoapify:geocode:{key.lower()}", GEOCODE_TTL_SECONDS, json.dumps(geo))


def get_cached_geocode(key: str) -> dict | None:
    raw = get_redis().get(f"geoapify:geocode:{key.lower()}")
    return json.loads(raw) if raw else None


def cache_places(cache_key: str, places: list[dict]) -> None:
    get_redis().setex(f"geoapify:places:{cache_key}", PLACES_TTL_SECONDS, json.dumps(places))


def get_cached_places(cache_key: str) -> list[dict] | None:
    raw = get_redis().get(f"geoapify:places:{cache_key}")
    return json.loads(raw) if raw else None


def cache_interest_tags(destination: str, tags: list[str]) -> None:
    get_redis().setex(
        f"interests:{destination.strip().lower()}", INTEREST_TTL_SECONDS, json.dumps(tags)
    )


def get_cached_interest_tags(destination: str) -> list[str] | None:
    raw = get_redis().get(f"interests:{destination.strip().lower()}")
    return json.loads(raw) if raw else None
