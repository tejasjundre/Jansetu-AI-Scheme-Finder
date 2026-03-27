import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .location_data import canonical_state_name, get_state_district_map


_BASE_DIR = Path(__file__).resolve().parent
_STATE_PORTAL_FILE = _BASE_DIR / "data" / "state_portal_candidates.json"

COMMON_TAGS = [
    "farmer",
    "student",
    "job seeker",
    "entrepreneur",
    "business",
    "senior citizen",
    "mother",
    "disability",
    "state portal",
]


@lru_cache(maxsize=1)
def load_state_portal_candidates():
    if not _STATE_PORTAL_FILE.exists():
        return []
    with _STATE_PORTAL_FILE.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    normalized = []
    for item in payload:
        state_name = canonical_state_name(item.get("state", ""))
        urls = [str(url).strip() for url in item.get("urls", []) if str(url).strip()]
        if not state_name or not urls:
            continue
        normalized.append({"state": state_name, "urls": urls})
    return normalized


def _probe_url(url: str, timeout_seconds: int = 8) -> bool:
    request = Request(url, headers={"User-Agent": "JanSetuSync/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200))
            return 200 <= status_code < 400
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False


def resolve_state_portal_url(urls, check_reachability: bool = True, timeout_seconds: int = 8):
    if not urls:
        return "", False
    if not check_reachability:
        return urls[0], True

    for url in urls:
        if _probe_url(url, timeout_seconds=timeout_seconds):
            return url, True
    return urls[0], False


def _district_coverage_for_state(state_name: str, max_districts: int = 450):
    districts = get_state_district_map().get(state_name, [])
    if len(districts) > max_districts:
        return []
    return districts


def build_state_portal_record(candidate, check_reachability: bool = True, timeout_seconds: int = 8):
    state_name = canonical_state_name(candidate.get("state", ""))
    urls = candidate.get("urls", [])
    portal_url, reachable = resolve_state_portal_url(
        urls=urls,
        check_reachability=check_reachability,
        timeout_seconds=timeout_seconds,
    )

    verification_status = "verified" if reachable else "review_required"
    verification_note = (
        "Official state government portal verified for access."
        if reachable
        else "State portal URL needs manual verification or may be temporarily unreachable."
    )

    return {
        "name": f"{state_name} Official Scheme Portal",
        "slug": f"{state_name.lower().replace(' ', '-').replace('&', 'and')}-official-scheme-portal",
        "category": "other",
        "description": (
            f"Official {state_name} state portal for citizen services and government scheme access. "
            "Use this when local state-specific options are needed beyond central listings."
        ),
        "eligibility": "Eligibility varies by scheme. Open the official state portal and select your target scheme category.",
        "min_age": 0,
        "max_age": 120,
        "income_limit": 99999999,
        "gender": "any",
        "official_source_name": f"{state_name} Government Portal",
        "url": portal_url,
        "verification_status": verification_status,
        "last_verified_on": date.today().isoformat() if reachable else "",
        "verification_notes": verification_note,
        "state_coverage": [state_name],
        "district_coverage": _district_coverage_for_state(state_name),
        "beneficiary_tags": COMMON_TAGS + [state_name.lower()],
        "expiry_date": "",
        "required_documents": [
            "Aadhaar or state identity proof",
            "Address proof",
            "Income or category certificates as required by selected scheme",
        ],
        "where_to_apply": "Open the official state portal and navigate to welfare, agriculture, education, employment, or social justice sections.",
        "offline_location": f"District Collector Office, {state_name}",
        "helpline": "",
        "effort_level": "medium",
    }


def iter_state_portal_records(check_reachability: bool = True, timeout_seconds: int = 8, limit: int = None):
    yielded = 0
    for candidate in load_state_portal_candidates():
        yield build_state_portal_record(
            candidate,
            check_reachability=check_reachability,
            timeout_seconds=timeout_seconds,
        )
        yielded += 1
        if limit and yielded >= limit:
            return
