from __future__ import annotations

import logging
import time
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
    "satellite-image observations plus external context (geopolitical/conflict, "
    "weather, labour, season) and must decide whether a supply-chain disruption "
    "has occurred.\n\n"
    "CRITICAL RULES — EXTERNAL CONTEXT AND IMAGERY:\n"
    "- External context should inform assessment and may elevate severity, but "
    "only for ports DIRECTLY in the conflict zone or subject to the court "
    "ruling.  For example: a port *inside* the Strait of Hormuz conflict zone "
    "(Jebel Ali, Bandar Abbas) IS disrupted regardless of imagery.  A port "
    "merely on the same continent is not.\n"
    "- If external context reports a court ruling voiding port concessions (e.g. "
    "Panama Supreme Court voided Hutchison concessions), the DIRECTLY affected "
    "ports (Balboa, Cristobal) ARE disrupted — no vessel/equipment movement "
    "means the port is effectively closed.\n"
    "- General lane-level disruptions (carrier rerouting, freight rate increases) "
    "affect many ports — assign severity based on the SPECIFIC port-level "
    "effects, not the lane-level event severity.  A port that gains transshipment "
    "traffic from rerouting is NOT disrupted.\n"
    "- If external context reports a drone/security incident damaging terminal "
    "equipment at a specific port, that port IS disrupted.\n"
    "- If external context reports war-risk insurance has tripled/quadrupled "
    "SPECIFICALLY for vessels calling at a port, this is a strong disruption "
    "signal for that port.\n"
    "- If external context reports schedule reliability below 50% on a trade "
    "lane, only ports with documented congestion/backlog from that lane qualify "
    "as disrupted.\n\n"
    "IMAGERY INTERPRETATION RULES:\n"
    "- A change in vessel count or type is NOT automatically a disruption.  More "
    "vessels at berth often means MORE throughput, not less.\n"
    "- A large vessel replaced by two smaller vessels may be normal fleet rotation, "
    "not disruption — assess based on total cargo capacity, not vessel count.\n"
    "- Empty yards that were full, or full yards that were empty, are strong signals.\n"
    "- Fewer vessels than baseline at anchorage may indicate vessels have been "
    "rerouted away (confirm with external context).\n"
    "- If the port appears to have NO vessels where it normally has many, and "
    "external context explains why, this confirms disruption.\n\n"
    "SEVERITY GUIDELINES:\n"
    "- Severity 5: armed conflict forcing port closure; court-ordered cessation of "
    "operations; major infrastructure damage (drone strike, crane collapse); "
    "catastrophic weather flooding terminal; >10 days congestion.\n"
    "- Severity 4: active war-risk zone with carrier rerouting; security incident "
    "damaging equipment; 5-10 day congestion; full port-wide labour strike with "
    "terminal shutdown or mass vessel diversions.\n"
    "- Severity 3: significant congestion (3-5 days waiting); weather warnings; "
    "fog season closures; equipment shortages; rolling labour stoppages "
    "measurably reducing berth productivity.\n"
    "- Severity 2: moderate congestion (1-3 days); seasonal weather issues; "
    "tariff/trade policy uncertainty; minor work bans, overtime restrictions, "
    "or warning strikes with minimal throughput impact.\n"
    "- Severity 1: normal operations; routine vessel rotation; labour "
    "negotiations without active industrial action; no significant change "
    "from baseline.\n\n"
    "IMPORTANT — LABOUR CONTEXT TIERS:\n"
    "Labour events carry a severity tier (1-5) in the external context.  Use it "
    "to calibrate: a severity-1 or severity-2 labour event (overtime bans, "
    "warning strikes) should NOT drive the overall score above 2 unless imagery "
    "independently shows significant congestion or yard overflow.  A severity-4 "
    "labour event (port-wide shutdown) may justify severity 4 even with ambiguous "
    "imagery.  The overall severity must be driven primarily by what the imagery "
    "shows — external context informs, imagery confirms.\n\n"
    "Do not invent a disruption to satisfy the prompt.  \"No significant change\" "
    "is a valid answer when external context is clear and imagery is normal.\n\n"
    "Return a JSON object matching the schema.  Include quantitative metrics:\n"
    "- container_yard_fill_pct: best estimate of container yard occupancy (0-100).\n"
    "- vessel_count: vessels at berth or immediately adjacent.\n"
    "- vessel_count_anchorage: vessels waiting offshore at anchorage.\n"
    "- disruption_category: one of the allowed literals. Use 'none' for normal "
    "operations; 'weather' for storms, fog, swell, flooding, or wind; 'labor' "
    "for strikes, stoppages, overtime bans, or industrial action; 'congestion' "
    "for vessel queues, berth delays, equipment constraints, or dwell-time "
    "growth; 'vessel_shift' when the primary signal is a material change in "
    "vessel mix, berth occupancy, anchorage pattern, diversions, or rerouting; "
    "'yard_overflow' when container/storage areas near capacity are the primary "
    "constraint; 'incident' for security events, infrastructure damage, legal "
    "closures, accidents, or conflict; 'other' only if none of these fit.\n\n"
    "EXPLANATION FIELD — WRITING RULES:\n"
    "- Write as a professional analyst briefing a logistics manager.  Lead with "
    "the conclusion in plain language, then provide the evidence that supports it.\n"
    "- NEVER reference your own decision rules, the prompt, or the assessment "
    "framework.  Do NOT use phrases like \"per critical rules\", \"based on "
    "guidelines\", \"the system determines\", \"external context takes precedence\", "
    "or any other language that exposes how the analysis was produced.\n"
    "- State findings directly.  Instead of \"Per critical rules, external context "
    "indicating severe disruption takes precedence over imagery,\" write "
    "\"Double-digit vessel waiting times and high yard utilization indicate "
    "severe congestion despite the terminal appearing operational from orbit.\"\n"
    "- Every sentence should be a fact or a supported judgement, never a "
    "description of the analytical process.\n"
    "- 2-4 sentences.  Specific and quantitative where possible."
)

_ASSESS_USER_TEMPLATE: str = (
    "Location: {location_context}\n\n"
    "Observations from satellite imagery:\n{observations}\n\n"
    "External context:\n{external_context}\n\n"
    "Based strictly on these observations and external context, assess whether a "
    "supply-chain disruption has occurred.  Return a structured disruption assessment "
    "with quantitative metrics.  Remember: external context about armed conflict, "
    "court rulings, port closures, or security incidents should inform assessment "
    "and may elevate severity, but only for ports DIRECTLY in the conflict zone or "
    "subject to the court ruling.  General lane-level disruptions (carrier rerouting, "
    "freight rate increases) should be assessed based on the SPECIFIC port-level "
    "effects, not the lane-level event severity."
)


class DisruptionAnalysis(BaseModel):
    """Structured Gemini output for a single site comparison — ML-ready feature vector."""

    disruption_detected: bool
    severity_score: int = Field(ge=1, le=5, description="1 = no change, 5 = severe disruption")
    confidence_grade: Literal["High", "Medium", "Low"]
    explanation: str = Field(
        description=(
            "Concise analyst-style summary, 2-4 sentences.  Lead with the conclusion "
            "in plain language, then provide supporting evidence.  Do NOT reference "
            "the analytical process, decision rules, or assessment framework — write "
            "as if briefing a logistics manager who needs to know what happened and why."
        ),
    )

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


def _call_gemini_with_retry(
    client: Client,
    generate_config: genai_types.GenerateContentConfig | None,
    contents: list[genai_types.Part],
    stage_label: str,
    max_retries: int = 5,
) -> genai_types.GenerateContentResponse:
    """
    Call Gemini with exponential backoff for 429 rate-limit errors.

    Vertex AI free tier has low quota (~5 RPM for gemini-2.5-flash).
    This retry loop backs off exponentially (1s, 2s, 4s, 8s, 16s) before
    giving up, which keeps the pipeline moving through backfill batches.
    """
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=_MODEL,
                contents=contents,  # type: ignore[arg-type]
                config=generate_config,
            )
        except Exception as exc:
            err_str = str(exc)
            if "429" not in err_str and "RESOURCE_EXHAUSTED" not in err_str:
                raise
            if attempt == max_retries - 1:
                logger.error(
                    "%s — 429 rate limit after %d retries, giving up: %s",
                    stage_label, max_retries, exc,
                )
                raise
            wait_s = 2 ** attempt
            logger.warning(
                "%s — 429 rate limit, retrying in %ds (attempt %d/%d)",
                stage_label, wait_s, attempt + 1, max_retries,
            )
            time.sleep(wait_s)
    # Unreachable — the loop always returns or raises
    raise RuntimeError("Unexpected retry exit")


def _call_gemini(
    baseline_bytes: bytes,
    current_bytes: bytes,
    location_context: str,
    external_context_str: str = "",
) -> DisruptionAnalysis:
    """
    Two-stage chain-of-thought analysis with rate-limit retry.

    Stage 1 — Observation: free-text description of each image.  No structured
    output so the model can reason openly about what it sees.  This grounds the
    analysis in observable facts and prevents "different = disruption" errors.

    Stage 2 — Assessment: structured disruption analysis based ONLY on the
    observations from Stage 1 plus external context.  Uses the DisruptionAnalysis
    JSON schema.  The external context includes geopolitical/conflict signals
    that may override ambiguous imagery findings.
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

    observe_response = _call_gemini_with_retry(
        client=client,
        generate_config=genai_types.GenerateContentConfig(
            system_instruction=_OBSERVE_SYSTEM_PROMPT,
        ),
        contents=[baseline_part, current_part, observe_text_part],
        stage_label="Stage 1 (observe)",
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

    assess_response = _call_gemini_with_retry(
        client=client,
        generate_config=genai_types.GenerateContentConfig(
            system_instruction=_ASSESS_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=DisruptionAnalysis,
        ),
        contents=[assess_text_part],
        stage_label="Stage 2 (assess)",
    )

    raw_text: str = assess_response.text or ""
    analysis = DisruptionAnalysis.model_validate_json(raw_text)
    logger.info(
        "Gemini result: disruption=%s severity=%d confidence=%s category=%s",
        analysis.disruption_detected,
        analysis.severity_score,
        analysis.confidence_grade,
        analysis.disruption_category,
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
        external_context_str: Pre-formatted weather/labour/geopolitical context string.

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
