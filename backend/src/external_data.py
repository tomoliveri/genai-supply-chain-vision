"""
External context data for the supply-chain disruption pipeline.

Four data sources, all free and automatable:
1.  **Weather** — Open-Meteo API (no key required).  Daily temperature, wind,
    precipitation, and a derived severity score.
2.  **Labour strikes** — Static JSON database at ``backend/data/labor_events.json``.
    Editable manually or via a future RSS/API feed.
3.  **Peak season** — Calendar-based heuristic using month and hemisphere.
4.  **Geopolitical / conflict** — Static JSON database at
    ``backend/data/geopolitical_events.json``.  Armed conflicts, security
    incidents, legal rulings, route disruptions, trade policy changes.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final, TypedDict

import requests

from backend.src.geopolitical import (
    GeopoliticalContext,
    check_geopolitical,
    format_geopolitical_for_gemini,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class WeatherContext(TypedDict):
    summary: str          # e.g. "Clear / 22°C / Wind 12 kt SW"
    severity: int         # 1 = calm … 5 = gale / blizzard / flood
    code: str             # "clear", "rain", "storm", "fog", "snow", …

class LaborContext(TypedDict):
    status: str           # "Normal", "Strike warning", "Strike active"
    detail: str           # e.g. "ILA contract expires 2026-09-30"

class ExternalContext(TypedDict):
    weather: WeatherContext
    labor: LaborContext
    peak_season: bool
    geopolitical: GeopoliticalContext

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPEN_METEO_FORECAST: Final[str] = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_ARCHIVE: Final[str] = "https://archive-api.open-meteo.com/v1/archive"

# WMO weather-code
_WMO_CODE_MAP: Final[dict[int, tuple[str, int]]] = {
    0:  ("Clear", 1),
    1:  ("Mainly clear", 1),
    2:  ("Partly cloudy", 1),
    3:  ("Overcast", 1),
    45: ("Fog", 2),
    48: ("Depositing rime fog", 2),
    51: ("Light drizzle", 2),
    53: ("Moderate drizzle", 2),
    55: ("Dense drizzle", 3),
    56: ("Light freezing drizzle", 2),
    57: ("Dense freezing drizzle", 3),
    61: ("Slight rain", 2),
    63: ("Moderate rain", 3),
    65: ("Heavy rain", 4),
    66: ("Light freezing rain", 3),
    67: ("Heavy freezing rain", 4),
    71: ("Slight snow", 2),
    73: ("Moderate snow", 3),
    75: ("Heavy snow", 4),
    77: ("Snow grains", 2),
    80: ("Slight rain showers", 2),
    81: ("Moderate rain showers", 3),
    82: ("Violent rain showers", 5),
    85: ("Slight snow showers", 2),
    86: ("Heavy snow showers", 4),
    95: ("Thunderstorm", 4),
    96: ("Thunderstorm with slight hail", 5),
    99: ("Thunderstorm with heavy hail", 5),
}

_PEAK_SEASON: Final[dict[str, list[int]]] = {
    # Northern Hemisphere ports peak Aug–Oct; Southern Hemisphere Jan–Mar.
    # Chinese New Year causes a global spike; approximate: late Jan / early Feb.
    "north": [8, 9, 10],    # Aug, Sep, Oct
    "south": [1, 2, 3],     # Jan, Feb, Mar
    "cny":   [1, 2],        # Jan, Feb — global spike
}

# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def _wmo_to_label(code: int) -> tuple[str, int]:
    return _WMO_CODE_MAP.get(code, ("Unknown", 2))


def fetch_weather(latitude: float, longitude: float, target_date: str | None = None) -> WeatherContext:
    """
    Retrieve the previous day's weather from the Open-Meteo free API.

    Open-Meteo's free tier allows ~10 000 calls/day without a key — more than
    sufficient for a pipeline that calls once per port per day.

    Args:
        latitude:    WGS84 latitude of the port.
        longitude:   WGS84 longitude of the port.
        target_date: ISO date string (YYYY-MM-DD) to query.  Defaults to today.

    Returns:
        :class:`WeatherContext` with summary text and severity 1–5.
    """
    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "timezone": "UTC",
    }
    if target_date:
        # Use only the date part, strip time if present.
        date_str = target_date[:10]
        params["start_date"] = date_str
        params["end_date"] = date_str
    else:
        params["forecast_days"] = 1

    try:
        # Use archive API for dates > 2 days in the past, forecast for recent.
        from datetime import date as dt_date, timedelta
        is_historical = False
        if target_date:
            try:
                scene_dt = dt_date.fromisoformat(target_date[:10])
                is_historical = scene_dt < (dt_date.today() - timedelta(days=2))
            except ValueError:
                pass
        url = _OPEN_METEO_ARCHIVE if is_historical else _OPEN_METEO_FORECAST
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()["daily"]
    except Exception as exc:
        logger.warning("Open-Meteo API call failed: %s — returning defaults", exc)
        return WeatherContext(summary="Weather data unavailable", severity=1, code="unknown")

    code = int(data["weather_code"][0])
    label, severity = _wmo_to_label(code)
    temp_max = float(data["temperature_2m_max"][0])
    temp_min = float(data["temperature_2m_min"][0])
    precip = float(data["precipitation_sum"][0])
    wind = float(data["wind_speed_10m_max"][0])

    # Boost severity for extreme wind
    if wind >= 15.0 and severity < 3:
        severity = 3
    if wind >= 25.0 and severity < 4:
        severity = 4
    if wind >= 35.0 and severity < 5:
        severity = 5

    # Boost for heavy precipitation
    if precip >= 25.0 and severity < 4:
        severity = 4
    if precip >= 50.0 and severity < 5:
        severity = 5

    summary = f"{label} / {temp_min:.0f}–{temp_max:.0f}°C / Wind {wind:.0f} kt"
    if precip > 0:
        summary += f" / {precip:.0f} mm rain"

    return WeatherContext(summary=summary, severity=severity, code=label.lower().replace(" ", "_"))


# ---------------------------------------------------------------------------
# Labour strikes
# ---------------------------------------------------------------------------

_LABOR_DB_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "labor_events.json"


def _load_labor_db() -> list[dict[str, Any]]:
    try:
        with open(_LABOR_DB_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Cannot load labor_events.json: %s — treating as no events", exc)
        return []


def check_labor(location_name: str, as_of: date | None = None) -> LaborContext:
    """
    Check whether a labour event is active for *location_name* on *as_of*.

    The labor database is a JSON array of objects with keys: ``port``,
    ``start_date``, ``end_date``, ``status``, ``detail``.  ``port`` is matched
    case-insensitively as a substring of *location_name*.
    """
    as_of = as_of or date.today()
    db = _load_labor_db()

    for event in db:
        port: str = str(event.get("port", "")).lower()
        if port not in location_name.lower():
            continue

        try:
            start = date.fromisoformat(str(event.get("start_date", "")))
            end = date.fromisoformat(str(event.get("end_date", "")))
        except ValueError:
            continue

        detail: str = str(event.get("detail", ""))

        if start <= as_of <= end:
            status: str = str(event.get("status", "Strike active"))
            return LaborContext(status=status, detail=detail)

        # Warning window: 14 days before start
        warning_start = start.replace(year=start.year)  # type: ignore[arg-type]
        from datetime import timedelta
        warning_start = start - timedelta(days=14)
        if warning_start <= as_of < start:
            return LaborContext(
                status="Strike warning",
                detail=f"{detail} (starts {start.isoformat()})" if detail else f"Potential action from {start.isoformat()}",
            )

    return LaborContext(status="Normal", detail="")


# ---------------------------------------------------------------------------
# Peak season
# ---------------------------------------------------------------------------

def is_peak_season(latitude: float, as_of: date | None = None) -> bool:
    """
    Return True if the month + hemisphere combination falls in peak shipping
    season, or during Chinese New Year.
    """
    as_of = as_of or date.today()
    month = as_of.month
    hemisphere = "north" if latitude >= 0 else "south"

    if month in _PEAK_SEASON["cny"]:
        return True
    return month in _PEAK_SEASON[hemisphere]


# ---------------------------------------------------------------------------
# Composite fetch — one call to rule them all
# ---------------------------------------------------------------------------

def gather_external_context(
    location_name: str,
    latitude: float,
    longitude: float,
    scene_date: str | None = None,
) -> ExternalContext:
    """
    Fetch weather, labour, geopolitical, and season data for one port on one date.

    Args:
        location_name:  e.g. "Port of Jebel Ali, Dubai"
        latitude:       WGS84 latitude.
        longitude:      WGS84 longitude.
        scene_date:     ISO date of the Sentinel-2 scene (YYYY-MM-DD).

    Returns:
        :class:`ExternalContext` with all four signals populated.
    """
    weather = fetch_weather(latitude, longitude, scene_date)

    as_of = date.today()
    if scene_date:
        try:
            as_of = date.fromisoformat(scene_date[:10])
        except ValueError:
            pass

    labor = check_labor(location_name, as_of)
    peak = is_peak_season(latitude, as_of)
    geopolitical = check_geopolitical(location_name, as_of)

    logger.debug(
        "External context for %r: weather=%s (sev=%d) labor=%s peak=%s geo=%s (sev=%d)",
        location_name[:40],
        weather["code"], weather["severity"],
        labor["status"], peak,
        geopolitical["category"], geopolitical["max_severity"],
    )
    return ExternalContext(
        weather=weather,
        labor=labor,
        peak_season=peak,
        geopolitical=geopolitical,
    )


def build_external_context_string(external_data: ExternalContext) -> str:
    """
    Build a rich external context string for the Gemini prompt that includes
    weather, labour, peak season, AND geopolitical/conflict information.

    The geopolitical section is critical — it conveys real-world events that
    satellite imagery alone cannot detect (court rulings, armed conflicts,
    insurance spikes, carrier rerouting decisions).

    Returns a formatted multi-line string ready for the Gemini ASSESS prompt.
    """
    parts: list[str] = []

    # ---- Geopolitical / conflict (most important — comes first) ----
    geo_str = format_geopolitical_for_gemini(external_data["geopolitical"])
    if geo_str:
        parts.append(geo_str)

    # ---- Weather ----
    w = external_data["weather"]
    parts.append(
        f"WEATHER: {w['summary']} (severity {w['severity']}/5, code={w['code']})"
    )

    # ---- Labour ----
    l = external_data["labor"]
    if l["status"] != "Normal":
        parts.append(
            f"LABOUR: {l['status']} — {l['detail']}"
        )
    else:
        parts.append("LABOUR: Normal operations — no active strikes or disputes.")

    # ---- Peak season ----
    parts.append(
        f"PEAK SEASON: {'Yes — elevated cargo volumes expected' if external_data['peak_season'] else 'No — standard seasonal volumes'}"
    )

    return "\n".join(parts)
