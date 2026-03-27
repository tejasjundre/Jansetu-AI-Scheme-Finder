import json
from functools import lru_cache
from pathlib import Path


_BASE_DIR = Path(__file__).resolve().parent
_DISTRICT_DATA_FILE = _BASE_DIR / "data" / "india_state_districts.json"

STATE_ALIASES = {
    "Andaman And Nicobar Islands": "Andaman and Nicobar Islands",
    "Jammu And Kashmir": "Jammu and Kashmir",
    "The Dadra And Nagar Haveli And Daman And Diu": "Dadra and Nagar Haveli and Daman and Diu",
}


def canonical_state_name(value: str) -> str:
    cleaned = str(value or "").strip()
    return STATE_ALIASES.get(cleaned, cleaned)


@lru_cache(maxsize=1)
def get_state_district_map():
    if not _DISTRICT_DATA_FILE.exists():
        return {}

    with _DISTRICT_DATA_FILE.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    return {
        canonical_state_name(state): [district for district in districts if district]
        for state, districts in payload.items()
    }


def get_state_choices(include_all_india: bool = True):
    items = [(state, state) for state in get_state_district_map().keys()]
    if include_all_india:
        return [("All India", "All India"), *items]
    return items


def get_district_choices(state: str, placeholder: str):
    districts = get_state_district_map().get(canonical_state_name(state), [])
    return [("", placeholder), *[(district, district) for district in districts]]
