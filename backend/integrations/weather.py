from __future__ import annotations

import time
from typing import Optional

import httpx

# ----------------
# WMO weather code
# https://open-meteo.com/en/docs#weathervariables
# ----------------
_UNREACHABLE = "⚠️ weer niet beschikbaar"
_UNKNOWN_LOCATION = "📍 locatie niet herkend"
_WMO_CODES: dict[int, str] = {
    0:  "☀️ helder",
    1:  "🌤️ grotendeels helder",
    2:  "⛅ gedeeltelijk bewolkt",
    3:  "☁️ bewolkt",
    45: "🌫️ mist",
    48: "🌫️ rijpmist",
    51: "🌦️ lichte motregen",
    53: "🌦️ motregen",
    55: "🌧️ zware motregen",
    61: "🌧️ lichte regen",
    63: "🌧️ regen",
    65: "🌧️ zware regen",
    71: "🌨️ lichte sneeuw",
    73: "🌨️ sneeuw",
    75: "❄️ zware sneeuw",
    77: "🌨️ sneeuwkorrels",
    80: "🌦️ lichte buien",
    81: "🌧️ buien",
    82: "⛈️ zware buien",
    85: "🌨️ sneeuwbuien",
    86: "❄️ zware sneeuwbuien",
    95: "⛈️ onweer",
    96: "⛈️ onweer met hagel",
    99: "⛈️ zwaar onweer met hagel",
}

# ----------------
# Eenvoudige in-memory cache
# ----------------
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 30 * 60  # 30 minuten

async def get_weather(location: str) -> Optional[str]:
    location_key = location.strip().lower()

    # Cache
    if location_key in _cache:
        cached_str, cached_at = _cache[location_key]
        if time.monotonic() - cached_at < _CACHE_TTL:
            return cached_str

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Stap 1: geocoding
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": location,
                    "count": 1,
                    "language": "nl",
                    "format": "json",
                },
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results:
                return _UNKNOWN_LOCATION

            lat = results[0]["latitude"]
            lon = results[0]["longitude"]

            # Stap 2: weerdata ophalen
            weather_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,weathercode,wind_speed_10m",
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                },
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()

        current = weather_data["current"]
        temp = round(current["temperature_2m"])
        code = current["weathercode"]
        description = _WMO_CODES.get(code, "onbekend")

        result = f"{temp}°C, {description}"
        _cache[location_key] = (result, time.monotonic())
        return result

    except Exception:
        return _UNREACHABLE