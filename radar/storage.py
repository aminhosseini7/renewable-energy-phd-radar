from __future__ import annotations
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fingerprint(*parts: str) -> str:
    raw = "|".join((p or "").strip().lower() for p in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:20]


def read_json(path: str, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: str, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
