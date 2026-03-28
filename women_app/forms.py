from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model

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
        self.fields["email"].widget.attrs.update({"placeholder": "Email (optional)"})
        self.fields["password1"].widget.attrs.update({"placeholder": "Create password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Confirm password"})

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
