"""Document analysis: classify, extract fields, flag mismatches.

Two interchangeable paths behind one ``analyze_document`` function:

* **Stub** (default) — deterministic, clearly labelled, no network. Used
  whenever ``ANTHROPIC_API_KEY`` is unset, so the deployed demo is free and
  reproducible.
* **Live** — the Anthropic Messages API with *prompt caching*: the large,
  static system prompt (classification taxonomy + extraction schema) carries
  a ``cache_control`` breakpoint so repeated analyses reuse it cheaply.

Both return the same :class:`AnalysisResult`, so callers and tests never care
which path ran.
"""

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings

from portal import enums

# Static, cacheable system prompt. Kept verbatim so the live path can mark it
# with a prompt-cache breakpoint — the whole point of caching is that this
# text never changes between calls.
SYSTEM_PROMPT = """You are a mortgage back-office assistant. You receive the
text of a single supporting document uploaded for a mortgage application.

Classify the document into exactly one of these kinds:
- id_card, payslip, epc_certificate, sales_agreement, bank_statement, other

Then extract any of these fields you can find, as a JSON object:
- full_name, national_number, gross_monthly_income, property_address,
  property_price, epc_score, document_date

Return ONLY a JSON object with this shape:
{
  "detected_kind": "<one of the kinds>",
  "summary": "<one sentence>",
  "extracted_fields": { ... },
  "confidence": <0.0-1.0>
}
Do not include any prose outside the JSON object.
"""

# Field name -> the applicant attribute it should agree with.
_FIELD_TO_APPLICATION_ATTR = {
    "national_number": "national_number",
    "full_name": "_full_name",
}


@dataclass
class AnalysisResult:
    """Normalised analysis output, identical across the stub and live paths."""

    detected_kind: str
    summary: str
    extracted_fields: dict[str, Any]
    mismatches: list[str] = field(default_factory=list)
    is_stub: bool = True
    model_used: str = ""


@dataclass
class ApplicationFacts:
    """The application data an analysis is checked against."""

    full_name: str
    national_number: str
    property_price: Decimal | None = None


def detect_mismatches(extracted: dict[str, Any], facts: ApplicationFacts) -> list[str]:
    """Compare extracted fields against the application, returning mismatches.

    Pure and path-independent, so it is exercised by both the stub and the
    live result and is trivially unit-tested.
    """
    mismatches: list[str] = []
    expected = {
        "national_number": facts.national_number,
        "full_name": facts.full_name,
    }
    for key, application_value in expected.items():
        found = extracted.get(key)
        if found and application_value and str(found).strip().lower() != str(application_value).strip().lower():
            mismatches.append(f"Document {key} '{found}' does not match application '{application_value}'.")
    return mismatches


def _stub_result(filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Deterministic offline analysis derived from the filename.

    Clearly labelled as a stub. It echoes the application's own data so a
    document never spuriously flags as a mismatch in the demo.
    """
    lowered = filename.lower()
    detected = enums.DocumentKind.OTHER.value
    for kind in enums.DocumentKind:
        token = kind.value.split("_")[0]
        if token in lowered:
            detected = kind.value
            break
    extracted = {"full_name": facts.full_name, "national_number": facts.national_number}
    return AnalysisResult(
        detected_kind=detected,
        summary=f"[STUB] Offline analysis of '{filename}'. Set ANTHROPIC_API_KEY for live analysis.",
        extracted_fields=extracted,
        mismatches=detect_mismatches(extracted, facts),
        is_stub=True,
        model_used="stub",
    )


def _live_result(text: str, filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Analyse via the Anthropic Messages API with prompt caching."""
    import anthropic  # noqa: PLC0415 — optional dependency, only needed on the live path

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[
            {
                "role": "user",
                "content": f"Filename: {filename}\n\nDocument text:\n{text}",
            },
        ],
    )
    payload = _parse_payload(response.content[0].text)
    extracted = payload.get("extracted_fields", {})
    return AnalysisResult(
        detected_kind=payload.get("detected_kind", enums.DocumentKind.OTHER.value),
        summary=payload.get("summary", ""),
        extracted_fields=extracted,
        mismatches=detect_mismatches(extracted, facts),
        is_stub=False,
        model_used=settings.ANTHROPIC_MODEL,
    )


def _parse_payload(text: str) -> dict[str, Any]:
    """Parse the model's text block as a JSON object, tolerating junk."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def analyze_document(text: str, filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Analyse a document, using the live path only when a key is configured."""
    if settings.AI_ANALYSIS_ENABLED:
        return _live_result(text, filename, facts)
    return _stub_result(filename, facts)
