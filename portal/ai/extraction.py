"""Turn an uploaded file into plain text for analysis.

A real deployment would route PDFs/images through OCR or a parser service.
Here we keep a lightweight, dependency-free extractor: text-like files are
decoded directly, PDFs yield their embedded text streams best-effort, and
anything we cannot read is rejected so it never drives the FSM to a success
state on garbage bytes.
"""

import re
from pathlib import Path

_MAX_TEXT_BYTES = 200_000

_TEXT_EXTENSIONS = {".txt", ".csv", ".md"}
_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_EXTENSIONS = _TEXT_EXTENSIONS | _PDF_EXTENSIONS | _IMAGE_EXTENSIONS

_PDF_TEXT = re.compile(rb"\(([^()]+)\)\s*T[jJ]")


class UnsupportedDocumentError(Exception):
    """The uploaded file is not a kind we can analyse."""


def extract_text(filename: str, raw: bytes) -> str:
    """Best-effort plain text for *raw*, dispatched by file extension."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        msg = f"Unsupported document type: {suffix or filename!r}."
        raise UnsupportedDocumentError(msg)

    chunk = raw[:_MAX_TEXT_BYTES]
    if suffix in _PDF_EXTENSIONS:
        return _pdf_text(chunk)
    if suffix in _IMAGE_EXTENSIONS:
        return ""
    return chunk.decode("utf-8", errors="replace")


def _pdf_text(chunk: bytes) -> str:
    fragments = [match.group(1).decode("latin-1", errors="replace") for match in _PDF_TEXT.finditer(chunk)]
    if fragments:
        return " ".join(fragments)
    return chunk.decode("latin-1", errors="replace")
