import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

from django.db.models import Q

from .models import EligibilityAssessment, Scheme


CATEGORY_LABELS = {
    "education": "Education",
    "financial": "Financial Support",
    "health": "Health",
    "employment": "Jobs and Skills",
    "empowerment": "Empowerment",
    "other": "Other",
}

CATEGORY_ALIASES = {
    "education": "education",
    "study": "education",
    "student": "education",
    "scholarship": "education",
    "shikshan": "education",
    "शिक्षा": "education",
    "शिक्षण": "education",
    "financial": "financial",
    "finance": "financial",
    "loan": "financial",
    "money": "financial",
    "income": "financial",
    "आर्थिक": "financial",
    "health": "health",
    "medical": "health",
    "hospital": "health",
    "aarogya": "health",
    "स्वास्थ्य": "health",
    "आरोग्य": "health",
    "employment": "employment",
    "job": "employment",
    "jobs": "employment",
    "career": "employment",
    "skill": "employment",
    "skills": "employment",
    "livelihood": "employment",
    "रोजगार": "employment",
    "नोकरी": "employment",
    "empowerment": "empowerment",
    "women": "empowerment",
    "woman": "empowerment",
    "mahila": "empowerment",
    "selfhelp": "empowerment",
    "महिला": "empowerment",
    "other": "other",
}

INCOME_BAND_LIMITS = {
    "under_1l": 100000,
    "under_2l": 200000,
    "under_5l": 500000,
    "under_8l": 800000,
    "above_8l": 99999999,
}

EFFORT_ESTIMATES = {
    "low": "1 to 3 days",
    "medium": "3 to 10 days",
    "high": "1 to 3 weeks",
}


def match_score_percent(score: int) -> int:
    if score <= 0:
        return 0
    return max(45, min(99, round((score / 40) * 100)))


def _load_schemes_from_json() -> List[Dict]:
    path = os.path.join(os.path.dirname(__file__), "data", "schemes.json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _split_values(value: Optional[str]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        output = []
        for item in value:
            output.extend(_split_values(item))
        return output
    return [item.strip() for item in re.split(r"[\n,;|]", str(value)) if item.strip()]


def extract_scheme_slug(raw_url: Optional[str], fallback: str = "") -> str:
    url = str(raw_url or "").strip()
    if "/schemes/" in url:
        return url.rstrip("/").split("/schemes/")[-1].split("/")[0].strip()
    if fallback:
        return re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-")
    return ""


def derive_scheme_tags(scheme: Dict) -> List[str]:
    text = " ".join(
        [
            scheme.get("name", ""),
            scheme.get("description", ""),
            scheme.get("eligibility", ""),
            " ".join(scheme.get("beneficiary_tags", [])),
        ]
    ).lower()
    tags = set(scheme.get("beneficiary_tags", []))
    keyword_map = {
        "student": ["student", "scholarship", "education", "study"],
        "stipend": ["stipend", "allowance", "honorarium", "fellowship", "scholarship"],
        "mother": ["mother", "pregnant", "pregnancy", "maternity"],
        "entrepreneur": ["startup", "enterprise", "business", "self-employment", "entrepreneur", "loan"],
        "business": ["startup", "enterprise", "business", "self-employment", "entrepreneur", "msme", "loan"],
        "disability": ["disability", "disabled", "divyang"],
        "women": ["women", "woman", "female", "girl", "widow", "daughter"],
        "child": ["child", "children", "girl child"],
        "senior citizen": ["senior citizen", "old age", "elderly", "pension"],
        "farmer": ["farmer", "agriculture", "fisherman", "fishermen"],
        "job seeker": ["job", "jobs", "employment", "livelihood", "placement", "apprenticeship"],
        "housing": ["housing", "house", "home", "shelter", "awas", "residence"],
        "food": ["food", "ration", "nutrition", "grain", "anna", "khadya"],
        "rural": ["rural", "village"],
        "urban": ["urban", "city"],
    }
    for tag, keywords in keyword_map.items():
        if any(keyword in text for keyword in keywords):
            tags.add(tag)
    return sorted(tags)


def normalize_category(category: Optional[str]) -> str:
    if not category:
        return "other"

    lowered = str(category).strip().lower()
    if lowered in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[lowered]

    normalized = "".join(ch for ch in lowered if ch.isalnum() or ch.isspace()).replace(" ", "")
    return CATEGORY_ALIASES.get(normalized, "other")


def normalize_scheme_record(record: Dict) -> Dict:
    category = normalize_category(record.get("category"))
    income_limit = record.get("income_limit", 99999999)

    try:
        income_limit = int(str(income_limit).replace(",", ""))
    except (TypeError, ValueError):
        income_limit = 99999999

    verification_status = str(record.get("verification_status", "review_required")).strip().lower()
    if verification_status not in {"verified", "review_required", "stale", "broken"}:
        verification_status = "review_required"

    last_verified_on = _parse_date(record.get("last_verified_on"))
    expiry_date = _parse_date(record.get("expiry_date"))
    beneficiary_tags = [tag.lower() for tag in _split_values(record.get("beneficiary_tags"))]
    required_documents = _split_values(record.get("required_documents"))
    state_coverage = [
        "All India" if item.strip().lower() == "all" else item
        for item in (_split_values(record.get("state_coverage")) or ["All India"])
    ]
    district_coverage = _split_values(record.get("district_coverage"))

    freshness_due = not last_verified_on or last_verified_on < date.today() - timedelta(days=90)
    is_expired = bool(expiry_date and expiry_date < date.today())

    normalized = {
        "name": str(record.get("name", "")).strip(),
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, "Other"),
        "description": str(record.get("description", "")).strip(),
        "eligibility": str(record.get("eligibility", "")).strip(),
        "min_age": int(record.get("min_age", 0) or 0),
        "max_age": int(record.get("max_age", 100) or 100),
        "income_limit": income_limit,
        "gender": str(record.get("gender", "any")).strip().lower() or "any",
        "official_source_name": str(record.get("official_source_name", "")).strip(),
        "url": str(record.get("url", "")).strip(),
        "verification_status": verification_status,
        "last_verified_on": last_verified_on,
        "verification_notes": str(record.get("verification_notes", "")).strip(),
        "state_coverage": state_coverage,
        "district_coverage": district_coverage,
        "beneficiary_tags": beneficiary_tags,
        "expiry_date": expiry_date,
        "required_documents": required_documents,
        "where_to_apply": str(record.get("where_to_apply", "")).strip(),
        "offline_location": str(record.get("offline_location", "")).strip(),
        "helpline": str(record.get("helpline", "")).strip(),
        "effort_level": str(record.get("effort_level", "medium")).strip().lower() or "medium",
        "is_expired": is_expired,
        "needs_freshness_review": freshness_due,
        "has_broken_link_alert": verification_status == "broken" or not str(record.get("url", "")).strip(),
        "slug": str(record.get("slug", "")).strip(),
    }
    normalized["slug"] = normalized["slug"] or extract_scheme_slug(normalized["url"], normalized["name"])
    normalized["beneficiary_tags"] = derive_scheme_tags(normalized)
    return normalized


def _db_scheme_records() -> List[Dict]:
    try:
        queryset = Scheme.objects.all()
        upgraded_queryset = queryset.filter(
            Q(official_source_name__gt="") | Q(last_verified_on__isnull=False) | Q(where_to_apply__gt="")
        )
        if upgraded_queryset.exists():
            queryset = upgraded_queryset
        if queryset.exists():
            return list(
                queryset.values(
                    "name",
                    "category",
                    "description",
                    "eligibility",
                    "min_age",
                    "max_age",
                    "income_limit",
                    "gender",
                    "official_source_name",
                    "url",
                    "verification_status",
                    "last_verified_on",
                    "verification_notes",
                    "state_coverage",
                    "district_coverage",
                    "beneficiary_tags",
                    "expiry_date",
                    "required_documents",
                    "where_to_apply",
                    "offline_location",
                    "helpline",
                    "effort_level",
                )
            )
    except Exception:
        return []
    return []


def get_all_schemes() -> List[Dict]:
    raw_records = _db_scheme_records() or _load_schemes_from_json()
    return [normalize_scheme_record(record) for record in raw_records if record.get("name")]


def load_seed_schemes() -> List[Dict]:
    return [normalize_scheme_record(record) for record in _load_schemes_from_json() if record.get("name")]


def available_categories() -> List[Dict]:
    categories = {}
    for scheme in get_all_schemes():
        categories[scheme["category"]] = scheme["category_label"]

    ordered = []
    for key in CATEGORY_LABELS:
        if key in categories:
            ordered.append({"value": key, "label": categories[key]})
    return ordered


def derive_income_value(user_data: Dict) -> int:
    annual_income = user_data.get("annual_income")
    if annual_income:
        return annual_income

    income_band = user_data.get("income_band")
    return INCOME_BAND_LIMITS.get(income_band, 99999999)


def build_profile_tags(user_data: Dict) -> List[str]:
    tags = []
    age = user_data.get("age")
    if user_data.get("is_student"):
        tags.append("student")
    if user_data.get("is_mother"):
        tags.append("mother")
    if user_data.get("is_entrepreneur"):
        tags.append("entrepreneur")
    if user_data.get("has_disability"):
        tags.append("disability")
    if age is not None and age < 18:
        tags.append("child")
    if age is not None and age >= 60:
        tags.append("senior citizen")
    residence_type = user_data.get("residence_type")
    if residence_type:
        tags.append(residence_type.replace("_", " "))
    caste = user_data.get("caste_category")
    if caste and caste != "general":
        tags.append(caste)
    for tag in user_data.get("focus_tags", []) or []:
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _state_matches(scheme: Dict, state: Optional[str]) -> bool:
    if not state:
        return True
    if not scheme["state_coverage"]:
        return True
    if any(item.lower() in {"all india", "india", "national", "all"} for item in scheme["state_coverage"]):
        return True
    return state.lower() in {item.lower() for item in scheme["state_coverage"]}


def _district_matches(scheme: Dict, district: Optional[str]) -> bool:
    if not district or not scheme["district_coverage"]:
        return True
    return district.lower() in {item.lower() for item in scheme["district_coverage"]}


def _age_income_gender_match(scheme: Dict, user_data: Dict) -> bool:
    age = user_data.get("age")
    gender = user_data.get("gender")
    income_value = derive_income_value(user_data)

    if age is not None and not (scheme["min_age"] <= age <= scheme["max_age"]):
        return False
    if income_value > scheme["income_limit"]:
        return False
    if gender and scheme["gender"] not in {"any", gender}:
        return False
    return True


def score_scheme_match(scheme: Dict, user_data: Dict) -> int:
    if scheme["is_expired"]:
        return -100
    if not _age_income_gender_match(scheme, user_data):
        return -100
    if not _state_matches(scheme, user_data.get("state")):
        return -100
    if not _district_matches(scheme, user_data.get("district")):
        return -100

    score = 10
    if user_data.get("support_need") == scheme["category"]:
        score += 12

    profile_tags = set(build_profile_tags(user_data))
    scheme_tags = set(scheme["beneficiary_tags"])
    if profile_tags and scheme_tags:
        score += 4 * len(profile_tags.intersection(scheme_tags))

    if user_data.get("age") is not None and user_data["age"] >= 60 and "senior citizen" in scheme_tags:
        score += 5
    if user_data.get("age") is not None and user_data["age"] < 18 and "child" in scheme_tags:
        score += 5

    if user_data.get("document_readiness") == "not_ready" and scheme["effort_level"] == "high":
        score -= 3

    if scheme["verification_status"] == "verified":
        score += 4
    elif scheme["verification_status"] == "stale":
        score -= 3
    elif scheme["verification_status"] == "broken":
        score -= 8

    if scheme["needs_freshness_review"]:
        score -= 2
    if user_data.get("state") and _state_matches(scheme, user_data["state"]):
        score += 2
    return score


def build_match_reasons(scheme: Dict, user_data: Dict) -> List[str]:
    reasons = []
    if user_data.get("support_need") == scheme["category"]:
        reasons.append(f"Matches your {scheme['category_label'].lower()} need")
    if _state_matches(scheme, user_data.get("state")):
        reasons.append(f"Covers {user_data.get('state') or 'your area'}")
    if scheme["verification_status"] == "verified":
        reasons.append("Recently verified against an official source")
    if scheme["beneficiary_tags"]:
        shared = set(build_profile_tags(user_data)).intersection(set(scheme["beneficiary_tags"]))
        for tag in sorted(shared):
            reasons.append(f"Relevant for {tag}")
    if "myscheme.gov.in" in str(scheme.get("url", "")):
        reasons.append("Available on the official myScheme government portal")
    return reasons[:3]


def build_next_steps(scheme: Dict, user_data: Dict) -> Dict:
    support_hint = None
    if user_data.get("document_readiness") == "not_ready":
        support_hint = "Document support is recommended before applying."
    elif scheme["effort_level"] == "high":
        support_hint = "Consider human support before starting this application."

    return {
        "documents": scheme["required_documents"],
        "where_to_apply": scheme["where_to_apply"] or "Use the official source link to begin the application process.",
        "offline_location": scheme["offline_location"] or "District welfare office or nearest facilitation center.",
        "helpline": scheme["helpline"] or "Use the department helpline listed on the official portal.",
        "effort_label": scheme["effort_level"].title(),
        "effort_estimate": EFFORT_ESTIMATES.get(scheme["effort_level"], "Varies"),
        "support_hint": support_hint,
        "official_detail_url": scheme.get("url", ""),
    }


def recommend_schemes_from_profile(user_data: Dict, limit: int = 5) -> List[Dict]:
    ranked = []
    for scheme in get_all_schemes():
        score = score_scheme_match(scheme, user_data)
        if score <= 0:
            continue
        enriched = dict(scheme)
        enriched["match_score"] = score
        enriched["match_score_percent"] = match_score_percent(score)
        enriched["match_reasons"] = build_match_reasons(scheme, user_data)
        enriched["next_steps"] = build_next_steps(scheme, user_data)
        ranked.append(enriched)

    ranked.sort(key=lambda item: (-item["match_score"], item["name"].lower()))
    return ranked[:limit]


def check_scheme_eligibility(user_data: Dict) -> List[Dict]:
    return recommend_schemes_from_profile(user_data, limit=8)


def search_schemes(query: str, limit: int = 6, category: Optional[str] = None) -> List[Dict]:
    terms = [token.strip().lower() for token in query.split() if token.strip()]
    if category:
        terms.append(category)

    scored = []
    for scheme in get_all_schemes():
        if category and scheme["category"] != category:
            continue

        searchable = " ".join(
            [
                scheme["name"],
                scheme["description"],
                scheme["eligibility"],
                scheme["category"],
                scheme["official_source_name"],
                " ".join(scheme["beneficiary_tags"]),
            ]
        ).lower()

        score = 0
        for term in terms:
            if term in searchable:
                score += 2
            if term in scheme["name"].lower():
                score += 3
            if term == scheme["category"]:
                score += 4
        if score:
            enriched = dict(scheme)
            enriched["match_score"] = score
            enriched["match_score_percent"] = match_score_percent(score)
            enriched["next_steps"] = build_next_steps(scheme, {})
            scored.append(enriched)

    scored.sort(key=lambda item: (-item["match_score"], item["name"].lower()))
    return scored[:limit]


def filter_schemes(
    query: str = "",
    category: Optional[str] = None,
    state: Optional[str] = None,
    sort: str = "recommended",
    limit: Optional[int] = None,
) -> List[Dict]:
    filtered = []
    search_text = (query or "").strip().lower()

    for scheme in get_all_schemes():
        if category and scheme["category"] != category:
            continue
        if state and not _state_matches(scheme, state):
            continue

        if search_text:
            searchable = " ".join(
                [
                    scheme["name"],
                    scheme["description"],
                    scheme["eligibility"],
                    scheme["official_source_name"],
                    " ".join(scheme["beneficiary_tags"]),
                    " ".join(scheme["state_coverage"]),
                ]
            ).lower()
            if search_text not in searchable:
                continue

        scheme_copy = dict(scheme)
        scheme_copy["next_steps"] = build_next_steps(scheme, {})
        filtered.append(scheme_copy)

    if sort == "recent":
        filtered.sort(
            key=lambda item: (
                item["last_verified_on"] is None,
                -((item["last_verified_on"] or date.min).toordinal()),
                item["name"].lower(),
            )
        )
    elif sort == "expiry":
        filtered.sort(
            key=lambda item: (
                item["expiry_date"] is None,
                (item["expiry_date"] or date.max).toordinal(),
                item["name"].lower(),
            )
        )
    elif sort == "name":
        filtered.sort(key=lambda item: item["name"].lower())
    else:
        filtered.sort(
            key=lambda item: (
                item["verification_status"] != "verified",
                item["needs_freshness_review"],
                item["last_verified_on"] is None,
                -((item["last_verified_on"] or date.min).toordinal()),
                item["name"].lower(),
            )
        )
    if limit:
        return filtered[:limit]
    return filtered


def serialize_recommendation_names(recommendations: Iterable[Dict]) -> List[str]:
    return [item["name"] for item in recommendations]


def create_assessment_from_form(form) -> EligibilityAssessment:
    assessment = form.save(commit=False)
    recommendations = recommend_schemes_from_profile(form.cleaned_data)
    assessment.recommendation_count = len(recommendations)
    assessment.recommended_scheme_names = serialize_recommendation_names(recommendations)
    assessment.needs_human_review = len(recommendations) == 0
    assessment.save()
    return assessment
