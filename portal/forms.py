"""Forms for the borrower portal.

Each simulation wizard step is a small ModelForm over the shared Simulation
row. Add-row income/expense lines have their own tiny forms. Boundary
validation lives here; business rules stay on the models.
"""

from django import forms

from portal.models import Application, Document, ExpenseLine, IncomeLine, Simulation


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


class ContributionForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["own_funds"]


class PersonalForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["date_of_birth", "dependents"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}


class IncomeLineForm(forms.ModelForm):
    class Meta:
        model = IncomeLine
        fields = ["income_type", "monthly_amount"]


class ExpenseLineForm(forms.ModelForm):
    class Meta:
        model = ExpenseLine
        fields = ["expense_type", "monthly_amount"]


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["kind", "file"]


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
