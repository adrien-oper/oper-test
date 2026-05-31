"""Document analysis: classify, extract fields, flag mismatches.

Three interchangeable backends behind one ``analyze_document`` function:

* **stub** (default with no key) — deterministic, clearly labelled, no
  network. Used whenever no key is configured, so the deployed demo is free
  and reproducible. Its output is always valid by construction.
* **sdk** — the Anthropic Messages API. The large, static system prompt
  carries a ``cache_control`` breakpoint so the API may reuse it across calls
  once it crosses the model's cache minimum. The production live path.
* **cli** — DEV-ONLY: shells out to the ``claude`` CLI in print mode, reusing
  the developer's Claude Code login. Opt in via ``DOCUMENT_ANALYZER_BACKEND``;
  it is never the default and fails loudly if the binary is missing.

All three return the same :class:`AnalysisResult` on success. Output a backend
cannot produce validly (unparseable JSON, missing or unknown ``detected_kind``)
raises :class:`InvalidAnalysisError` so the caller can fail the document
rather than silently record a bogus "other" classification.
"""

import json
import re
import shutil
import subprocess  # noqa: S404 — dev-only CLI backend; argv is a list, binary resolved via shutil.which
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

MAX_TOKENS = 1024

STUB = "stub"
SDK = "sdk"
CLI = "cli"

_VALID_KINDS = {kind.value for kind in enums.DocumentKind}
# Assumes period as decimal separator; European "1.234,56" format is not handled.
_PRICE_NON_NUMERIC = re.compile(r"[^\d.]")


class InvalidAnalysisError(Exception):
    """The analyzer produced output that cannot be trusted as a result."""


class AnalyzerBackendError(Exception):
    """A configured analyzer backend could not be invoked."""


@dataclass
class AnalysisResult:
    """Normalised analysis output, identical across all backends."""

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

    Pure and path-independent, so it is exercised by every backend and is
    trivially unit-tested.
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


def _user_prompt(text: str, filename: str) -> str:
    return f"Filename: {filename}\n\nDocument text:\n{text}"


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
        summary=f"[STUB] Offline analysis of '{filename}'. Configure a live backend for real analysis.",
        extracted_fields=extracted,
        mismatches=detect_mismatches(extracted, facts),
        is_stub=True,
        model_used=STUB,
    )


def _sdk_result(text: str, filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Analyse via the Anthropic Messages API."""
    import anthropic  # noqa: PLC0415 — optional dependency, only needed on the live path

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
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
                    "content": _user_prompt(text, filename),
                },
            ],
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError) as exc:
        # A bad/missing key, a key without access, or an unknown model are
        # permanent: every retry fails identically. Surface them as a config
        # error so the caller fails the document instead of wedging it in
        # ``analyzing`` while the backend retries forever.
        msg = f"The Anthropic API rejected the request as unrecoverable: {type(exc).__name__}."
        raise AnalyzerBackendError(msg) from exc
    return _result_from_payload(_parse_payload(response.content[0].text), facts, model_used=settings.ANTHROPIC_MODEL)


def _cli_result(text: str, filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Analyse by shelling out to the ``claude`` CLI in print mode (dev only)."""
    binary = shutil.which(settings.CLAUDE_CLI_PATH)
    if binary is None:
        msg = f"The 'cli' analyzer backend needs the {settings.CLAUDE_CLI_PATH!r} binary on PATH."
        raise AnalyzerBackendError(msg)

    # Feed the prompt on stdin, never as an argv element: it carries the
    # document text (possibly PII) which argv would expose in process listings.
    prompt = f"{SYSTEM_PROMPT}\n\n{_user_prompt(text, filename)}"
    try:
        completed = subprocess.run(  # noqa: S603 — argv is flags only, binary resolved via shutil.which
            [binary, "-p", "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = f"The 'claude' CLI exited with status {exc.returncode}."
        raise AnalyzerBackendError(msg) from exc

    return _result_from_payload(_parse_payload(_cli_text(completed.stdout)), facts, model_used="claude-cli")


def _cli_text(stdout: str) -> str:
    """Pull the assistant's text out of ``claude -p --output-format json``."""
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        msg = "The 'claude' CLI did not return valid JSON."
        raise InvalidAnalysisError(msg) from exc
    if isinstance(envelope, dict) and "result" in envelope:
        return str(envelope["result"])
    return stdout


def _result_from_payload(payload: dict[str, Any], facts: ApplicationFacts, *, model_used: str) -> AnalysisResult:
    extracted = payload.get("extracted_fields", {})
    extracted = extracted if isinstance(extracted, dict) else {}
    return AnalysisResult(
        detected_kind=payload["detected_kind"],
        summary=payload.get("summary", ""),
        extracted_fields=extracted,
        mismatches=detect_mismatches(extracted, facts),
        is_stub=False,
        model_used=model_used,
    )


def _parse_payload(text: str) -> dict[str, Any]:
    """Parse a backend's text block as a valid analysis object or fail loudly."""
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


def resolve_backend() -> str:
    """Pick the analyzer backend, never defaulting to the dev-only ``cli``.

    An explicit ``DOCUMENT_ANALYZER_BACKEND`` wins; otherwise fall back to
    ``sdk`` when a key is present and ``stub`` when it is not.
    """
    configured = (settings.DOCUMENT_ANALYZER_BACKEND or "").strip().lower()
    if configured:
        if configured not in {STUB, SDK, CLI}:
            msg = f"Unknown DOCUMENT_ANALYZER_BACKEND: {configured!r}."
            raise AnalyzerBackendError(msg)
        return configured
    return SDK if settings.ANTHROPIC_API_KEY else STUB


def analyze_document(text: str, filename: str, facts: ApplicationFacts) -> AnalysisResult:
    """Analyse a document through the resolved backend."""
    backend = resolve_backend()
    if backend == SDK:
        return _sdk_result(text, filename, facts)
    if backend == CLI:
        return _cli_result(text, filename, facts)
    return _stub_result(filename, facts)
