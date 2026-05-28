"""Sign-up and onboarding forms."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from portal.models import HelpOffice

User = get_user_model()


class SignupForm(forms.Form):
    """Email + password with consent checkboxes.

    The email doubles as the username. Password strength is delegated to
    Django's configured validators.
    """

    email = forms.EmailField(label="E-mail")
    password = forms.CharField(label="Password", widget=forms.PasswordInput, min_length=10)
    accept_terms = forms.BooleanField(label="I accept the terms and conditions")
    accept_privacy = forms.BooleanField(label="I accept the privacy policy")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            msg = "An account with this e-mail already exists."
            raise forms.ValidationError(msg)
        return email

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self) -> User:
        email = self.cleaned_data["email"]
        return User.objects.create_user(username=email, email=email, password=self.cleaned_data["password"])


class PhoneVerificationForm(forms.Form):
    """Stubbed phone verification — any 6-digit code is accepted."""

    phone_number = forms.CharField(label="Mobile number", max_length=20)
    code = forms.CharField(label="Verification code", min_length=6, max_length=6, required=False)

    def clean_code(self) -> str:
        code = self.cleaned_data.get("code", "")
        if code and not code.isdigit():
            msg = "The code must be 6 digits."
            raise forms.ValidationError(msg)
        return code


class HelpOfficeForm(forms.Form):
    """Pick a help office to finish onboarding."""

    office = forms.ModelChoiceField(queryset=HelpOffice.objects.all(), label="Help office")
