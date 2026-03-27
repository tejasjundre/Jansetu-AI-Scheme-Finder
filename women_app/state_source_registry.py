import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from .location_data import canonical_state_name, get_state_district_map
from .state_portal_sync import load_state_portal_candidates, resolve_state_portal_url


_BASE_DIR = Path(__file__).resolve().parent
_STATE_SOURCE_FILE = _BASE_DIR / "data" / "state_verified_sources.json"


@lru_cache(maxsize=1)
def load_state_verified_sources():
    payload = []
    if _STATE_SOURCE_FILE.exists():
        with _STATE_SOURCE_FILE.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)

    normalized = []
    seen_keys = set()

    def add_source_entry(
        state_name: str,
        source_name: str,
        url: str,
        category: str = "other",
        tags=None,
        is_official: bool = True,
    ):
        state_name = canonical_state_name(state_name)
        source_name = str(source_name or "").strip()
        url = str(url or "").strip()
        if not state_name or not source_name or not url:
            return

        category_value = str(category or "other").strip().lower() or "other"
        tags_value = [str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()]
        key = (state_name.lower(), source_name.lower(), url.lower())
        if key in seen_keys:
            return
        seen_keys.add(key)

        normalized.append(
            {
                "state": state_name,
                "source_name": source_name,
                "url": url,
                "category": category_value,
                "tags": tags_value,
                "is_official": bool(is_official),
            }
        )

    for item in payload:
        add_source_entry(
            state_name=item.get("state", ""),
            source_name=item.get("source_name", ""),
            url=item.get("url", ""),
            category=item.get("category", "other"),
            tags=item.get("tags", []),
            is_official=item.get("is_official", True),
        )

    states_with_curated_sources = {entry["state"] for entry in normalized}
    for candidate in load_state_portal_candidates():
        state_name = canonical_state_name(candidate.get("state", ""))
        urls = [str(url).strip() for url in candidate.get("urls", []) if str(url).strip()]
        if not state_name or not urls:
            continue
        if state_name in states_with_curated_sources:
            continue
        add_source_entry(
            state_name=state_name,
            source_name=f"{state_name} Official Government Portal",
            url=urls[0],
            category="other",
            tags=["state portal", "citizen service", state_name.lower()],
            is_official=True,
        )

    return sorted(normalized, key=lambda entry: (entry["state"], entry["source_name"]))


def _district_coverage(state_name: str, max_districts: int = 450):
    districts = get_state_district_map().get(state_name, [])
    if len(districts) > max_districts:
        return []
    return districts


def build_source_registry_record(source, verify_url: bool = True, timeout_seconds: int = 8):
    candidate_url = source.get("url", "")
    is_official = bool(source.get("is_official", True))
    final_url, reachable = resolve_state_portal_url(
        [candidate_url],
        check_reachability=verify_url,
        timeout_seconds=timeout_seconds,
    )

    if is_official:
        verification_status = "verified" if reachable else "review_required"
        verification_note = (
            f"Verified against official state source {final_url}."
            if reachable
            else f"Official source configured but currently unreachable: {final_url}."
        )
    else:
        verification_status = "review_required"
        verification_note = (
            f"Reachable third-party discovery source: {final_url}. Verify final eligibility/apply links on official portals."
            if reachable
            else f"Third-party discovery source configured but currently unreachable: {final_url}."
        )

    state_name = source["state"]
    source_name = source["source_name"]
    tags = list(dict.fromkeys(source["tags"] + [state_name.lower(), "state source", "verified source"]))

    if is_official:
        description = (
            f"Official {state_name} source for state-specific schemes and benefit services. "
            "Use this source when searching beyond central catalog entries."
        )
    else:
        description = (
            "Additional discovery source for scheme leads. "
            "Always verify rules, dates, and apply URLs against official government portals."
        )

    eligibility_text = (
        "Eligibility depends on the selected scheme under this official state source."
        if is_official
        else "Treat this as discovery support. Confirm official eligibility on the government scheme page before applying."
    )

    return {
        "name": source_name,
        "slug": f"{state_name.lower().replace(' ', '-')}-{source_name.lower().replace(' ', '-')[:48]}",
        "category": source.get("category", "other"),
        "description": description,
        "eligibility": eligibility_text,
        "min_age": 0,
        "max_age": 120,
        "income_limit": 99999999,
        "gender": "any",
        "official_source_name": source_name,
        "url": final_url,
        "verification_status": verification_status,
        "last_verified_on": date.today().isoformat() if reachable else "",
        "verification_notes": verification_note,
        "state_coverage": [state_name],
        "district_coverage": _district_coverage(state_name),
        "beneficiary_tags": tags,
        "expiry_date": "",
        "required_documents": [
            "State identity and address proof",
            "Income or category certificates as needed",
            "Scheme-specific supporting documents",
        ],
        "where_to_apply": "Open this official state source and navigate to scheme or welfare sections for application links.",
        "offline_location": f"District Collector Office, {state_name}",
        "helpline": "",
        "effort_level": "medium",
        "source_type": "verified_state_registry",
    }
