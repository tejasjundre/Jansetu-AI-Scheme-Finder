import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .localization import get_content_list, get_field_choices, get_field_labels, get_ui_strings
from .location_data import canonical_state_name, get_district_choices, get_state_choices
from .models import CitizenProfile, EligibilityAssessment, EscalationRequest


INDIA_STATES = get_state_choices()

FOCUS_PRESETS = {
    "farmer": {
        "support_need": "agriculture",
        "focus_tags": ["farmer", "agriculture", "rural"],
    },
    "student": {
        "support_need": "education",
        "focus_tags": ["student", "scholarship", "education"],
        "is_student": True,
    },
    "older": {
        "support_need": "financial",
        "focus_tags": ["senior citizen", "pension", "older person"],
    },
    "job_seeker": {
        "support_need": "employment",
        "focus_tags": ["job seeker", "jobs", "livelihood", "skills"],
    },
    "stipend": {
        "support_need": "education",
        "focus_tags": ["stipend", "training", "education"],
    },
    "housing": {
        "support_need": "financial",
        "focus_tags": ["housing", "home", "shelter"],
    },
    "food": {
        "support_need": "other",
        "focus_tags": ["food", "ration", "nutrition"],
    },
    "businessman": {
        "support_need": "employment",
        "focus_tags": ["business", "entrepreneur", "self-employment", "loan"],
        "is_entrepreneur": True,
    },
}


class LocalizedDistrictFormMixin:
    district_required = False

    def _selected_state(self):
        raw_value = (
            self.data.get(self.add_prefix("state"))
            or self.initial.get("state")
            or getattr(self.instance, "state", "")
        )
        return canonical_state_name(raw_value)

    def _localize_common_fields(self, lang: str):
        ui = get_ui_strings(lang)
        labels = get_field_labels(lang)

        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label

        self.fields["state"].choices = [("", ui["select_state"]), *INDIA_STATES]
        self.fields["district"].choices = get_district_choices(self._selected_state(), ui["select_district"])
        self.fields["district"].required = self.district_required
        self.fields["state"].widget.attrs.update({"data-state-select": "true"})
        self.fields["district"].widget.attrs.update({"data-district-select": "true"})
        return ui


class EligibilityWizardForm(LocalizedDistrictFormMixin, forms.ModelForm):
    need_focus = forms.ChoiceField(required=False, choices=())
    state = forms.ChoiceField(choices=())
    district = forms.ChoiceField(required=False, choices=())
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = EligibilityAssessment
        fields = [
            "language",
            "age",
            "annual_income",
            "income_band",
            "gender",
            "state",
            "district",
            "residence_type",
            "support_need",
            "is_student",
            "is_mother",
            "is_entrepreneur",
            "has_disability",
            "caste_category",
            "document_readiness",
            "notes",
        ]
        widgets = {
            "language": forms.HiddenInput(),
        }

    def __init__(self, *args, lang: str = "en", **kwargs):
        super().__init__(*args, **kwargs)
        ui = self._localize_common_fields(lang)
        self.ui = ui
        focus_options = get_content_list("need_focus_options", lang)
        self.fields["need_focus"].choices = [(item["value"], item["label"]) for item in focus_options]
        self.fields["need_focus"].label = ui["select_need_focus"]
        self.fields["support_need"].choices = get_field_choices("support_need", lang)
        self.fields["support_need"].widget = forms.HiddenInput()
        self.fields["support_need"].required = False
        self.fields["income_band"].choices = get_field_choices("income_band", lang)
        self.fields["gender"].choices = get_field_choices("gender", lang)
        self.fields["residence_type"].choices = get_field_choices("residence_type", lang)
        self.fields["caste_category"].choices = get_field_choices("caste_category", lang)
        self.fields["document_readiness"].choices = get_field_choices("document_readiness", lang)
        self.fields["gender"].initial = self.initial.get("gender") or "any"
        self.fields["need_focus"].initial = self.initial.get("need_focus") or ""

    def clean_age(self):
        age = self.cleaned_data["age"]
        if age < 0 or age > 110:
            raise forms.ValidationError("Enter an age between 0 and 110.")
        return age

    def clean(self):
        cleaned_data = super().clean()
        focus_value = cleaned_data.get("need_focus") or self.initial.get("need_focus") or ""
        support_need = cleaned_data.get("support_need") or ""
        preset = FOCUS_PRESETS.get(focus_value, {})

        if not focus_value and not support_need:
            self.add_error("need_focus", self.ui["select_need_focus"])
            return cleaned_data

        if preset and not support_need:
            cleaned_data["support_need"] = preset["support_need"]

        for flag_name in ("is_student", "is_mother", "is_entrepreneur", "has_disability"):
            if preset.get(flag_name):
                cleaned_data[flag_name] = True

        focus_tags = []
        for tag in preset.get("focus_tags", []):
            if tag not in focus_tags:
                focus_tags.append(tag)
        cleaned_data["focus_tags"] = focus_tags
        return cleaned_data


class EscalationRequestForm(LocalizedDistrictFormMixin, forms.ModelForm):
    state = forms.ChoiceField(choices=())
    district = forms.ChoiceField(required=False, choices=())

    class Meta:
        model = EscalationRequest
        fields = [
            "name",
            "phone_number",
            "email",
            "preferred_language",
            "support_type",
            "state",
            "district",
            "message",
        ]
        widgets = {
            "preferred_language": forms.HiddenInput(),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, lang: str = "en", **kwargs):
        super().__init__(*args, **kwargs)
        self._localize_common_fields(lang)
        self.fields["support_type"].choices = get_field_choices("support_type", lang)
        self.fields["name"].widget.attrs.update(
            {
                "placeholder": "Enter your full name",
                "autocomplete": "name",
            }
        )
        self.fields["phone_number"].widget.attrs.update(
            {
                "placeholder": "10-digit mobile number",
                "inputmode": "numeric",
                "autocomplete": "tel",
                "pattern": "(?:\\+91[\\s-]?)?[6-9][0-9]{9}",
                "maxlength": "16",
                "title": "Enter a valid Indian mobile number (example: 9876543210).",
            }
        )
        self.fields["email"].required = False
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Email address (optional)",
                "autocomplete": "email",
                "inputmode": "email",
            }
        )
        self.fields["message"].widget.attrs.update(
            {
                "placeholder": "Briefly describe the help you need...",
            }
        )

    def clean_phone_number(self):
        raw_value = (self.cleaned_data.get("phone_number") or "").strip()
        digits = re.sub(r"\D", "", raw_value)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) != 10 or digits[0] not in "6789":
            raise forms.ValidationError(
                "Enter a valid 10-digit Indian mobile number (example: 9876543210)."
            )
        return digits

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip().lower()
        if not value:
            return ""
        try:
            validate_email(value)
        except ValidationError as exc:
            raise forms.ValidationError(
                "Enter a valid email address (example: name@example.com)."
            ) from exc
        return value


class EscalationOpsUpdateForm(forms.ModelForm):
    due_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    class Meta:
        model = EscalationRequest
        fields = ["status", "assigned_to", "due_at", "resolution_notes"]
        widgets = {
            "resolution_notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Resolution notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        self.fields["assigned_to"].queryset = user_model.objects.filter(is_staff=True, is_active=True).order_by("username")
        self.fields["assigned_to"].required = False
        self.fields["resolution_notes"].required = False


class CitizenRegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"placeholder": "Choose username"})
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Email (optional)",
                "autocomplete": "email",
                "inputmode": "email",
            }
        )
        self.fields["password1"].widget.attrs.update({"placeholder": "Create password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Confirm password"})

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip().lower()
        if not value:
            return ""

        try:
            validate_email(value)
        except ValidationError as exc:
            raise forms.ValidationError(
                "Enter a valid email address (example: name@example.com)."
            ) from exc

        user_model = get_user_model()
        duplicate_qs = user_model.objects.filter(email__iexact=value)
        if self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
        if duplicate_qs.exists():
            raise forms.ValidationError(
                "An account with this email already exists. Please login or use another email."
            )
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip()
        if commit:
            user.save()
        return user


class CitizenLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))


class CitizenProfileForm(LocalizedDistrictFormMixin, forms.ModelForm):
    state = forms.ChoiceField(choices=())
    district = forms.ChoiceField(required=False, choices=())

    class Meta:
        model = CitizenProfile
        fields = [
            "language",
            "age",
            "annual_income",
            "income_band",
            "gender",
            "state",
            "district",
            "residence_type",
            "support_need",
            "is_student",
            "is_mother",
            "is_entrepreneur",
            "has_disability",
            "caste_category",
            "document_readiness",
            "notes",
        ]
        widgets = {
            "language": forms.HiddenInput(),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, lang: str = "en", **kwargs):
        super().__init__(*args, **kwargs)
        self._localize_common_fields(lang)
        self.fields["support_need"].choices = get_field_choices("support_need", lang)
        self.fields["income_band"].choices = get_field_choices("income_band", lang)
        self.fields["gender"].choices = get_field_choices("gender", lang)
        self.fields["residence_type"].choices = get_field_choices("residence_type", lang)
        self.fields["caste_category"].choices = get_field_choices("caste_category", lang)
        self.fields["document_readiness"].choices = get_field_choices("document_readiness", lang)


class ApplicationSubmissionForm(forms.Form):
    scheme_name = forms.CharField(max_length=220)
    aadhaar_number = forms.CharField(max_length=12, min_length=4)
    bank_account = forms.CharField(max_length=24)
    annual_income = forms.IntegerField(min_value=0)
    caste_category = forms.ChoiceField(choices=EligibilityAssessment.CASTE_CHOICES)
    education_level = forms.ChoiceField(
        choices=[
            ("school", "School"),
            ("diploma", "Diploma"),
            ("graduate", "Graduate"),
            ("postgraduate", "Postgraduate"),
            ("other", "Other"),
        ]
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheme_name"].label = "Scheme name"
        self.fields["scheme_name"].widget.attrs.update({"placeholder": "Type or select a scheme"})
        self.fields["aadhaar_number"].label = "Aadhaar number (last 4-12 digits)"
        self.fields["aadhaar_number"].widget.attrs.update({"placeholder": "Example: 1234"})
        self.fields["bank_account"].label = "Bank account number"
        self.fields["bank_account"].widget.attrs.update({"placeholder": "Enter beneficiary account number"})
        self.fields["annual_income"].label = "Annual income (INR)"
        self.fields["annual_income"].widget.attrs.update({"placeholder": "Example: 250000"})
        self.fields["caste_category"].label = "Caste category"
        self.fields["education_level"].label = "Education level"
        self.fields["notes"].label = "Additional notes (optional)"
        self.fields["notes"].widget.attrs.update({"placeholder": "Any special context for verification..."})

    def clean_aadhaar_number(self):
        value = str(self.cleaned_data["aadhaar_number"]).strip()
        if len(value) < 4:
            raise forms.ValidationError("Enter at least last 4 digits for Aadhaar verification.")
        if not value.isdigit():
            raise forms.ValidationError("Aadhaar value should contain digits only.")
        return value
