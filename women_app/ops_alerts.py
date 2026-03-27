import json
import os
from datetime import datetime
from urllib.request import Request, urlopen


def _alert_payload(title: str, body: str, level: str = "warning"):
    timestamp = datetime.utcnow().isoformat() + "Z"
    text = f"[{level.upper()}] {title}\n{body}\nTime: {timestamp}"
    return {"text": text, "level": level, "title": title, "body": body, "timestamp": timestamp}


def send_ops_alert(title: str, body: str, level: str = "warning") -> bool:
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False

    payload = json.dumps(_alert_payload(title=title, body=body, level=level)).encode("utf-8")
    request = Request(
        webhook_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "JanSetuOps/1.0"},
    )
    try:
        with urlopen(request, timeout=8):
            return True
    except Exception:
        return False
