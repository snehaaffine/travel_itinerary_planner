from datetime import date, timedelta
from typing import Any

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CLIMATE_URL = "https://climate-api.open-meteo.com/v1/climate"


def _summarize_daily(daily: dict[str, Any]) -> str:
    dates = daily.get("time") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or daily.get("precipitation_probability_max") or []
    lines: list[str] = []
    for index, day in enumerate(dates[:14]):
        high = highs[index] if index < len(highs) else "?"
        low = lows[index] if index < len(lows) else "?"
        rain = precip[index] if index < len(precip) else "?"
        lines.append(f"{day}: high {high}C, low {low}C, precip {rain}")
    return "\n".join(lines) if lines else "No weather data"


def fetch_weather(lat: float, lon: float, start: str | None, end: str | None) -> str:
    try:
        if start and end:
            response = httpx.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "timezone": "auto",
                    "start_date": start,
                    "end_date": end,
                },
                timeout=15.0,
            )
            if not response.is_error:
                return _summarize_daily(response.json().get("daily") or {})
        start_climate = date.today().replace(year=date.today().year - 1)
        end_climate = start_climate + timedelta(days=6)
        response = httpx.get(
            CLIMATE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start_climate.isoformat(),
                "end_date": end_climate.isoformat(),
                "models": "EC_Earth3P_HR",
                "daily": "temperature_2m_mean",
            },
            timeout=15.0,
        )
        if response.is_error:
            return "Weather unavailable"
        daily = response.json().get("daily") or {}
        return "Typical climate (forecast unavailable):\n" + _summarize_daily(daily)
    except httpx.HTTPError:
        return "Weather unavailable"
