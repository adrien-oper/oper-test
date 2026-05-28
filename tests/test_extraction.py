"""Text extraction: type gating and per-format decoding."""

import pytest

from portal.ai.extraction import UnsupportedDocumentError, extract_text


class TestExtractText:
    def test_text_file_is_decoded(self):
        assert extract_text("notes.txt", b"hello world") == "hello world"

    def test_pdf_with_text_operators_is_extracted(self):
        raw = b"BT (Ada Lovelace) Tj (92052812928) Tj ET"
        assert extract_text("payslip.pdf", raw) == "Ada Lovelace 92052812928"

    def test_pdf_without_operators_falls_back_to_raw_decode(self):
        assert "plain text" in extract_text("doc.pdf", b"just plain text, no operators")

    def test_image_yields_no_text(self):
        assert not extract_text("scan.png", b"\x89PNG\r\n binary")

    @pytest.mark.parametrize("name", ["malware.exe", "archive.zip", "noextension"])
    def test_unsupported_type_raises(self, name):
        with pytest.raises(UnsupportedDocumentError):
            extract_text(name, b"data")
