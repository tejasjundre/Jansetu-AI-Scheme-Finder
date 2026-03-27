import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from .location_data import canonical_state_name


_BASE_DIR = Path(__file__).resolve().parent
_HELP_CENTER_FILE = _BASE_DIR / "data" / "help_centers.json"


def _normalize_text(value: str) -> str:
    return str(value or "").strip()


def _normalize_key(value: str) -> str:
    return _normalize_text(value).lower()


def _default_help_center(state: str, district: str):
    state_label = canonical_state_name(state or "All India")
    district_label = _normalize_text(district)
    office_label = district_label or state_label
    map_query = quote_plus(f"{office_label} district collector office")
    return {
        "state": state_label,
        "district": district_label,
        "office_name": f"{office_label} District Help Center",
        "address": f"District Collector Office, {office_label}",
        "phone": "1800-111-555",
        "hours": "Mon-Sat, 10:00 AM to 5:00 PM",
        "map_url": f"https://maps.google.com/?q={map_query}",
        "source_name": "Generated fallback directory",
        "last_verified_on": "",
        "is_fallback": True,
    }


@lru_cache(maxsize=1)
def _load_help_centers():
    if not _HELP_CENTER_FILE.exists():
        return []

    with _HELP_CENTER_FILE.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    centers = []
    for item in payload:
        state = canonical_state_name(item.get("state", ""))
        district = _normalize_text(item.get("district", ""))
        centers.append(
            {
                "state": state or "All India",
                "district": district,
                "office_name": _normalize_text(item.get("office_name")),
                "address": _normalize_text(item.get("address")),
                "phone": _normalize_text(item.get("phone")),
                "hours": _normalize_text(item.get("hours")),
                "map_url": _normalize_text(item.get("map_url")),
                "source_name": _normalize_text(item.get("source_name")),
                "last_verified_on": _normalize_text(item.get("last_verified_on")),
                "is_fallback": False,
            }
        )
    return centers


def find_help_centers(state: str = "", district: str = "", limit: int = 3):
    target_state = canonical_state_name(state or "")
    target_district = _normalize_text(district)
    state_key = _normalize_key(target_state)
    district_key = _normalize_key(target_district)

    exact = []
    state_matches = []
    national = []
    for center in _load_help_centers():
        center_state_key = _normalize_key(center["state"])
        center_district_key = _normalize_key(center["district"])
        if district_key and center_state_key == state_key and center_district_key == district_key:
            exact.append(center)
        elif center_state_key == state_key and not center_district_key:
            state_matches.append(center)
        elif center_state_key in {"all india", "india", "national", "all"}:
            national.append(center)

    results = (exact + state_matches + national)[: max(1, int(limit or 1))]
    if results:
        return results
    return [_default_help_center(state=target_state or "All India", district=target_district)]


def get_best_help_center(state: str = "", district: str = ""):
    return find_help_centers(state=state, district=district, limit=1)[0]
