"""Validation on the document upload form: type, size and parseability."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from portal.forms import MAX_UPLOAD_BYTES, DocumentUploadForm


def _form(upload):
    return DocumentUploadForm(data={"kind": "payslip"}, files={"file": upload})


class TestDocumentUploadValidation:
    def test_accepts_supported_pdf(self):
        upload = SimpleUploadedFile("payslip.pdf", b"%PDF-1.4 hello", content_type="application/pdf")
        assert _form(upload).is_valid()

    def test_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile("malware.exe", b"MZbinary", content_type="application/octet-stream")
        form = _form(upload)
        assert not form.is_valid()
        assert "file" in form.errors

    def test_rejects_extension_content_type_mismatch(self):
        upload = SimpleUploadedFile("payslip.pdf", b"<html>", content_type="text/html")
        form = _form(upload)
        assert not form.is_valid()
        assert "file" in form.errors

    def test_rejects_oversized_file(self):
        upload = SimpleUploadedFile("big.pdf", b"x" * (MAX_UPLOAD_BYTES + 1), content_type="application/pdf")
        form = _form(upload)
        assert not form.is_valid()
        assert "file" in form.errors

    @pytest.mark.parametrize("name", ["scan.png", "notes.txt"])
    def test_accepts_other_supported_types(self, name):
        ext = name.rsplit(".", 1)[1]
        content_type = "image/png" if ext == "png" else "text/plain"
        upload = SimpleUploadedFile(name, b"data", content_type=content_type)
        assert _form(upload).is_valid()
