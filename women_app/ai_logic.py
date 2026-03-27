import re
from typing import Dict, Optional

from .eligibility import (
    CATEGORY_LABELS,
    check_scheme_eligibility,
    normalize_category,
    recommend_schemes_from_profile,
    search_schemes,
    serialize_recommendation_names,
)


CHAT_COPY = {
    "en": {
        "greeting": "JanSetu can help you find government schemes in a simple way. Tell me your age, state, income, and what kind of help you need.",
        "need_profile": "I can check this, but I still need your {fields}. Example: I am 24, from Maharashtra, income 180000, and I need financial help.",
        "profile_intro": "Here is the profile I understood: {summary}.",
        "results_intro": "These are the best matches for you:",
        "no_match": "I could not find a strong match yet. Try the step-by-step wizard or ask for human support.",
        "discovery_intro": "These scheme records look useful:",
        "fallback": "Tell me the problem you need help with, like scholarship, health, pension, job, business, family support, or disability support. Age, income, and state help me match better.",
        "reasons_label": "Why it fits",
        "official_link_label": "Official link",
        "field_age": "age",
        "field_income": "income",
        "field_need": "need type",
        "summary_age": "age",
        "summary_income": "income",
    },
    "hi": {
        "greeting": "जनसेतु आपको सरकारी योजनाएं खोजने, पात्रता समझने और अगले कदम जानने में मदद कर सकता है। अपनी उम्र, आय, राज्य और ज़रूरत बताइए।",
        "need_profile": "मैं यह देख सकता हूं, लेकिन मुझे अभी आपकी {fields} चाहिए। उदाहरण: मेरी उम्र 24 है, मैं महाराष्ट्र से हूं, आय 180000 है और मुझे आर्थिक सहायता चाहिए।",
        "profile_intro": "मैंने आपकी प्रोफ़ाइल ऐसे समझी: {summary}",
        "results_intro": "ये आपके लिए सबसे अच्छे मिलान हैं:",
        "no_match": "अभी कोई मज़बूत मिलान नहीं मिला। चरण-दर-चरण विज़ार्ड आज़माएं या मानव सहायता मांगें।",
        "discovery_intro": "ये योजना रिकॉर्ड उपयोगी लगते हैं:",
        "fallback": "अपनी समस्या बताइए, जैसे छात्रवृत्ति, स्वास्थ्य, पेंशन, नौकरी, व्यवसाय, परिवार सहायता या दिव्यांग सहायता। बेहतर मिलान के लिए उम्र, आय और राज्य भी बताएं।",
        "reasons_label": "यह क्यों उपयुक्त है",
        "official_link_label": "आधिकारिक लिंक",
        "field_age": "उम्र",
        "field_income": "आय",
        "field_need": "ज़रूरत का प्रकार",
        "summary_age": "उम्र",
        "summary_income": "आय",
    },
    "mr": {
        "greeting": "जनसेतु तुम्हाला सरकारी योजना शोधणे, पात्रता समजून घेणे आणि पुढचे पाऊल जाणून घेणे यासाठी मदत करू शकतो. तुमचे वय, उत्पन्न, राज्य आणि गरज सांगा.",
        "need_profile": "मी हे पाहू शकतो, पण अजून तुमची {fields} हवी आहेत. उदाहरण: माझे वय 24 आहे, मी महाराष्ट्रातून आहे, उत्पन्न 180000 आहे आणि मला आर्थिक मदत हवी आहे.",
        "profile_intro": "मी तुमची प्रोफाइल अशी समजली: {summary}",
        "results_intro": "हे तुमच्यासाठी सर्वात योग्य पर्याय आहेत:",
        "no_match": "आत्ता ठोस जुळणी मिळाली नाही. टप्प्याटप्प्याचा विज़ार्ड वापरा किंवा मानवी मदत मागा.",
        "discovery_intro": "हे योजना रेकॉर्ड उपयोगी वाटतात:",
        "fallback": "तुमची अडचण सांगा, जसे शिष्यवृत्ती, आरोग्य, पेन्शन, नोकरी, व्यवसाय, कुटुंब मदत किंवा दिव्यांग मदत. चांगल्या जुळणीसाठी वय, उत्पन्न आणि राज्यही सांगा.",
        "reasons_label": "हे का योग्य आहे",
        "official_link_label": "अधिकृत लिंक",
        "field_age": "वय",
        "field_income": "उत्पन्न",
        "field_need": "गरजेचा प्रकार",
        "summary_age": "वय",
        "summary_income": "उत्पन्न",
    },
}

GREETINGS = {"hello", "hi", "hey", "namaste", "नमस्ते", "नमस्कार"}

GENDER_KEYWORDS = {
    "female": "female",
    "woman": "female",
    "women": "female",
    "girl": "female",
    "mahila": "female",
    "महिला": "female",
    "male": "male",
    "man": "male",
    "boy": "male",
    "पुरुष": "male",
}

STATE_KEYWORDS = [
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Maharashtra",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Jammu and Kashmir",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Madhya Pradesh",
    "Odisha",
    "Punjab",
    "Puducherry",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]


def _copy(lang: str) -> Dict:
    return CHAT_COPY.get(lang, CHAT_COPY["en"])


def _extract_age(user_input: str) -> Optional[int]:
    patterns = [
        r"\b(?:i am|i'm|age is|age|उम्र|वय)\s*(\d{1,2})\b",
        r"\b(\d{1,2})\s*(?:years old|year old|yrs old|yrs|years)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            return int(match.group(1))
    return None


def _parse_income_value(raw_value: str, suffix: str = "") -> Optional[int]:
    cleaned = raw_value.replace(",", "").strip()
    if not cleaned:
        return None

    value = float(cleaned)
    suffix = suffix.lower().strip()
    if suffix in {"l", "lac", "lakh", "lakhs"}:
        value *= 100000
    elif suffix == "k":
        value *= 1000
    return int(value)


def _extract_income(user_input: str) -> Optional[int]:
    patterns = [
        r"\b(?:income|salary|earning|earnings|आय|उत्पन्न)\s*(?:is|=|:)?\s*(?:rs\.?|inr|rupees)?\s*([\d,]+(?:\.\d+)?)\s*(l|lac|lakh|lakhs|k)?\b",
        r"\b(?:rs\.?|inr|rupees)\s*([\d,]+(?:\.\d+)?)\s*(l|lac|lakh|lakhs|k)?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            return _parse_income_value(match.group(1), match.group(2) or "")
    return None


def _extract_gender(user_input: str) -> Optional[str]:
    for keyword, gender in GENDER_KEYWORDS.items():
        if keyword.lower() in user_input:
            return gender
    return None


def _extract_state(user_input: str) -> Optional[str]:
    lowered = user_input.lower()
    for state in STATE_KEYWORDS:
        if state.lower() in lowered:
            return state
    return None


def _extract_category(user_input: str) -> Optional[str]:
    for keyword in list(CATEGORY_LABELS) + [
        "study",
        "scholarship",
        "loan",
        "finance",
        "money",
        "medical",
        "hospital",
        "job",
        "jobs",
        "skill",
        "skills",
        "career",
        "mahila",
        "women",
        "शिक्षा",
        "शिक्षण",
        "आर्थिक",
        "आरोग्य",
        "स्वास्थ्य",
        "रोजगार",
        "नोकरी",
    ]:
        if keyword.lower() in user_input:
            return normalize_category(keyword)
    return None


def _extract_profile_tags(user_input: str) -> Dict:
    lowered = user_input.lower()
    return {
        "is_student": any(term in lowered for term in ["student", "scholarship", "विद्यार्थी"]),
        "is_mother": any(term in lowered for term in ["mother", "pregnant", "माता", "आई"]),
        "is_entrepreneur": any(term in lowered for term in ["business", "startup", "entrepreneur", "self-employment", "उद्योग"]),
        "has_disability": any(term in lowered for term in ["disability", "disabled", "दिव्यांग"]),
    }


def extract_user_profile(user_input: str) -> Dict:
    lowered = user_input.lower()
    profile_tags = _extract_profile_tags(lowered)
    return {
        "age": _extract_age(lowered),
        "annual_income": _extract_income(lowered),
        "income_band": "",
        "gender": _extract_gender(lowered) or "any",
        "state": _extract_state(lowered),
        "district": "",
        "residence_type": "",
        "support_need": _extract_category(lowered),
        "caste_category": "general",
        "document_readiness": "partial",
        **profile_tags,
    }


def _format_currency(value: int) -> str:
    if value >= 100000:
        return f"Rs {value / 100000:.1f} lakh".replace(".0", "")
    return f"Rs {value:,}"


def _profile_summary(profile: Dict, lang: str) -> str:
    copy = _copy(lang)
    details = []
    if profile.get("age") is not None:
        details.append(f"{copy['summary_age']} {profile['age']}")
    if profile.get("annual_income") is not None:
        details.append(f"{copy['summary_income']} {_format_currency(profile['annual_income'])}")
    if profile.get("gender") and profile.get("gender") != "any":
        details.append(profile["gender"])
    if profile.get("state"):
        details.append(profile["state"])
    if profile.get("support_need"):
        details.append(CATEGORY_LABELS.get(profile["support_need"], "Other"))
    return ", ".join(details)


def _render_recommendations(recommendations, lang: str) -> str:
    copy = _copy(lang)
    lines = [copy["results_intro"]]
    for scheme in recommendations[:3]:
        lines.append(f"- {scheme['name']} [{scheme['category_label']}]")
        if scheme.get("match_reasons"):
            lines.append(f"  {copy['reasons_label']}: {', '.join(scheme['match_reasons'])}")
        if scheme.get("url"):
            lines.append(f"  {copy['official_link_label']}: {scheme['url']}")
    return "\n".join(lines)


def _missing_fields(profile: Dict, lang: str):
    copy = _copy(lang)
    missing = []
    if profile.get("age") is None:
        missing.append(copy["field_age"])
    if profile.get("annual_income") is None:
        missing.append(copy["field_income"])
    if not profile.get("support_need"):
        missing.append(copy["field_need"])
    return missing


def ai_chat_response(user_input: str, lang: str = "en") -> Dict:
    cleaned_input = (user_input or "").strip()
    lowered = cleaned_input.lower()
    copy = _copy(lang)
    profile = extract_user_profile(cleaned_input)

    if any(word in lowered.split() for word in GREETINGS):
        return {
            "text": copy["greeting"],
            "matched_schemes": [],
            "needs_human_review": False,
        }

    if any(term in lowered for term in ["eligible", "eligibility", "apply", "can i get", "पात्र", "मिळेल"]):
        missing = _missing_fields(profile, lang)
        if missing:
            return {
                "text": copy["need_profile"].format(fields=", ".join(missing)),
                "matched_schemes": [],
                "needs_human_review": False,
            }

        recommendations = check_scheme_eligibility(profile)
        if not recommendations:
            return {
                "text": copy["no_match"],
                "matched_schemes": [],
                "needs_human_review": True,
            }

        return {
            "text": copy["profile_intro"].format(summary=_profile_summary(profile, lang)) + "\n" + _render_recommendations(recommendations, lang),
            "matched_schemes": recommendations,
            "needs_human_review": False,
        }

    if profile.get("age") is not None and profile.get("annual_income") is not None and profile.get("support_need"):
        recommendations = recommend_schemes_from_profile(profile)
        if not recommendations:
            return {
                "text": copy["no_match"],
                "matched_schemes": [],
                "needs_human_review": True,
            }
        return {
            "text": copy["profile_intro"].format(summary=_profile_summary(profile, lang)) + "\n" + _render_recommendations(recommendations, lang),
            "matched_schemes": recommendations,
            "needs_human_review": False,
        }

    if "scheme" in lowered or "yojana" in lowered or "योजना" in lowered or "योजने" in lowered or profile.get("support_need"):
        matches = search_schemes(cleaned_input, limit=4, category=profile.get("support_need"))
        if not matches:
            return {
                "text": copy["no_match"],
                "matched_schemes": [],
                "needs_human_review": True,
            }
        lines = [copy["discovery_intro"]]
        for scheme in matches:
            lines.append(f"- {scheme['name']} [{scheme['category_label']}]")
            lines.append(f"  {scheme['description']}")
        return {
            "text": "\n".join(lines),
            "matched_schemes": matches,
            "needs_human_review": False,
        }

    return {
        "text": copy["fallback"],
        "matched_schemes": [],
        "needs_human_review": True,
    }


def recommendation_names_from_response(response: Dict):
    return serialize_recommendation_names(response.get("matched_schemes", []))
