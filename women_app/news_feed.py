import os
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

from django.core.cache import cache


PIB_RSS_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
PIB_SOURCE_NAME = "Press Information Bureau"
DEFAULT_NEWS_IMAGE = "https://static.pib.gov.in/WriteReadData/specificdocs/photo/2021/aug/ph202183101.png"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


NEWS_CACHE_SECONDS = _env_int("NEWS_CACHE_SECONDS", 60 * 30)
STALE_NEWS_CACHE_SECONDS = _env_int("STALE_NEWS_CACHE_SECONDS", 60 * 60 * 24)
NEWS_META_FETCH_LIMIT = max(0, _env_int("NEWS_META_FETCH_LIMIT", 3))

SCHEME_KEYWORDS = {
    "scheme": 8,
    "yojana": 8,
    "launch": 7,
    "launched": 7,
    "approval": 6,
    "approved": 6,
    "benefit": 5,
    "welfare": 5,
    "subsidy": 5,
    "scholarship": 5,
    "housing": 5,
    "pension": 5,
    "farmer": 4,
    "food": 4,
    "stipend": 4,
    "business": 4,
    "self-employment": 4,
    "राशन": 4,
    "पेंशन": 5,
    "योजना": 8,
    "स्कीम": 8,
    "मंजूरी": 6,
    "लॉन्च": 7,
    "किसान": 4,
    "आवास": 5,
    "खाद्य": 4,
    "रोजगार": 4,
    "उड़ान": 4,
}

SOCIAL_IMAGE_KEYWORDS = ("facebook", "linkedin", "whatsapp", "email", "twitter", "icon", "logo")


def _http_text(url: str) -> str:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=int(os.getenv("NEWS_FETCH_TIMEOUT_SECONDS", "3"))) as response:
        return response.read().decode("utf-8", "ignore")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _keyword_score(text: str) -> int:
    lowered = text.lower()
    return sum(weight for keyword, weight in SCHEME_KEYWORDS.items() if keyword.lower() in lowered)


def _pick_image(html: str) -> str:
    og_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
    candidates = [og_match.group(1)] if og_match else []
    candidates.extend(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I))
    fallback = DEFAULT_NEWS_IMAGE

    for raw_url in candidates:
        url = raw_url.strip().replace("https:/pib.gov.in", "https://pib.gov.in")
        if url.startswith("//"):
            url = f"https:{url}"
        if not url.startswith("http"):
            continue
        lowered = url.lower()
        if any(keyword in lowered for keyword in SOCIAL_IMAGE_KEYWORDS):
            continue
        if url == DEFAULT_NEWS_IMAGE:
            fallback = url
            continue
        return url
    return fallback


def _article_meta(url: str) -> Dict[str, str]:
    html = _http_text(url)
    summary_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.I)
    date_match = re.search(r'(\d{1,2}\s+[A-Z]{3}\s+\d{4})', html, re.I)
    return {
        "summary": _clean_text(summary_match.group(1)) if summary_match else "",
        "published_on": _clean_text(date_match.group(1)) if date_match else "",
        "image_url": _pick_image(html),
    }


def get_launch_news(limit: int = 6) -> List[Dict[str, str]]:
    cache_key = f"pib-launch-news:{limit}"
    stale_key = f"pib-launch-news:stale:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if os.getenv("NEWS_FETCH_ENABLED", "1").strip().lower() in {"0", "false", "no", "off"}:
        return cache.get(stale_key, [])

    try:
        feed_text = _http_text(PIB_RSS_URL)
        root = ET.fromstring(feed_text)
    except Exception:
        stale = cache.get(stale_key, [])
        cache.set(cache_key, stale, 60 * 5)
        return stale

    items = []
    for position, item in enumerate(root.findall("./channel/item")):
        title = _clean_text(item.findtext("title", default=""))
        url = _clean_text(item.findtext("link", default=""))
        feed_summary = _clean_text(item.findtext("description", default=""))
        score = _keyword_score(f"{title} {feed_summary}")
        if not title or not url or score <= 0:
            continue
        items.append({"title": title, "url": url, "score": score, "position": position, "feed_summary": feed_summary})

    results = []
    selected_items = items[: max(limit, 1)]
    for position, item in enumerate(selected_items):
        if position < NEWS_META_FETCH_LIMIT:
            try:
                meta = _article_meta(item["url"])
            except Exception:
                meta = {
                    "summary": "",
                    "published_on": "",
                    "image_url": DEFAULT_NEWS_IMAGE,
                }
        else:
            meta = {
                "summary": "",
                "published_on": "",
                "image_url": DEFAULT_NEWS_IMAGE,
            }
        results.append(
            {
                "title": item["title"],
                "url": item["url"],
                "summary": meta["summary"] or item["feed_summary"] or "Open the official government release to read the latest update.",
                "published_on": meta["published_on"],
                "image_url": meta["image_url"],
                "source_name": PIB_SOURCE_NAME,
                "score": item["score"],
                "position": item["position"],
            }
        )

    trimmed = results[:limit]
    cache.set(cache_key, trimmed, NEWS_CACHE_SECONDS)
    cache.set(stale_key, trimmed, STALE_NEWS_CACHE_SECONDS)
    return trimmed
