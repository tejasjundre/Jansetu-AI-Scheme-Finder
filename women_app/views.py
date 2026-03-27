import json
import logging
from collections import Counter
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.db.utils import DatabaseError, OperationalError
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .ai_logic import ai_chat_response, recommendation_names_from_response
from .eligibility import (
    available_categories,
    create_assessment_from_form,
    filter_schemes,
    get_all_schemes,
    recommend_schemes_from_profile,
)
from .forms import EscalationRequestForm, EligibilityWizardForm, INDIA_STATES, EscalationOpsUpdateForm
from .help_centers import find_help_centers, get_best_help_center
from .localization import SUPPORTED_LANGUAGES, get_content_list, get_ui_strings
from .location_data import get_state_district_map
from .models import AuditLog, ChatHistory, EligibilityAssessment, EscalationRequest, Scheme
from .myscheme_api import fetch_scheme_detail
from .news_feed import get_launch_news
from .voice_utils import synthesize_speech_mp3, transcribe_audio_upload

logger = logging.getLogger(__name__)
User = get_user_model()

def get_current_language(request):
    candidate = request.GET.get("lang") or request.POST.get("language") or request.session.get("preferred_lang")
    if candidate not in SUPPORTED_LANGUAGES:
        candidate = "en"
    request.session["preferred_lang"] = candidate
    return candidate


def build_context(request, extra=None):
    lang = get_current_language(request)
    context = {
        "current_lang": lang,
        "languages": SUPPORTED_LANGUAGES,
        "t": get_ui_strings(lang),
        "district_map": get_state_district_map(),
    }
    if extra:
        context.update(extra)
    return context


def _serialize_chat_scheme(scheme):
    return {
        "name": scheme["name"],
        "category_label": scheme["category_label"],
        "slug": scheme.get("slug", ""),
        "url": scheme["url"],
        "where_to_apply": scheme["next_steps"]["where_to_apply"] if scheme.get("next_steps") else "",
        "helpline": scheme["next_steps"]["helpline"] if scheme.get("next_steps") else "",
    }


def healthz(request):
    db_ok = True
    cache_ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (DatabaseError, OperationalError):
        db_ok = False

    cache_key = "healthz:probe"
    try:
        cache.set(cache_key, "ok", timeout=15)
        cache_ok = cache.get(cache_key) == "ok"
    except Exception:
        cache_ok = False

    status_ok = db_ok and cache_ok
    status_code = 200 if status_ok else 503
    return JsonResponse(
        {
            "status": "ok" if status_ok else "degraded",
            "services": {
                "database": "ok" if db_ok else "error",
                "cache": "ok" if cache_ok else "error",
            },
        },
        status=status_code,
    )


@ensure_csrf_cookie
def home(request):
    lang = get_current_language(request)
    schemes = get_all_schemes()
    featured_schemes = []
    featured_tags = ["women", "student", "mother", "entrepreneur", "senior citizen", "disability"]
    for tag in featured_tags:
        match = next((scheme for scheme in schemes if tag in scheme["beneficiary_tags"]), None)
        if match and match not in featured_schemes:
            featured_schemes.append(match)
        if len(featured_schemes) >= 4:
            break
    covered_states = sorted(
        {
            state
            for scheme in schemes
            for state in scheme["state_coverage"]
            if state.lower() not in {"all india", "india", "national", "all"}
        }
    )
    today = timezone.localdate()
    newly_launched = [
        item
        for item in schemes
        if item.get("last_verified_on")
        and item["verification_status"] == "verified"
        and (today - item["last_verified_on"]).days <= 14
    ]
    newly_launched.sort(
        key=lambda row: (
            row.get("last_verified_on") is None,
            -(row.get("last_verified_on") or today).toordinal(),
        )
    )
    closing_soon = [
        item
        for item in schemes
        if item.get("expiry_date")
        and not item.get("is_expired")
        and 0 <= (item["expiry_date"] - today).days <= 45
    ]
    closing_soon.sort(key=lambda row: (row.get("expiry_date") or today))

    return render(
        request,
        "home.html",
        build_context(
            request,
            {
                "scheme_count": len(schemes),
                "category_count": len(available_categories()),
                "state_count": len(covered_states) or 1,
                "stale_scheme_count": sum(1 for scheme in schemes if scheme["needs_freshness_review"]),
                "home_needs": get_content_list("home_needs", lang),
                "home_steps": get_content_list("home_steps", lang),
                "home_comfort_points": get_content_list("home_comfort_points", lang),
                "need_focus_options": get_content_list("need_focus_options", lang),
                "separate_features": get_content_list("separate_features", lang),
                "launch_news": get_launch_news(limit=7),
                "featured_schemes": featured_schemes,
                "newly_launched_schemes": newly_launched[:6],
                "closing_soon_schemes": closing_soon[:6],
            },
        ),
    )


@ensure_csrf_cookie
def wizard(request):
    lang = get_current_language(request)
    initial_wizard_step = 1
    initial = {
        "language": lang,
        "support_need": request.GET.get("need", ""),
        "need_focus": request.GET.get("focus", ""),
        "state": request.GET.get("state", ""),
    }
    form = EligibilityWizardForm(request.POST or None, initial=initial, lang=lang)
    recommendations = []
    assessment = None
    selected_state = request.POST.get("state") or initial.get("state") or ""
    selected_district = request.POST.get("district") or ""

    if request.method == "POST" and form.is_valid():
        assessment = create_assessment_from_form(form)
        recommendations = recommend_schemes_from_profile(form.cleaned_data)
        initial_wizard_step = 3

        ChatHistory.objects.create(
            user_message=f"Wizard request from {assessment.state} for {assessment.support_need}",
            bot_response=f"Recommended {len(recommendations)} schemes",
            language=lang,
            source="wizard",
            matched_scheme_count=len(recommendations),
            recommended_scheme_names=assessment.recommended_scheme_names,
            needs_human_review=assessment.needs_human_review,
        )
    elif request.method == "POST" and form.errors:
        step_fields = {
            1: {"age", "state", "district", "need_focus", "support_need", "income_band"},
            2: {"gender", "residence_type", "is_student", "is_mother", "is_entrepreneur", "has_disability"},
            3: {"annual_income", "caste_category", "document_readiness", "notes"},
        }
        errored_fields = set(form.errors.keys())
        for step_number, fields in step_fields.items():
            if errored_fields.intersection(fields):
                initial_wizard_step = step_number
                break

    return render(
        request,
        "wizard.html",
        build_context(
            request,
            {
                "wizard_form": form,
                "recommendations": recommendations,
                "assessment": assessment,
                "initial_wizard_step": initial_wizard_step,
                "wizard_tips": get_content_list("wizard_tips", lang),
                "need_focus_options": get_content_list("need_focus_options", lang),
                "help_center": get_best_help_center(selected_state, selected_district),
            },
        ),
    )


@ensure_csrf_cookie
def chat(request):
    return render(
        request,
        "chatbot.html",
        build_context(
            request,
            {
                "chat_prompts": get_content_list("chat_prompts", get_current_language(request)),
                "chat_best_for": get_content_list("chat_best_for", get_current_language(request)),
            },
        ),
    )


def schemes(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip() or None
    state = request.GET.get("state", "").strip() or None
    sort = request.GET.get("sort", "recommended").strip() or "recommended"
    scheme_records = filter_schemes(query=query, category=category, state=state, sort=sort)
    paginator = Paginator(scheme_records, 24)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "schemes.html",
        build_context(
            request,
            {
                "schemes": page_obj.object_list,
                "categories": available_categories(),
                "page_obj": page_obj,
                "selected_query": query,
                "selected_category": category or "",
                "selected_state": state or "",
                "selected_sort": sort,
                "state_options": [state for state, _ in INDIA_STATES if state != "All India"],
                "scheme_total": paginator.count,
            },
        ),
    )


def scheme_detail(request, slug):
    lang = get_current_language(request)
    selected_state = request.GET.get("state", "").strip()
    selected_district = request.GET.get("district", "").strip()
    local_scheme = (
        Scheme.objects.filter(url__iendswith=f"/schemes/{slug}")
        .values(
            "name",
            "category",
            "description",
            "eligibility",
            "official_source_name",
            "url",
            "state_coverage",
            "district_coverage",
            "required_documents",
            "where_to_apply",
            "offline_location",
            "helpline",
            "effort_level",
            "verification_status",
            "last_verified_on",
        )
        .first()
    )
    detail_lang = lang if lang in {"en", "hi", "mr"} else "en"
    detail = fetch_scheme_detail(slug, lang=detail_lang)
    if not local_scheme and not detail:
        return render(request, "privacy.html", build_context(request), status=404)

    summary = local_scheme or {}
    scheme_name = (detail or {}).get("name") or summary.get("name") or slug.replace("-", " ").title()
    context = {
        "scheme": {
            "name": scheme_name,
            "description": (detail or {}).get("brief_description") or summary.get("description", ""),
            "eligibility": summary.get("eligibility", ""),
            "official_source_name": (detail or {}).get("nodal_ministry") or summary.get("official_source_name", "myScheme"),
            "url": (detail or {}).get("detail_url") or summary.get("url", ""),
            "state_coverage": summary.get("state_coverage", ""),
            "district_coverage": summary.get("district_coverage", ""),
            "where_to_apply": summary.get("where_to_apply", ""),
            "required_documents": summary.get("required_documents", ""),
            "effort_level": summary.get("effort_level", "medium"),
            "verification_status": summary.get("verification_status", "verified"),
            "last_verified_on": summary.get("last_verified_on"),
        },
        "detail": detail,
        "help_center": get_best_help_center(selected_state, selected_district),
        "selected_state": selected_state,
        "selected_district": selected_district,
        "state_options": [item for item, _ in INDIA_STATES if item != "All India"],
    }
    return render(request, "scheme_detail.html", build_context(request, context))


@ensure_csrf_cookie
def support(request):
    lang = get_current_language(request)
    form = EscalationRequestForm(request.POST or None, initial={"preferred_language": lang}, lang=lang)
    submitted = False
    selected_state = request.POST.get("state", "")
    selected_district = request.POST.get("district", "")

    if request.method == "POST" and form.is_valid():
        form.save()
        submitted = True
        form = EscalationRequestForm(initial={"preferred_language": lang}, lang=lang)

    return render(
        request,
        "support.html",
        build_context(
            request,
            {
                "support_form": form,
                "submitted": submitted,
                "support_reasons": get_content_list("support_reasons", lang),
                "help_center": get_best_help_center(selected_state, selected_district),
            },
        ),
    )


def privacy(request):
    lang = get_current_language(request)
    return render(
        request,
        "privacy.html",
        build_context(
            request,
            {
                "privacy_store_items": get_content_list("privacy_store_items", lang),
                "privacy_use_items": get_content_list("privacy_use_items", lang),
            },
        ),
    )


@staff_member_required(login_url="/admin/login/")
def ops_dashboard(request):
    schemes = get_all_schemes()
    unanswered_queries = ChatHistory.objects.filter(needs_human_review=True).count()
    pending_escalations = EscalationRequest.objects.exclude(status="resolved").count()
    stale_schemes = [scheme for scheme in schemes if scheme["needs_freshness_review"]]
    broken_links = [scheme for scheme in schemes if scheme["has_broken_link_alert"]]

    recommendation_counter = Counter()
    for names in ChatHistory.objects.values_list("recommended_scheme_names", flat=True):
        for name in names or []:
            recommendation_counter[name] += 1
    for names in EligibilityAssessment.objects.values_list("recommended_scheme_names", flat=True):
        for name in names or []:
            recommendation_counter[name] += 1

    most_requested = recommendation_counter.most_common(5)

    if request.method == "POST":
        escalation_id = request.POST.get("escalation_id", "").strip()
        escalation = EscalationRequest.objects.filter(pk=escalation_id).first()
        if escalation:
            ops_form = EscalationOpsUpdateForm(request.POST, instance=escalation)
            if ops_form.is_valid():
                update = ops_form.save(commit=False)
                update.status_updated_at = timezone.now()
                if update.status == "in_progress" and not update.assigned_to_id:
                    update.assigned_to = request.user
                if update.status == "resolved" and not update.resolution_notes:
                    update.resolution_notes = "Resolved from ops dashboard."
                update.save()

    recent_escalations = EscalationRequest.objects.select_related("assigned_to").all()[:10]
    overdue_escalations = EscalationRequest.objects.filter(
        status__in=["new", "in_progress"],
        due_at__isnull=False,
        due_at__lt=timezone.now(),
    ).count()
    unassigned_escalations = EscalationRequest.objects.filter(
        status__in=["new", "in_progress"],
        assigned_to__isnull=True,
    ).count()

    overview_rows = [
        {"label": "Queries needing review", "value": unanswered_queries, "tone": "amber"},
        {"label": "Pending escalations", "value": pending_escalations, "tone": "indigo"},
        {"label": "Overdue escalations", "value": overdue_escalations, "tone": "red"},
        {"label": "Unassigned escalations", "value": unassigned_escalations, "tone": "amber"},
        {"label": "Stale schemes", "value": len(stale_schemes), "tone": "indigo"},
        {"label": "Broken links", "value": len(broken_links), "tone": "red"},
    ]
    overview_max = max([item["value"] for item in overview_rows] or [1]) or 1
    for item in overview_rows:
        item["width"] = max(8, round((item["value"] / overview_max) * 100)) if item["value"] else 0

    demand_rows = [
        {"label": name, "value": count}
        for name, count in most_requested
    ]
    demand_max = max([item["value"] for item in demand_rows] or [1]) or 1
    for item in demand_rows:
        item["width"] = max(10, round((item["value"] / demand_max) * 100)) if item["value"] else 0

    context = {
        "unanswered_queries": unanswered_queries,
        "pending_escalations": pending_escalations,
        "overdue_escalations": overdue_escalations,
        "unassigned_escalations": unassigned_escalations,
        "stale_scheme_count": len(stale_schemes),
        "broken_link_count": len(broken_links),
        "most_requested": most_requested,
        "stale_schemes": stale_schemes[:6],
        "broken_links": broken_links[:6],
        "recent_escalations": recent_escalations,
        "recent_queries": ChatHistory.objects.all()[:8],
        "recent_audit_logs": AuditLog.objects.all()[:10],
        "ops_assignable_users": User.objects.filter(is_staff=True, is_active=True).order_by("username"),
        "default_due_at": (timezone.now() + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M"),
        "ops_overview_rows": overview_rows,
        "demand_rows": demand_rows,
    }
    return render(request, "ops_dashboard.html", build_context(request, context))


@require_GET
def help_center_api(request):
    state = request.GET.get("state", "").strip()
    district = request.GET.get("district", "").strip()
    centers = find_help_centers(state=state, district=district, limit=3)
    return JsonResponse({"state": state, "district": district, "centers": centers})


@require_POST
def speech_to_text_api(request):
    audio_file = request.FILES.get("audio")
    lang = request.POST.get("lang", "en")
    if not audio_file:
        return JsonResponse({"error": "missing_audio"}, status=400)
    if audio_file.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "audio_too_large"}, status=400)

    try:
        transcript = transcribe_audio_upload(audio_file, lang=lang)
    except Exception:
        logger.exception("Speech transcription failed")
        return JsonResponse({"error": "transcription_failed"}, status=503)

    transcript = (transcript or "").strip()
    if not transcript:
        return JsonResponse({"error": "empty_transcript"}, status=422)
    return JsonResponse({"transcript": transcript, "lang": lang})


@require_POST
def text_to_speech_api(request):
    lang = "en"
    text = ""
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8"))
            text = (data.get("text") or "").strip()
            lang = data.get("lang") or "en"
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_json"}, status=400)
    else:
        text = (request.POST.get("text") or "").strip()
        lang = request.POST.get("lang") or "en"

    if not text:
        return JsonResponse({"error": "missing_text"}, status=400)

    if len(text) > 700:
        text = text[:700]

    try:
        audio_bytes = synthesize_speech_mp3(text=text, lang=lang)
    except Exception:
        logger.exception("Text to speech generation failed")
        return JsonResponse({"error": "tts_failed"}, status=503)

    response = HttpResponse(audio_bytes, content_type="audio/mpeg")
    response["Cache-Control"] = "no-store"
    return response


@require_POST
def chat_api(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.exception("Invalid JSON payload in chat_api")
        return JsonResponse({"error": "invalid_json"}, status=400)

    user_input = data.get("message", "").strip()
    lang = data.get("lang", "en")
    if not user_input:
        return JsonResponse({"error": "empty_message"}, status=400)

    response = ai_chat_response(user_input, lang=lang)

    try:
        ChatHistory.objects.create(
            user_message=user_input,
            bot_response=response["text"],
            language=lang,
            source="chat",
            matched_scheme_count=len(response["matched_schemes"]),
            recommended_scheme_names=recommendation_names_from_response(response),
            needs_human_review=response["needs_human_review"],
        )
    except Exception:
        logger.exception("Failed to save ChatHistory")

    return JsonResponse(
        {
            "reply": response["text"],
            "needs_human_review": response["needs_human_review"],
            "recommended_schemes": [_serialize_chat_scheme(item) for item in response["matched_schemes"][:3]],
        }
    )
