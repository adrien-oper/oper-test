"""Document analysis: classify, extract fields, flag mismatches.

Two interchangeable paths behind one ``analyze_document`` function:

* **Stub** (default) — deterministic, clearly labelled, no network. Used
  whenever ``ANTHROPIC_API_KEY`` is unset, so the deployed demo is free and
  reproducible. Its output is always valid by construction.
* **Live** — the Anthropic Messages API. The large, static system prompt
  carries a ``cache_control`` breakpoint so the API may reuse it across calls
  once it crosses the model's cache minimum.

Both return the same :class:`AnalysisResult` on success. Output the model
cannot produce validly (unparseable JSON, missing or unknown ``detected_kind``)
raises :class:`InvalidAnalysisError` so the caller can fail the document
rather than silently record a bogus "other" classification.
"""

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings

from portal import enums

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

_VALID_KINDS = {kind.value for kind in enums.DocumentKind}
_PRICE_NON_NUMERIC = re.compile(r"[^\d.]")


class InvalidAnalysisError(Exception):
    """The analyzer produced output that cannot be trusted as a result."""


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


def _normalise_price(value: object) -> Decimal | None:
    cleaned = _PRICE_NON_NUMERIC.sub("", str(value))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


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

    found_price = _normalise_price(extracted["property_price"]) if extracted.get("property_price") else None
    if found_price is not None and facts.property_price is not None and found_price != facts.property_price:
        mismatches.append(
            f"Document property_price '{found_price}' does not match application '{facts.property_price}'."
        )
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
    """Analyse via the Anthropic Messages API."""
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
        detected_kind=payload["detected_kind"],
        summary=payload.get("summary", ""),
        extracted_fields=extracted if isinstance(extracted, dict) else {},
        mismatches=detect_mismatches(extracted if isinstance(extracted, dict) else {}, facts),
        is_stub=False,
        model_used=settings.ANTHROPIC_MODEL,
    )


def _parse_payload(text: str) -> dict[str, Any]:
    """Parse the model's text block as a valid analysis object or fail loudly."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        msg = "Analyzer response was not valid JSON."
        raise InvalidAnalysisError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "Analyzer response was not a JSON object."
        raise InvalidAnalysisError(msg)
    if parsed.get("detected_kind") not in _VALID_KINDS:
        msg = f"Analyzer returned an unknown document kind: {parsed.get('detected_kind')!r}."
        raise InvalidAnalysisError(msg)
    return parsed


def analyze_document(text: str, filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Analyse a document, using the live path only when a key is configured."""
    if settings.AI_ANALYSIS_ENABLED:
        return _live_result(text, filename, facts)
    return _stub_result(filename, facts)
