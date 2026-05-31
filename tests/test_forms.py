"""Validation on the document upload form: type, size and parseability."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from portal.forms import (
    MAX_UPLOAD_BYTES,
    ContributionForm,
    DocumentUploadForm,
    ExpenseLineForm,
    IncomeLineForm,
    PersonalForm,
    ProjectForm,
)


class TestProjectFormValidation:
    def _data(self, price):
        return {"property_type": "house", "region": "flanders", "property_price": price, "property_usage": "own_home"}

    def test_accepts_positive_price(self):
        assert ProjectForm(data=self._data("300000")).is_valid()

    @pytest.mark.parametrize("price", ["0", "-100"])
    def test_rejects_non_positive_price(self, price):
        form = ProjectForm(data=self._data(price))
        assert not form.is_valid()
        assert "property_price" in form.errors


class TestNonNegativeAmounts:
    """Money and count fields reject negative input, mirroring the price guard.

    Only ``property_price`` had a non-positive guard; own funds, income,
    expense and dependants accepted negatives, which then flowed into the
    affordability maths and the application recap.
    """

    def test_contribution_rejects_negative_own_funds(self):
        form = ContributionForm(data={"own_funds": "-5000"})
        assert not form.is_valid()
        assert "own_funds" in form.errors

    def test_contribution_accepts_zero_and_positive(self):
        assert ContributionForm(data={"own_funds": "0"}).is_valid()
        assert ContributionForm(data={"own_funds": "60000"}).is_valid()

    def test_income_rejects_negative_amount(self):
        form = IncomeLineForm(data={"income_type": "salary", "monthly_amount": "-3000"})
        assert not form.is_valid()
        assert "monthly_amount" in form.errors

    def test_expense_rejects_negative_amount(self):
        form = ExpenseLineForm(data={"expense_type": "other", "monthly_amount": "-3000"})
        assert not form.is_valid()
        assert "monthly_amount" in form.errors

    def test_personal_rejects_negative_dependents(self):
        form = PersonalForm(data={"dependents": "-2", "date_of_birth": ""})
        assert not form.is_valid()
        assert "dependents" in form.errors

    def test_personal_accepts_zero_dependents(self):
        assert PersonalForm(data={"dependents": "0", "date_of_birth": ""}).is_valid()


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

    @pytest.mark.parametrize("content_type", ["", None])
    def test_rejects_absent_content_type(self, content_type):
        """An absent or empty content-type must not bypass the MIME check."""
        upload = SimpleUploadedFile("payslip.pdf", b"%PDF-1.4 hello", content_type=content_type)
        form = _form(upload)
        assert not form.is_valid()
        assert "file" in form.errors
