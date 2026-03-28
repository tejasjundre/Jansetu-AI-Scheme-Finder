from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatHistory(models.Model):
    SOURCE_CHOICES = [
        ("chat", "Chat"),
        ("wizard", "Eligibility Wizard"),
    ]

    user_message = models.TextField()
    bot_response = models.TextField()
    language = models.CharField(max_length=10, default="en")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="chat")
    matched_scheme_count = models.PositiveIntegerField(default=0)
    recommended_scheme_names = models.JSONField(default=list, blank=True)
    needs_human_review = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Chat Log"
        verbose_name_plural = "Chat Logs"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["source", "needs_human_review", "-created_at"]),
            models.Index(fields=["language", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user_message[:40]}..."


class Scheme(models.Model):
    CATEGORY_CHOICES = [
        ("education", "Education"),
        ("agriculture", "Agriculture"),
        ("financial", "Financial Support"),
        ("health", "Health"),
        ("employment", "Jobs and Skills"),
        ("empowerment", "Empowerment"),
        ("other", "Other"),
    ]

    GENDER_CHOICES = [
        ("any", "Any"),
        ("female", "Female"),
        ("male", "Male"),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ("verified", "Verified"),
        ("review_required", "Review Required"),
        ("stale", "Stale"),
        ("broken", "Broken Link"),
    ]

    EFFORT_LEVEL_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    eligibility = models.TextField()
    min_age = models.IntegerField(default=0)
    max_age = models.IntegerField(default=100)
    income_limit = models.IntegerField(default=9999999)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="any")

    official_source_name = models.CharField(max_length=200, blank=True)
    url = models.URLField(blank=True)
    verification_status = models.CharField(
        max_length=30,
        choices=VERIFICATION_STATUS_CHOICES,
        default="review_required",
    )
    last_verified_on = models.DateField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    state_coverage = models.TextField(default="All India")
    district_coverage = models.TextField(blank=True)
    beneficiary_tags = models.CharField(max_length=255, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    required_documents = models.TextField(blank=True)
    where_to_apply = models.TextField(blank=True)
    offline_location = models.CharField(max_length=255, blank=True)
    helpline = models.CharField(max_length=120, blank=True)
    effort_level = models.CharField(
        max_length=20,
        choices=EFFORT_LEVEL_CHOICES,
        default="medium",
    )

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "Government Scheme"
        verbose_name_plural = "Government Schemes"
        indexes = [
            models.Index(fields=["category", "name"]),
            models.Index(fields=["verification_status", "last_verified_on"]),
            models.Index(fields=["gender", "category"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    @property
    def needs_freshness_review(self):
        if not self.last_verified_on:
            return True
        return self.last_verified_on < timezone.localdate() - timedelta(days=90)


class EligibilityAssessment(models.Model):
    INCOME_BAND_CHOICES = [
        ("under_1l", "Under Rs 1 lakh"),
        ("under_2l", "Under Rs 2 lakh"),
        ("under_5l", "Under Rs 5 lakh"),
        ("under_8l", "Under Rs 8 lakh"),
        ("above_8l", "Above Rs 8 lakh"),
    ]

    GENDER_CHOICES = [
        ("female", "Female"),
        ("male", "Male"),
        ("any", "Prefer not to say"),
    ]

    RESIDENCE_CHOICES = [
        ("rural", "Rural"),
        ("urban", "Urban"),
        ("semi_urban", "Semi Urban"),
    ]

    CASTE_CHOICES = [
        ("general", "General"),
        ("sc", "SC"),
        ("st", "ST"),
        ("obc", "OBC"),
        ("ews", "EWS"),
        ("minority", "Minority"),
        ("other", "Other"),
    ]

    DOCUMENT_CHOICES = [
        ("ready", "All documents ready"),
        ("partial", "Some documents ready"),
        ("not_ready", "Need document help"),
    ]

    language = models.CharField(max_length=10, default="en")
    age = models.PositiveIntegerField()
    annual_income = models.PositiveIntegerField(null=True, blank=True)
    income_band = models.CharField(max_length=30, choices=INCOME_BAND_CHOICES)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="any")
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    residence_type = models.CharField(max_length=20, choices=RESIDENCE_CHOICES)
    support_need = models.CharField(max_length=50)
    is_student = models.BooleanField(default=False)
    is_mother = models.BooleanField(default=False)
    is_entrepreneur = models.BooleanField(default=False)
    has_disability = models.BooleanField(default=False)
    caste_category = models.CharField(max_length=20, choices=CASTE_CHOICES, default="general")
    document_readiness = models.CharField(max_length=20, choices=DOCUMENT_CHOICES)
    notes = models.TextField(blank=True)
    recommendation_count = models.PositiveIntegerField(default=0)
    recommended_scheme_names = models.JSONField(default=list, blank=True)
    needs_human_review = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Eligibility Assessment"
        verbose_name_plural = "Eligibility Assessments"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["state", "support_need"]),
            models.Index(fields=["needs_human_review", "-created_at"]),
        ]

    def __str__(self):
        return f"Assessment {self.pk} - {self.state}"


class EscalationRequest(models.Model):
    SUPPORT_TYPE_CHOICES = [
        ("ngo_worker", "NGO Worker"),
        ("shg_volunteer", "SHG Volunteer"),
        ("callback", "Support Callback"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]

    name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    preferred_language = models.CharField(max_length=10, default="en")
    support_type = models.CharField(max_length=30, choices=SUPPORT_TYPE_CHOICES)
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    message = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_escalations",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    status_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Escalation Request"
        verbose_name_plural = "Escalation Requests"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["state", "status"]),
            models.Index(fields=["status", "due_at"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_support_type_display()}"

    @property
    def is_overdue(self):
        if self.status == "resolved" or not self.due_at:
            return False
        return self.due_at < timezone.now()


class AuditLog(models.Model):
    event_type = models.CharField(max_length=100)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField(default=200)
    actor = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["path", "method", "-created_at"]),
            models.Index(fields=["status_code", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.method} {self.path}"


class CitizenProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="citizen_profile",
    )
    language = models.CharField(max_length=10, default="en")
    age = models.PositiveIntegerField(null=True, blank=True)
    annual_income = models.PositiveIntegerField(null=True, blank=True)
    income_band = models.CharField(
        max_length=30,
        choices=EligibilityAssessment.INCOME_BAND_CHOICES,
        default="under_5l",
    )
    gender = models.CharField(
        max_length=10,
        choices=EligibilityAssessment.GENDER_CHOICES,
        default="any",
    )
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    residence_type = models.CharField(
        max_length=20,
        choices=EligibilityAssessment.RESIDENCE_CHOICES,
        default="urban",
    )
    support_need = models.CharField(max_length=50, default="other")
    is_student = models.BooleanField(default=False)
    is_mother = models.BooleanField(default=False)
    is_entrepreneur = models.BooleanField(default=False)
    has_disability = models.BooleanField(default=False)
    caste_category = models.CharField(
        max_length=20,
        choices=EligibilityAssessment.CASTE_CHOICES,
        default="general",
    )
    document_readiness = models.CharField(
        max_length=20,
        choices=EligibilityAssessment.DOCUMENT_CHOICES,
        default="partial",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Citizen Profile"
        verbose_name_plural = "Citizen Profiles"

    def __str__(self):
        return f"{self.user.username} profile"

    def to_recommendation_input(self):
        return {
            "age": self.age,
            "annual_income": self.annual_income,
            "income_band": self.income_band,
            "gender": self.gender,
            "state": self.state,
            "district": self.district,
            "residence_type": self.residence_type,
            "support_need": self.support_need,
            "is_student": self.is_student,
            "is_mother": self.is_mother,
            "is_entrepreneur": self.is_entrepreneur,
            "has_disability": self.has_disability,
            "caste_category": self.caste_category,
            "document_readiness": self.document_readiness,
            "notes": self.notes,
        }
