"""Forms for the borrower portal.

Each simulation wizard step is a small ModelForm over the shared Simulation
row. Add-row income/expense lines have their own tiny forms. Boundary
validation lives here; business rules stay on the models.
"""

from decimal import Decimal
from pathlib import Path

from django import forms
from django.core.files.uploadedfile import UploadedFile

from portal.ai.extraction import SUPPORTED_EXTENSIONS
from portal.models import Application, Document, ExpenseLine, IncomeLine, Simulation

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".csv": {"text/csv", "text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
}


class PurposeForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["purpose"]
        widgets = {"purpose": forms.RadioSelect}


class BorrowersForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["borrower_count"]
        widgets = {"borrower_count": forms.RadioSelect}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["property_type", "region", "property_price", "property_usage"]

    def clean_property_price(self) -> Decimal:
        price: Decimal = self.cleaned_data["property_price"]
        if price <= 0:
            msg = "Enter a property price greater than zero."
            raise forms.ValidationError(msg)
        return price


class ContributionForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["own_funds"]
        widgets = {"own_funds": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}


class PersonalForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["date_of_birth", "dependents"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "dependents": forms.NumberInput(attrs={"min": "0", "step": "1"}),
        }


class IncomeLineForm(forms.ModelForm):
    class Meta:
        model = IncomeLine
        fields = ["income_type", "monthly_amount"]
        widgets = {"monthly_amount": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}


class ExpenseLineForm(forms.ModelForm):
    class Meta:
        model = ExpenseLine
        fields = ["expense_type", "monthly_amount"]
        widgets = {"monthly_amount": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["kind", "file"]

    def clean_file(self) -> UploadedFile:
        upload: UploadedFile = self.cleaned_data["file"]
        if upload.size and upload.size > MAX_UPLOAD_BYTES:
            msg = f"File is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
            raise forms.ValidationError(msg)

        suffix = Path(upload.name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            msg = f"Unsupported file type. Allowed: {allowed}."
            raise forms.ValidationError(msg)

        if upload.content_type and upload.content_type not in _ALLOWED_CONTENT_TYPES[suffix]:
            msg = "File content type does not match its extension."
            raise forms.ValidationError(msg)
        return upload


class ApplicationDetailsForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = [
            "first_name",
            "last_name",
            "national_number",
            "current_address",
            "employment_status",
            "employer_name",
        ]
