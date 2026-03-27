from django.contrib import admin

from .models import AuditLog, ChatHistory, EligibilityAssessment, EscalationRequest, Scheme


admin.site.site_header = "JanSetu Admin"
admin.site.site_title = "JanSetu Admin"
admin.site.index_title = "Operations and Scheme Management"


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user_message",
        "language",
        "source",
        "matched_scheme_count",
        "needs_human_review",
        "created_at",
    )
    list_filter = ("language", "source", "needs_human_review", "created_at")
    search_fields = ("user_message", "bot_response")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(Scheme)
class SchemeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "verification_status",
        "state_coverage",
        "last_verified_on",
        "expiry_date",
        "effort_level",
    )
    list_filter = ("category", "verification_status", "gender", "effort_level")
    search_fields = (
        "name",
        "description",
        "eligibility",
        "official_source_name",
        "state_coverage",
        "district_coverage",
        "beneficiary_tags",
    )
    ordering = ("category", "name")

    fieldsets = (
        ("Basic Information", {"fields": ("name", "category", "description", "eligibility")}),
        ("Eligibility Criteria", {"fields": ("min_age", "max_age", "income_limit", "gender", "beneficiary_tags")}),
        ("Verification and Coverage", {"fields": ("official_source_name", "url", "verification_status", "last_verified_on", "verification_notes", "state_coverage", "district_coverage", "expiry_date")}),
        ("Next Steps", {"fields": ("required_documents", "where_to_apply", "offline_location", "helpline", "effort_level")}),
    )


@admin.register(EligibilityAssessment)
class EligibilityAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "state",
        "support_need",
        "document_readiness",
        "recommendation_count",
        "needs_human_review",
        "created_at",
    )
    list_filter = ("support_need", "document_readiness", "needs_human_review", "created_at")
    search_fields = ("state", "district", "notes")
    readonly_fields = ("created_at", "recommended_scheme_names")


@admin.register(EscalationRequest)
class EscalationRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "support_type", "state", "status", "assigned_to", "due_at", "created_at")
    list_filter = ("support_type", "status", "preferred_language", "state", "created_at")
    search_fields = ("name", "phone_number", "email", "message", "state", "district")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "status_updated_at")
    fieldsets = (
        ("Request", {"fields": ("name", "phone_number", "email", "preferred_language", "support_type", "state", "district", "message")}),
        ("Workflow", {"fields": ("status", "assigned_to", "due_at", "resolution_notes", "status_updated_at", "created_at")}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("event_type", "method", "path", "status_code", "actor", "created_at")
    list_filter = ("event_type", "method", "status_code", "created_at")
    search_fields = ("path", "actor")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
