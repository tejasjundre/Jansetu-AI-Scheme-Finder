import re
from datetime import date
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urldefrag, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .location_data import canonical_state_name, get_state_district_map


SCHEME_KEYWORDS = [
    "scheme",
    "yojana",
    "scholarship",
    "subsidy",
    "pension",
    "benefit",
    "welfare",
    "farmer",
    "agriculture",
    "employment",
    "skill",
    "grant",
    "loan",
    "stipend",
    "business",
    "entrepreneur",
]
GENERIC_ANCHORS = {
    "home",
    "about",
    "contact",
    "login",
    "register",
    "sitemap",
    "gallery",
    "news",
    "notice",
    "tender",
    "faq",
}
BLOCKED_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".ico", ".woff", ".ttf", ".zip")


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = ""
        for key, value in attrs:
            if key.lower() == "href":
                href = str(value or "").strip()
                break
        self._href = href
        self._text_parts = []

    def handle_data(self, data):
        if self._href is None:
            return
        text = str(data or "").strip()
        if text:
            self._text_parts.append(text)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self._href is None:
            return
        text = " ".join(self._text_parts).strip()
        self.links.append((self._href, text))
        self._href = None
        self._text_parts = []


def _normalize_url(url: str):
    cleaned = str(url or "").strip()
    if not cleaned:
        return ""
    base, _ = urldefrag(cleaned)
    base = base.strip()
    if not base:
        return ""
    try:
        parsed = urlsplit(base)
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return base
    safe_path = quote(parsed.path or "/", safe="/:@%+-._~!$&'()*;,=")
    safe_query = quote(parsed.query, safe="=&:@%+-._~!$'()*;,/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, safe_path, safe_query, ""))


def _host_key(url: str):
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _same_host_family(seed_url: str, target_url: str):
    seed_host = _host_key(seed_url)
    target_host = _host_key(target_url)
    return target_host == seed_host or target_host.endswith("." + seed_host) or seed_host.endswith("." + target_host)


def _fetch_html(url: str, timeout_seconds: int = 8):
    request = Request(url, headers={"User-Agent": "JanSetuCrawler/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "html" not in content_type and "text" not in content_type:
                return ""
            return response.read().decode("utf-8", "ignore")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return ""


def _keyword_score(text: str):
    lowered = (text or "").lower()
    return sum(1 for keyword in SCHEME_KEYWORDS if keyword in lowered)


def _is_section_candidate(url: str, text: str):
    if not url or url.lower().endswith(BLOCKED_SUFFIXES):
        return False
    score = _keyword_score(f"{url} {text}")
    return score >= 1


def _is_scheme_link(url: str, text: str):
    if not url or url.lower().endswith(BLOCKED_SUFFIXES):
        return False
    if url.lower().startswith(("javascript:", "mailto:", "tel:")):
        return False

    label = (text or "").strip().lower()
    if label in GENERIC_ANCHORS:
        return False

    score = _keyword_score(f"{url} {label}")
    return score >= 1


def _link_name(text: str, url: str, state_name: str):
    clean_text = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean_text) >= 4 and clean_text.lower() not in GENERIC_ANCHORS:
        return clean_text[:180]
    path = (urlparse(url).path or "").strip("/")
    slug = path.split("/")[-1] if path else "scheme-link"
    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    if not slug:
        slug = "official scheme link"
    return f"{slug.title()} ({state_name})"


def _infer_category(url: str, text: str):
    lowered = f"{url} {text}".lower()
    if any(token in lowered for token in ["agriculture", "farmer", "farming", "crop", "kisan", "krishi", "irrigation"]):
        return "agriculture"
    if any(token in lowered for token in ["scholarship", "student", "education", "epass"]):
        return "education"
    if any(token in lowered for token in ["health", "hospital", "medical"]):
        return "health"
    if any(token in lowered for token in ["loan", "subsidy", "grant", "financial"]):
        return "financial"
    if any(token in lowered for token in ["job", "employment", "skill", "entrepreneur", "business"]):
        return "employment"
    if any(token in lowered for token in ["social", "welfare", "empowerment", "pension"]):
        return "empowerment"
    return "other"


def _infer_tags(url: str, text: str, state_name: str):
    lowered = f"{url} {text}".lower()
    tags = [state_name.lower(), "state source", "verified source"]
    for keyword in SCHEME_KEYWORDS:
        if keyword in lowered and keyword not in tags:
            tags.append(keyword)
    return tags


def _state_district_coverage(state_name: str, max_districts: int = 450):
    districts = get_state_district_map().get(canonical_state_name(state_name), [])
    if len(districts) > max_districts:
        return []
    return districts


def crawl_source_for_scheme_links(
    source_url: str,
    max_pages: int = 12,
    max_links: int = 80,
    timeout_seconds: int = 8,
):
    source_url = _normalize_url(source_url)
    if not source_url:
        return []

    queue = [source_url]
    seen_pages = set()
    candidates = {}

    while queue and len(seen_pages) < max_pages:
        current_url = queue.pop(0)
        current_url = _normalize_url(current_url)
        if not current_url or current_url in seen_pages:
            continue
        seen_pages.add(current_url)

        html = _fetch_html(current_url, timeout_seconds=timeout_seconds)
        if not html:
            continue

        parser = _LinkParser()
        parser.feed(html)

        for href, label in parser.links:
            absolute = _normalize_url(urljoin(current_url, href))
            if not absolute or not absolute.startswith(("http://", "https://")):
                continue
            if not _same_host_family(source_url, absolute):
                continue

            if _is_section_candidate(absolute, label) and absolute not in seen_pages and absolute not in queue:
                if len(queue) < max_pages * 3:
                    queue.append(absolute)

            if not _is_scheme_link(absolute, label):
                continue

            score = _keyword_score(f"{absolute} {label}")
            previous = candidates.get(absolute)
            if not previous or score > previous["score"]:
                candidates[absolute] = {"url": absolute, "label": label.strip(), "score": score}

    ranked = sorted(candidates.values(), key=lambda item: (-item["score"], item["url"]))
    return ranked[: max_links]


def build_crawled_scheme_record(source, discovered):
    state_name = canonical_state_name(source["state"])
    source_name = source["source_name"]
    url = discovered["url"]
    label = discovered.get("label", "")
    category = _infer_category(url, label)
    tags = _infer_tags(url, label, state_name)

    return {
        "name": _link_name(label, url, state_name),
        "category": category,
        "description": (
            f"Crawled from verified source {source_name}. "
            "Open the official page to review current scheme rules and application process."
        ),
        "eligibility": "Eligibility is defined on the linked official state source page.",
        "min_age": 0,
        "max_age": 120,
        "income_limit": 99999999,
        "gender": "any",
        "official_source_name": source_name,
        "url": url,
        "verification_status": "verified",
        "last_verified_on": date.today().isoformat(),
        "verification_notes": f"Auto-discovered from verified state source: {source.get('url', '')}",
        "state_coverage": [state_name],
        "district_coverage": _state_district_coverage(state_name),
        "beneficiary_tags": tags,
        "expiry_date": "",
        "required_documents": [
            "Identity proof",
            "Address proof",
            "Scheme-specific documents listed on the official page",
        ],
        "where_to_apply": "Apply through the official linked source page.",
        "offline_location": f"District Collector Office, {state_name}",
        "helpline": "",
        "effort_level": "medium",
    }
