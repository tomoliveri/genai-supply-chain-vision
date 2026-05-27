from __future__ import annotations

import logging
from typing import Literal

import google.cloud.storage as gcs
from google.genai import Client
from google.genai import types as genai_types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_PROJECT_ID: str = "traveltime-465606"
_LOCATION: str = "australia-southeast1"
_MODEL: str = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Two-stage chain-of-thought prompts
# ---------------------------------------------------------------------------

_OBSERVE_SYSTEM_PROMPT: str = (
    "You are a geospatial imagery analyst.  You will be shown two satellite images "
    "of a logistics site (port, warehouse district, or rail yard).\n\n"
    "Your ONLY task is to describe what you see — do NOT assess disruption, do NOT "
    "compare, do NOT draw conclusions.  List observable facts.\n\n"
    "For each image separately, enumerate:\n"
    "1. Vessels — count, approximate size (large cargo / medium / small / barge), "
    "position (at berth, at anchor, in channel), any clusters.\n"
    "2. Quay / berth activity — cranes visible?  Any equipment on the dock?\n"
    "3. Container / storage yard — approximate fill level (empty / partly full / "
    "dense), any notable patterns.\n"
    "4. Water — any slicks, sediment plumes, unusual discolouration.\n"
    "5. Landside — vehicle queues, road congestion, construction.\n\n"
    "Be specific and quantitative when possible.  If you cannot determine something "
    "with confidence, say so rather than guessing.\n\n"
    "The images are Sentinel-2 true-colour composites at 10 m/px, cropped to "
    "2 km × 2 km.  They may appear dark or low-contrast — this is normal for "
    "surface-reflectance satellite imagery."
)

_OBSERVE_USER_TEMPLATE: str = (
    "Location: {location_context}\n\n"
    "Image 1 (baseline / historical): first attached image.\n"
    "Image 2 (current acquisition): second attached image.\n\n"
    "Describe each image using the enumeration above."
)

_ASSESS_SYSTEM_PROMPT: str = (
    "You are a geospatial supply-chain analyst.  You will be given a set of "
    "satellite-image observations plus external context (weather, labour, season) "
    "and must decide whether a supply-chain disruption has occurred.\n\n"
    "CRITICAL RULES:\n"
    "- A change in vessel count or type is NOT automatically a disruption.  More "
    "vessels at berth often means MORE throughput, not less.\n"
    "- A large vessel replaced by two smaller vessels may be normal fleet rotation, "
    "not disruption — assess based on total cargo capacity, not vessel count.\n"
    "- Empty yards that were full, or full yards that were empty, are strong signals.\n"
    "- Severe weather (gale, storm, flood) IS a disruption — category 'weather'.\n"
    "- Active labour strikes ARE a disruption — category 'labor'.\n"
    "- Severity 5 is reserved for disasters: flood, fire, major spill, berth collapse.\n"
    "- If the only change is different vessels at the same berths, that is normal "
    "operations (severity 1, no disruption).\n"
    "- Do not invent a disruption to satisfy the prompt.  \"No significant change\" "
    "is a valid and common answer.\n\n"
    "Return a JSON object matching the schema.  Include quantitative metrics:\n"
    "- container_yard_fill_pct: best estimate of container yard occupancy (0-100).\n"
    "- vessel_count: vessels at berth or immediately adjacent.\n"
    "- vessel_count_anchorage: vessels waiting offshore at anchorage.\n"
    "- disruption_category: one of the allowed literals."
)

_ASSESS_USER_TEMPLATE: str = (
    "Location: {location_context}\n\n"
    "Observations from satellite imagery:\n{observations}\n\n"
    "External context:\n{external_context}\n\n"
    "Based strictly on these observations and external context, assess whether a "
    "supply-chain disruption has occurred.  Return a structured disruption assessment "
    "with quantitative metrics."
)


class DisruptionAnalysis(BaseModel):
    """Structured Gemini output for a single site comparison — ML-ready feature vector."""

    disruption_detected: bool
    severity_score: int = Field(ge=1, le=5, description="1 = no change, 5 = severe disruption")
    confidence_grade: Literal["High", "Medium", "Low"]
    explanation: str = Field(description="Concise analyst-style summary, 2-4 sentences.")

    # Quantitative metrics extracted during analysis — these are the ML features.
    container_yard_fill_pct: int = Field(
        ge=0, le=100,
        description="Estimated percentage of container yard occupied (0 = empty, 100 = full)",
    )
    vessel_count: int = Field(
        ge=0,
        description="Number of vessels at berth or immediately adjacent to the terminal",
    )
    vessel_count_anchorage: int = Field(
        ge=0,
        description="Number of vessels waiting at anchorage offshore (congestion signal)",
    )
    disruption_category: Literal[
        "none", "weather", "labor", "congestion", "vessel_shift",
        "yard_overflow", "incident", "other",
    ] = Field(description="Primary category of disruption, or 'none' if no disruption")


def _fetch_gcs_bytes(gcs_uri: str) -> bytes:
    """Download a GCS object and return its raw bytes."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Expected a gs:// URI, got: {gcs_uri!r}")

    path = gcs_uri[len("gs://"):]
    bucket_name, _, blob_name = path.partition("/")

    client = gcs.Client()
    blob = client.bucket(bucket_name).blob(blob_name)
    data: bytes = blob.download_as_bytes()
    logger.debug("Fetched %d bytes from %s", len(data), gcs_uri)
    return data


def _call_gemini(
    baseline_bytes: bytes,
    current_bytes: bytes,
    location_context: str,
    external_context_str: str = "",
) -> DisruptionAnalysis:
    """
    Two-stage chain-of-thought analysis.

    Stage 1 — Observation: free-text description of each image.  No structured
    output so the model can reason openly about what it sees.  This grounds the
    analysis in observable facts and prevents "different = disruption" errors.

    Stage 2 — Assessment: structured disruption analysis based ONLY on the
    observations from Stage 1.  Uses the DisruptionAnalysis JSON schema.
    """
    client = Client(vertexai=True, project=_PROJECT_ID, location=_LOCATION)

    baseline_part = genai_types.Part.from_bytes(data=baseline_bytes, mime_type="image/jpeg")
    current_part = genai_types.Part.from_bytes(data=current_bytes, mime_type="image/jpeg")

    # ---- Stage 1: Observe --------------------------------------------------
    observe_prompt = _OBSERVE_USER_TEMPLATE.format(location_context=location_context)
    observe_text_part = genai_types.Part.from_text(text=observe_prompt)

    logger.info(
        "Stage 1 (observe) — %s for %r",
        _MODEL, location_context[:60],
    )

    observe_response = client.models.generate_content(
        model=_MODEL,
        contents=[baseline_part, current_part, observe_text_part],  # type: ignore[list-item]
        config=genai_types.GenerateContentConfig(
            system_instruction=_OBSERVE_SYSTEM_PROMPT,
        ),
    )
    observations: str = observe_response.text or ""
    logger.debug("Observations (%d chars): %s", len(observations), observations[:200])

    # ---- Stage 2: Assess ---------------------------------------------------
    assess_prompt = _ASSESS_USER_TEMPLATE.format(
        location_context=location_context,
        observations=observations,
        external_context=external_context_str or "No external context available.",
    )
    assess_text_part = genai_types.Part.from_text(text=assess_prompt)

    logger.info("Stage 2 (assess) — %s for %r", _MODEL, location_context[:60])

    assess_response = client.models.generate_content(
        model=_MODEL,
        contents=[assess_text_part],
        config=genai_types.GenerateContentConfig(
            system_instruction=_ASSESS_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=DisruptionAnalysis,
        ),
    )

    raw_text: str = assess_response.text or ""
    analysis = DisruptionAnalysis.model_validate_json(raw_text)
    logger.info(
        "Gemini result: disruption=%s severity=%d confidence=%s",
        analysis.disruption_detected,
        analysis.severity_score,
        analysis.confidence_grade,
    )
    return analysis


def analyse_disruption(
    current_image_path: str,
    baseline_image_path: str,
    location_context: str,
    external_context_str: str = "",
) -> DisruptionAnalysis:
    """
    End-to-end pipeline: fetch both GCS images → Gemini analysis.

    Does NOT write to Firestore — callers are responsible for persistence.
    This function is the primary entry point for the daily pipeline.

    Args:
        current_image_path:  gs:// URI of the most recent imagery JPEG.
        baseline_image_path: gs:// URI of the historical baseline JPEG.
        location_context:    Free-text description of the site (name, function, etc.).
        external_context_str: Pre-formatted weather/labour/season context string.

    Returns:
        :class:`DisruptionAnalysis` with the Gemini-structured assessment.
    """
    current_bytes = _fetch_gcs_bytes(current_image_path)
    baseline_bytes = _fetch_gcs_bytes(baseline_image_path)
    return _call_gemini(baseline_bytes, current_bytes, location_context, external_context_str)


def analyse_disruption_from_bytes(
    current_bytes: bytes,
    baseline_bytes: bytes,
    location_context: str,
    external_context_str: str = "",
) -> DisruptionAnalysis:
    """
    Identical pipeline without GCS fetching — for testing or pre-fetched payloads.

    Does NOT write to Firestore; callers handle persistence if required.
    """
    return _call_gemini(baseline_bytes, current_bytes, location_context, external_context_str)
