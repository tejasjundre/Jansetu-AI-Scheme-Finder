import json
import re
from datetime import date
from html import unescape
from typing import Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache

from .location_data import canonical_state_name, get_state_district_map


MYSHEME_WEB_BASE = "https://www.myscheme.gov.in"
MYSHEME_SEARCH_API = "https://api.myscheme.gov.in/search/v6"
MYSHEME_DETAILS_API = "https://api.myscheme.gov.in/schemes/v6/public/schemes"
MYSHEME_API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Origin": MYSHEME_WEB_BASE,
    "Referer": f"{MYSHEME_WEB_BASE}/",
    "x-api-key": MYSHEME_API_KEY,
}
DETAIL_CACHE_SECONDS = 60 * 60 * 6
DETAIL_VERIFY_NOTES = "Enriched from official myScheme scheme detail endpoint."
ALL_INDIA_MARKERS = {"all", "all india", "india", "national", "pan india", "pan-india"}

LOCAL_CATEGORY_MAP = {
    "Education & Learning": "education",
    "Agriculture,Rural & Environment": "agriculture",
    "Health & Wellness": "health",
    "Skills & Employment": "employment",
    "Business & Entrepreneurship": "employment",
    "Banking,Financial Services and Insurance": "financial",
    "Women and Child": "empowerment",
    "Social welfare & Empowerment": "empowerment",
    "Housing & Shelter": "financial",
    "Science, IT & Communications": "education",
    "Sports & Culture": "education",
    "Public Safety,Law & Justice": "other",
    "Transport & Infrastructure": "other",
    "Travel & Tourism": "other",
    "Utility & Sanitation": "health",
}

TAG_KEYWORDS = {
    "student": ["student", "scholarship", "education", "study"],
    "mother": ["mother", "pregnant", "pregnancy", "maternity", "childbirth"],
    "women": ["woman", "women", "female", "girl", "daughter", "widow", "mahila"],
    "entrepreneur": ["business", "startup", "entrepreneur", "enterprise", "self-employment"],
    "disability": ["disability", "disabled", "divyang", "special needs"],
    "senior citizen": ["senior citizen", "old age", "elderly", "pension"],
    "child": ["child", "children", "girl child", "boy child"],
    "rural": ["rural", "village"],
    "farmer": ["farmer", "farming", "agriculture", "fisherman", "fishermen"],
}
HELPLINE_REGEX = re.compile(r"(?:\+91[-\s]?)?(?:1800[-\s]?\d{3}[-\s]?\d{3,4}|[6-9]\d{9})")


def _http_json(url: str, referer: Optional[str] = None) -> Dict:
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return {}


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _strip_markdown(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"[*_#>`-]+", " ", text)
    return _collapse_whitespace(text.replace("\n", " "))


def _walk_text_nodes(nodes: Iterable) -> List[str]:
    text_parts = []
    for node in nodes or []:
        if isinstance(node, dict):
            if node.get("text"):
                text_parts.append(str(node["text"]))
            text_parts.extend(_walk_text_nodes(node.get("children", [])))
        elif isinstance(node, list):
            text_parts.extend(_walk_text_nodes(node))
    return text_parts


def _walk_links(nodes: Iterable) -> List[str]:
    links = []
    for node in nodes or []:
        if isinstance(node, dict):
            if node.get("type") == "link" and node.get("link"):
                links.append(str(node["link"]).strip())
            links.extend(_walk_links(node.get("children", [])))
        elif isinstance(node, list):
            links.extend(_walk_links(node))
    return links


def _extract_lines_from_rich_content(nodes: Iterable) -> List[str]:
    lines = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        text = _collapse_whitespace(" ".join(_walk_text_nodes(node.get("children", []))))
        if text:
            lines.append(text)
    return lines


def _extract_list_from_markdown(markdown_text: str) -> List[str]:
    items = []
    for line in (markdown_text or "").splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", line).strip()
        cleaned = _collapse_whitespace(cleaned)
        if cleaned:
            items.append(cleaned)
    return items


def _dedupe_text(values: Iterable[str]) -> List[str]:
    output = []
    seen = set()
    for value in values:
        cleaned = _collapse_whitespace(str(value))
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output


def _extract_slug_from_url(url: str) -> str:
    if "/schemes/" not in (url or ""):
        return ""
    return str(url).rstrip("/").split("/schemes/")[-1].split("/")[0].strip()


def _extract_labels(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        labels = []
        label = _collapse_whitespace(value.get("label"))
        if label:
            labels.append(label)
        name = _collapse_whitespace(value.get("name"))
        if name:
            labels.append(name)
        values = value.get("value")
        if isinstance(values, str):
            cleaned = _collapse_whitespace(values)
            if cleaned:
                labels.append(cleaned)
        return labels
    if isinstance(value, list):
        output = []
        for item in value:
            output.extend(_extract_labels(item))
        return output
    return []


def _normalize_state_coverage(raw_values) -> List[str]:
    states = []
    for state in _extract_labels(raw_values):
        cleaned = canonical_state_name(_collapse_whitespace(state))
        if not cleaned:
            continue
        if cleaned.lower() in ALL_INDIA_MARKERS:
            return ["All India"]
        if cleaned not in states:
            states.append(cleaned)
    return states or ["All India"]


def _expand_state_districts(states: Iterable[str], max_states: int = 3, max_districts: int = 450) -> List[str]:
    normalized_states = [canonical_state_name(str(item or "").strip()) for item in states if item]
    if not normalized_states:
        return []
    if any(state.lower() in ALL_INDIA_MARKERS for state in normalized_states):
        return []
    if len(normalized_states) > max_states:
        return []

    district_map = get_state_district_map()
    districts = []
    seen = set()
    for state in normalized_states:
        for district in district_map.get(state, []):
            lowered = district.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            districts.append(district)
            if len(districts) > max_districts:
                return []
    return districts


def _infer_effort_level(document_count: int, step_count: int) -> str:
    if document_count >= 8 or step_count >= 6:
        return "high"
    if document_count >= 3 or step_count >= 2:
        return "medium"
    return "low"


def _extract_helpline_value(values: Iterable[str]) -> str:
    joined = " \n ".join(str(value or "") for value in values)
    if not joined.strip():
        return ""

    matches = []
    for raw in HELPLINE_REGEX.findall(joined):
        normalized = _collapse_whitespace(raw).replace(" ", "").replace("-", "")
        if normalized and normalized not in matches:
            matches.append(normalized)

    if matches:
        return ", ".join(matches[:3])
    return ""


def _derive_beneficiary_tags(text: str, explicit_tags: Optional[Iterable[str]] = None) -> List[str]:
    combined = " ".join(_dedupe_text(explicit_tags or [])) + " " + (text or "")
    lowered = combined.lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            tags.append(tag)
    for item in explicit_tags or []:
        cleaned = _collapse_whitespace(str(item)).lower()
        if cleaned:
            tags.append(cleaned)
    return _dedupe_text(tags)


def _infer_gender(text: str, tags: Iterable[str]) -> str:
    lowered = f"{text} {' '.join(tags)}".lower()
    if any(token in lowered for token in ["women", "woman", "female", "girl", "mother", "daughter", "widow"]):
        return "female"
    if any(token in lowered for token in ["men", "man", "male", "boy"]):
        return "male"
    return "any"


def _category_from_labels(labels: Iterable[str]) -> str:
    for label in labels or []:
        if label in LOCAL_CATEGORY_MAP:
            return LOCAL_CATEGORY_MAP[label]
    return "other"


def build_myscheme_summary_record(item: Dict) -> Optional[Dict]:
    fields = item.get("fields") or {}
    slug = _collapse_whitespace(fields.get("slug"))
    if not slug:
        return None

    categories = fields.get("schemeCategory") or []
    name = _collapse_whitespace(fields.get("schemeName"))
    brief = _collapse_whitespace(fields.get("briefDescription"))
    tags = _derive_beneficiary_tags(
        f"{name} {brief} {' '.join(categories)}",
        explicit_tags=fields.get("tags") or [],
    )
    state_values = _normalize_state_coverage(fields.get("beneficiaryState") or ["All"])
    district_values = _dedupe_text(_extract_labels(fields.get("beneficiaryDistrict")))
    if not district_values:
        district_values = _expand_state_districts(state_values)
    ministry = _collapse_whitespace(fields.get("nodalMinistryName")) or "myScheme"
    detail_url = f"{MYSHEME_WEB_BASE}/schemes/{slug}"

    return {
        "name": name,
        "slug": slug,
        "category": _category_from_labels(categories),
        "description": brief or "Open the official record to read the full scheme details.",
        "eligibility": "Open the official scheme record to review the latest eligibility conditions.",
        "min_age": 0,
        "max_age": 110,
        "income_limit": 99999999,
        "gender": _infer_gender(f"{name} {brief}", tags),
        "official_source_name": ministry,
        "url": detail_url,
        "verification_status": "verified",
        "last_verified_on": date.today().isoformat(),
        "verification_notes": "Imported from the official myScheme government catalogue.",
        "state_coverage": state_values,
        "district_coverage": district_values,
        "beneficiary_tags": tags,
        "expiry_date": fields.get("schemeCloseDate"),
        "required_documents": [],
        "where_to_apply": "Open the official myScheme page to read eligibility, documents, and available application channels.",
        "offline_location": ministry,
        "helpline": "",
        "effort_level": "medium",
    }


def merge_myscheme_detail_into_record(summary_record: Dict, detail: Optional[Dict]) -> Dict:
    if not detail:
        return summary_record

    merged = dict(summary_record)
    categories = detail.get("categories") or []
    mapped_category = _category_from_labels(categories)
    if mapped_category != "other" or merged.get("category") == "other":
        merged["category"] = mapped_category

    description = _collapse_whitespace(detail.get("brief_description") or detail.get("description") or "")
    if description:
        merged["description"] = description

    eligibility_text = _collapse_whitespace(detail.get("eligibility_text") or "")
    if eligibility_text:
        merged["eligibility"] = eligibility_text

    nodal_ministry = _collapse_whitespace(detail.get("nodal_ministry") or "")
    nodal_department = _collapse_whitespace(detail.get("nodal_department") or "")
    if nodal_ministry:
        merged["official_source_name"] = nodal_ministry

    if detail.get("state_coverage"):
        merged["state_coverage"] = _normalize_state_coverage(detail.get("state_coverage") or [])

    detail_districts = _dedupe_text(detail.get("district_coverage") or [])
    if not detail_districts:
        detail_districts = _expand_state_districts(merged.get("state_coverage") or [])
    if detail_districts:
        merged["district_coverage"] = detail_districts

    tags = _dedupe_text(detail.get("tags") or merged.get("beneficiary_tags") or [])
    if tags:
        merged["beneficiary_tags"] = tags

    documents = _dedupe_text(detail.get("documents") or merged.get("required_documents") or [])
    merged["required_documents"] = documents

    steps = _dedupe_text(detail.get("application_steps") or [])
    links = detail.get("quick_links") or []
    if steps:
        merged["where_to_apply"] = " ".join(steps[:2])
    elif links:
        first_link = links[0]
        merged["where_to_apply"] = f"Start from {first_link.get('label', 'official portal')}: {first_link.get('url', '')}".strip()

    if nodal_department:
        merged["offline_location"] = nodal_department
    elif nodal_ministry:
        merged["offline_location"] = nodal_ministry

    faq_values = []
    for item in detail.get("faqs") or []:
        question = _collapse_whitespace(item.get("question"))
        answer = _collapse_whitespace(item.get("answer_md"))
        faq_values.extend([question, answer])
    helpline_value = _extract_helpline_value(
        [
            detail.get("description"),
            detail.get("eligibility_text"),
            " ".join(steps),
            " ".join(documents),
            " ".join(faq_values),
            merged.get("helpline", ""),
        ]
    )
    if helpline_value:
        merged["helpline"] = helpline_value

    merged["effort_level"] = _infer_effort_level(len(documents), len(steps))
    merged["verification_status"] = "verified"
    merged["last_verified_on"] = date.today().isoformat()

    existing_note = _collapse_whitespace(merged.get("verification_notes", ""))
    if DETAIL_VERIFY_NOTES.lower() not in existing_note.lower():
        merged["verification_notes"] = _collapse_whitespace(
            f"{existing_note} {DETAIL_VERIFY_NOTES}".strip()
        )

    detail_slug = _collapse_whitespace(detail.get("slug") or "")
    if detail_slug:
        merged["slug"] = detail_slug
        merged["url"] = f"{MYSHEME_WEB_BASE}/schemes/{detail_slug}"
    return merged


def enrich_summary_record(record: Dict, lang: str = "en") -> Dict:
    slug = _collapse_whitespace(record.get("slug") or _extract_slug_from_url(record.get("url", "")))
    if not slug:
        return record

    detail = fetch_scheme_detail(slug, lang=lang)
    return merge_myscheme_detail_into_record(record, detail)


def fetch_catalog_page(offset: int = 0, size: int = 100, keyword: str = "", filters: Optional[List[Dict]] = None) -> Dict:
    size = max(1, min(int(size or 100), 100))
    payload_filters = quote(json.dumps(filters or []))
    query = urlencode(
        {
            "lang": "en",
            "q": payload_filters,
            "keyword": keyword,
            "sort": "schemename-asc",
            "from": offset,
            "size": size,
        }
    )
    query = query.replace("%255B", "%5B").replace("%255D", "%5D").replace("%257B", "%7B").replace("%257D", "%7D")
    query = query.replace("%2522", "%22").replace("%253A", "%3A").replace("%252C", "%2C")
    return _http_json(f"{MYSHEME_SEARCH_API}/schemes?{query}", referer=f"{MYSHEME_WEB_BASE}/search")


def iter_catalog_records(size: int = 100, limit: Optional[int] = None) -> Iterable[Dict]:
    size = max(1, min(int(size or 100), 100))
    offset = 0
    yielded = 0
    total = None

    while total is None or offset < total:
        payload = fetch_catalog_page(offset=offset, size=size)
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            break
        hits = (data.get("hits") or {}).get("items") or []
        total = int(((data.get("summary") or {}).get("total")) or len(hits))

        if not hits:
            break

        for item in hits:
            record = build_myscheme_summary_record(item)
            if not record:
                continue
            yield record
            yielded += 1
            if limit and yielded >= limit:
                return

        offset += size


def _pick_apply_links(detail_url: str, references: List[Dict], process_nodes: List[Dict], channels: List[Dict]) -> List[Dict]:
    links = [{"label": "Open myScheme page", "url": detail_url}]

    for channel in channels or []:
        url = _collapse_whitespace(channel.get("applicationUrl"))
        label = _collapse_whitespace(channel.get("applicationName")) or "Apply online"
        if url and "temp.com" not in url:
            links.append({"label": label, "url": url})

    for reference in references or []:
        url = _collapse_whitespace(reference.get("url"))
        label = _collapse_whitespace(reference.get("title")) or "Reference"
        if url:
            links.append({"label": label, "url": url})

    for process_link in _walk_links(process_nodes):
        if process_link:
            links.append({"label": "Application portal", "url": process_link})

    deduped = []
    seen = set()
    for link in links:
        url = link["url"].strip()
        if not url or url.lower() in seen:
            continue
        seen.add(url.lower())
        deduped.append(link)
    return deduped[:6]


def fetch_scheme_detail(slug: str, lang: str = "en") -> Optional[Dict]:
    slug = _collapse_whitespace(slug)
    if not slug:
        return None

    cache_key = f"myscheme-detail:{lang}:{slug}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    referer = f"{MYSHEME_WEB_BASE}/schemes/{slug}"
    main_payload = _http_json(
        f"{MYSHEME_DETAILS_API}?slug={quote(slug)}&lang={lang}",
        referer=referer,
    )
    main_data = main_payload.get("data") or {}
    scheme_id = main_data.get("_id")
    lang_data = (main_data.get(lang) or main_data.get("en") or {})
    if not scheme_id or not lang_data:
        return None

    docs_payload = _http_json(f"{MYSHEME_DETAILS_API}/{scheme_id}/documents?lang={lang}", referer=referer)
    faq_payload = _http_json(f"{MYSHEME_DETAILS_API}/{scheme_id}/faqs?lang={lang}", referer=referer)
    channel_payload = _http_json(f"{MYSHEME_DETAILS_API}/{scheme_id}/applicationchannel", referer=referer)

    basic = lang_data.get("basicDetails") or {}
    content = lang_data.get("schemeContent") or {}
    eligibility = lang_data.get("eligibilityCriteria") or {}
    process = lang_data.get("applicationProcess") or []
    docs_data = ((docs_payload.get("data") or {}).get(lang) or {})
    faq_data = ((faq_payload.get("data") or {}).get(lang) or {})
    channels = (((channel_payload.get("data") or {}).get("applicationChannel")) or []) if isinstance(channel_payload.get("data"), dict) else []

    detail_url = f"{MYSHEME_WEB_BASE}/schemes/{slug}"
    references = content.get("references") or []
    description = _strip_markdown(content.get("detailedDescription_md") or content.get("briefDescription") or "")
    benefits = _strip_markdown(content.get("benefits_md") or "")
    eligibility_text = _strip_markdown(eligibility.get("eligibilityDescription_md") or "")
    document_list = _extract_list_from_markdown(docs_data.get("documentsRequired_md") or "")
    if not document_list:
        document_list = _extract_lines_from_rich_content(docs_data.get("documents_required") or [])
    application_steps = _extract_lines_from_rich_content(process)
    faq_items = faq_data.get("faqs") or []
    tags = _derive_beneficiary_tags(
        " ".join(
            [
                basic.get("schemeName") or "",
                content.get("briefDescription") or "",
                eligibility_text,
                " ".join(item.get("label") for item in basic.get("schemeCategory") or []),
            ]
        ),
        explicit_tags=basic.get("tags") or [],
    )
    state_coverage = _normalize_state_coverage(main_data.get("beneficiaryState") or basic.get("state") or [])
    district_coverage = _dedupe_text(
        _extract_labels(basic.get("district"))
        + _extract_labels(basic.get("districts"))
        + _extract_labels((basic.get("beneficiaryDistrict") or {}))
    )
    if not district_coverage:
        district_coverage = _expand_state_districts(state_coverage)

    detail = {
        "slug": slug,
        "name": _collapse_whitespace(basic.get("schemeName")),
        "short_title": _collapse_whitespace(basic.get("schemeShortTitle")),
        "detail_url": detail_url,
        "brief_description": _collapse_whitespace(content.get("briefDescription")),
        "description": description,
        "benefits": benefits,
        "eligibility_text": eligibility_text,
        "documents": _dedupe_text(document_list),
        "application_steps": _dedupe_text(application_steps),
        "quick_links": _pick_apply_links(detail_url, references, process, channels),
        "references": [link for link in references if link.get("url")],
        "faqs": faq_items[:6],
        "nodal_ministry": _collapse_whitespace((basic.get("nodalMinistryName") or {}).get("label")),
        "nodal_department": _collapse_whitespace((basic.get("nodalDepartmentName") or {}).get("label")),
        "scheme_level": _collapse_whitespace((basic.get("level") or {}).get("label")),
        "scheme_type": _collapse_whitespace((basic.get("schemeType") or {}).get("label")),
        "categories": [
            _collapse_whitespace(item.get("label"))
            for item in basic.get("schemeCategory") or []
            if item.get("label")
        ],
        "state_coverage": state_coverage,
        "district_coverage": district_coverage,
        "tags": tags,
    }
    cache.set(cache_key, detail, DETAIL_CACHE_SECONDS)
    return detail
