"""
Geopolitical and conflict context for the supply-chain disruption pipeline.

Queries ``backend/data/geopolitical_events.json`` — a structured database of
active and recent events that affect port operations: armed conflicts, security
incidents, legal/regulatory rulings, route disruptions, and trade policy changes.

This module is designed for automated CI/CD — just edit the JSON to add or
update events; no code changes needed.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final, TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GeopoliticalEvent(TypedDict):
    """Shape of one entry in geopolitical_events.json."""

    id: str
    region: str
    category: str  # armed_conflict, security_incident, legal_regulatory, congestion, weather, trade_policy, route_disruption
    title: str
    description: str
    severity: int  # 1–5, mirrors the briefing severity scale
    affected_ports: list[str]
    start_date: str
    end_date: str
    status: str  # active, recovering, monitoring
    impacts: list[str]
    schedule_reliability_pct: float | None  # optional
    avg_transit_delay_days: float | None  # optional


class GeopoliticalContext(TypedDict):
    """Aggregated geopolitical signals for a single port on a single date."""

    active_events: list[str]  # titles of events active on this date
    max_severity: int  # 1 = no events, 5 = active armed conflict
    category: str  # dominant category
    summary: str  # 1-2 sentence summary for the Gemini prompt
    impacts: list[str]  # combined impact descriptions


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GEO_DB_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "data" / "geopolitical_events.json"
)

# Map of location-name substrings (lowercased) to the "affected_ports" names
# used in geopolitical_events.json.  This allows the module to match
# "Port of Jebel Ali, Dubai" → "Jebel Ali" without requiring exact equality.
# Add new ports here as the watchlist grows.
_PORT_ALIASES: Final[dict[str, str]] = {
    "jebel ali": "Jebel Ali",
    "dubai": "Dubai",
    "salalah": "Salalah",
    "jeddah": "Jeddah",
    "balboa": "Balboa",
    "cristobal": "Cristobal",
    "panama": "Panama",
    "casablanca": "Casablanca",
    "mombasa": "Mombasa",
    "tema": "Tema",
    "beira": "Beira",
    "cape town": "Cape Town",
    "hamburg": "Hamburg",
    "bremerhaven": "Bremerhaven",
    "wilhelmshaven": "Wilhelmshaven",
    "rotterdam": "Rotterdam",
    "lisbon": "Lisbon",
    "piraeus": "Piraeus",
    "genoa": "Genoa",
    "la spezia": "La Spezia",
    "gioia tauro": "Gioia Tauro",
    "ningbo": "Ningbo",
    "jakarta": "Jakarta",
    "tanjung priok": "Jakarta",
    "surabaya": "Surabaya",
    "san antonio": "San Antonio",
    "valparaiso": "Valparaíso",
    "valparaíso": "Valparaíso",
    "tauranga": "Tauranga",
    "lyttelton": "Lyttelton",
    "los angeles": "Los Angeles",
    "long beach": "Long Beach",
    "port of la": "Los Angeles",
    "seagirt": "Baltimore",
    "baltimore": "Baltimore",
    "singapore": "Singapore",
    "antwerp": "Antwerp",
    "felixstowe": "Felixstowe",
    "new york": "New York",
    "savannah": "Savannah",
    "norfolk": "Norfolk",
    "charleston": "Charleston",
    "colombo": "Colombo",
    "port klang": "Port Klang",
    "tanjung pelepas": "Tanjung Pelepas",
}


# ---------------------------------------------------------------------------
# Database loader
# ---------------------------------------------------------------------------


def _load_geo_db() -> list[GeopoliticalEvent]:
    """Load the geopolitical events database from JSON."""
    try:
        raw = json.loads(_GEO_DB_PATH.read_text(encoding="utf-8"))
        return raw  # type: ignore[return-value]
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Cannot load geopolitical_events.json: %s — treating as no events", exc)
        return []


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _port_matches(location_name: str, event_port: str) -> bool:
    """
    Check if *location_name* corresponds to *event_port*.

    Uses substring matching on the lowercased location name against both the
    event port name and the alias map.
    """
    name_lower = location_name.lower()

    # Direct match against event port
    if event_port.lower() in name_lower:
        return True

    # Check aliases
    for alias_key, canonical in _PORT_ALIASES.items():
        if canonical == event_port and alias_key in name_lower:
            return True

    return False


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def check_geopolitical(
    location_name: str,
    as_of: date | None = None,
    db: list[GeopoliticalEvent] | None = None,
) -> GeopoliticalContext:
    """
    Return all geopolitical events active for *location_name* on *as_of*.

    Args:
        location_name: e.g. "Port of Jebel Ali, Dubai"
        as_of: Date to check; defaults to today.
        db: Pre-loaded events list (for testing); loaded from JSON if None.

    Returns:
        :class:`GeopoliticalContext` with active events, max severity, and summary.
    """
    as_of = as_of or date.today()
    if db is None:
        db = _load_geo_db()

    active: list[GeopoliticalEvent] = []

    for event in db:
        # Check date range
        try:
            start = date.fromisoformat(event["start_date"])
            end = date.fromisoformat(event["end_date"])
        except ValueError:
            continue

        if not (start <= as_of <= end):
            continue

        # Check port match
        if not any(_port_matches(location_name, p) for p in event["affected_ports"]):
            continue

        active.append(event)

    if not active:
        return GeopoliticalContext(
            active_events=[],
            max_severity=1,
            category="none",
            summary="No active geopolitical events affecting this port.",
            impacts=[],
        )

    # Aggregate
    max_sev = max(e["severity"] for e in active)
    categories = sorted({e["category"] for e in active})
    titles = [e["title"] for e in active]
    all_impacts: list[str] = []
    for e in active:
        all_impacts.extend(e["impacts"])

    # Build summary — most severe event first
    active.sort(key=lambda e: e["severity"], reverse=True)
    top = active[0]
    summary_parts = [f"{top['title']} (severity {top['severity']}/5): {top['description']}"]
    for e in active[1:]:
        summary_parts.append(f"Additionally: {e['title']} — {e['description'][:120]}…" if len(e['description']) > 120 else f"Additionally: {e['title']} — {e['description']}")

    return GeopoliticalContext(
        active_events=titles,
        max_severity=max_sev,
        category="+".join(categories),
        summary=" ".join(summary_parts),
        impacts=all_impacts,
    )


def format_geopolitical_for_gemini(geo: GeopoliticalContext) -> str:
    """
    Format geopolitical context as a string suitable for the Gemini
    external_context_str parameter.

    Returns empty string if there are no active events.
    """
    if geo["max_severity"] <= 1:
        return ""

    lines = ["GEOPOLITICAL / CONFLICT CONTEXT:"]
    lines.append(f"  Region status: {geo['category']} (max severity {geo['max_severity']}/5)")
    for title in geo["active_events"]:
        lines.append(f"  Active event: {title}")
    if geo["impacts"]:
        lines.append("  Known operational impacts:")
        for imp in geo["impacts"][:8]:  # Cap at 8 to keep prompt size reasonable
            lines.append(f"    - {imp}")

    return "\n".join(lines)
