import logging
from typing import Any

import httpx

from app.config import Settings
from app.services.geoapify.common import GeoapifyError, require_key

STATICMAP_URL = "https://maps.geoapify.com/v1/staticmap"
MAP_FOREST = "#333d29"   # activity/attraction pins
MAP_GOLD = "#c8a96e"     # meal/dining pins
MAP_STYLE = "osm-bright"

logger = logging.getLogger(__name__)


def static_map_marker(
    lon: float,
    lat: float,
    *,
    color: str,
    size: str = "medium",
    text: str | None = None,
) -> dict[str, Any]:
    marker: dict[str, Any] = {
        "lon": lon,
        "lat": lat,
        "type": "circle",
        "color": color,
        "size": size,
        "contentcolor": "#ffffff",
    }
    if text:
        marker["text"] = text
        marker["textsize"] = "medium"
    return marker


def map_area_rect(markers: list[tuple[float, float]], pad: float | None = None) -> dict[str, Any]:
    lons = [point[0] for point in markers]
    lats = [point[1] for point in markers]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    span_lon = max(east - west, 0.0)
    span_lat = max(north - south, 0.0)
    pad_lon = pad if pad is not None else max(span_lon * 0.16, 0.0035)
    pad_lat = pad if pad is not None else max(span_lat * 0.16, 0.0035)
    return {
        "type": "rect",
        "value": {
            "lon1": west - pad_lon,
            "lat1": north + pad_lat,
            "lon2": east + pad_lon,
            "lat2": south - pad_lat,
        },
    }


def map_center(points: list[tuple[float, float]]) -> dict[str, float]:
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return {"lon": (min(lons) + max(lons)) / 2, "lat": (min(lats) + max(lats)) / 2}

def static_map_request_body(
    points: list[tuple[float, float, str]],
    *,
    width: int = 800,
    height: int = 400,
) -> dict[str, Any]:
    markers = [
        static_map_marker(
            lon,
            lat,
            color=MAP_GOLD if kind == "meal" else MAP_FOREST,
            text=str(index),
        )
        for index, (lon, lat, kind) in enumerate(points, start=1)
    ]
    body: dict[str, Any] = {
        "style": MAP_STYLE,
        "width": width,
        "height": height,
        "format": "png",
        "markers": markers,
    }
    coords = [(lon, lat) for lon, lat, _ in points]
    if len(coords) == 1:
        # A single stop has no bounding box to fit — center + a sane zoom.
        body["center"] = map_center(coords)
        body["zoom"] = 14
    else:
        body["area"] = map_area_rect(coords)
    return body


def fetch_static_map(
    *,
    lat: float,
    lon: float,
    markers: list[tuple[float, float, str]] | None = None,
    width: int = 800,
    height: int = 400,
    settings: Settings | None = None,
) -> bytes | None:
    try:
        api_key = require_key(settings)
    except GeoapifyError:
        logger.warning("Static map skipped: GEOAPIFY_API_KEY is not configured")
        return None
    points: list[tuple[float, float, str]] = []
    seen: set[tuple[float, float]] = set()
    for marker_lon, marker_lat, kind in markers or [(lon, lat, "activity")]:
        key = (round(marker_lon, 5), round(marker_lat, 5))
        if key in seen:
            continue
        seen.add(key)
        points.append((marker_lon, marker_lat, kind))
        if len(points) >= 12:
            break
    if not points:
        points = [(lon, lat, "activity")]
    body = static_map_request_body(points, width=width, height=height)
    try:
        response = httpx.post(
            STATICMAP_URL,
            params={"apiKey": api_key},
            json=body,
            timeout=45.0,
        )
    except httpx.HTTPError:
        logger.warning("Static map request failed", exc_info=True)
        return None
    if response.is_error:
        logger.warning(
            "Static map API error %s: %s",
            response.status_code,
            (response.text or "")[:300],
        )
        return None
    content_type = (response.headers.get("content-type") or "").lower()
    if "image" not in content_type and not response.content.startswith(
        (b"\x89PNG", b"\xff\xd8")
    ):
        logger.warning("Static map returned non-image content-type %s", content_type)
        return None
    return response.content
