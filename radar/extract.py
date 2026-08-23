from __future__ import annotations
import re
from datetime import date
from dateutil import parser as dateparser
from .scoring import contains

DATE_PATTERNS = [
    r"(?:deadline|application deadline|closing date|applications? close|apply by|close date|closes|publish to date|bewerbungsfrist|ansök senast|sista ansökningsdag)\s*[:\-]?\s*(\d{4}-\d{1,2}-\d{1,2})",
    r"(?:deadline|application deadline|closing date|applications? close|apply by|close date|closes|publish to date|bewerbungsfrist|ansök senast|sista ansökningsdag)\s*[:\-]?\s*([0-3]?\d\s+[A-Za-zÀ-ÿ]{3,12}\s+[’']?\d{2,4})",
    r"(?:deadline|application deadline|closing date|applications? close|apply by|close date|closes|publish to date|bewerbungsfrist|ansök senast|sista ansökningsdag)\s*[:\-]?\s*([A-Za-zÀ-ÿ]{3,12}\s+[0-3]?\d(?:st|nd|rd|th)?[,]?\s+\d{4})",
    r"(?:deadline|application deadline|closing date|applications? close|apply by|close date|closes|publish to date|bewerbungsfrist|ansök senast|sista ansökningsdag)\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
]


def extract_deadline(text: str) -> tuple[str, str]:
    compact = " ".join(text.split())
    for pat in DATE_PATTERNS:
        m = re.search(pat, compact, re.I)
        if not m:
            continue
        raw = m.group(1).replace("’", "'")
        try:
            dt = dateparser.parse(raw, dayfirst=True, fuzzy=True)
            if dt:
                return dt.date().isoformat(), m.group(0)[:180]
        except Exception:
            pass
    return "", ""


def deadline_status(deadline: str) -> str:
    if not deadline:
        return "open_or_unknown"
    try:
        return "expired" if date.fromisoformat(deadline) < date.today() else "open"
    except Exception:
        return "open_or_unknown"


def extract_funding(text: str, dna: dict) -> dict:
    confirmed = [t for t in dna["funding"]["confirmed_terms"] if contains(text, t)]
    competitive = [t for t in dna["funding"]["competitive_terms"] if contains(text, t)]
    level = "Confirmed" if confirmed else ("Competitive" if competitive else "Unknown")
    money_patterns = [
        r"(?:AUD|CAD|USD|EUR|GBP|SEK|A\$|C\$|\$|€|£)\s?\d{1,3}(?:[ ,.]\d{3})*(?:\.\d+)?(?:\s*(?:per annum|per year|p\.a\.|pa|per month|monthly|annually|/month|/year))?",
        r"€\s?\d{1,4}(?:,\d{3})?\s?[–—-]\s?€?\s?\d{1,4}(?:,\d{3})?(?:\s*(?:gross)?\s*per month)?",
    ]
    amounts = []
    for pat in money_patterns:
        for m in re.finditer(pat, text, re.I):
            val = m.group(0).strip()
            if val not in amounts:
                amounts.append(val)
            if len(amounts) >= 5:
                break
    return {"level": level, "evidence": (confirmed or competitive)[:8], "amounts": amounts[:5]}


def opening_signals(text: str, dna: dict) -> list[str]:
    return [t for t in dna.get("supervisor_opening_signals", []) if contains(text, t)][:10]


def excerpt(text: str, hits: list[str], length: int = 440) -> str:
    compact = " ".join(text.split())
    low = compact.lower()
    pos = 0
    candidates = [low.find(h.lower()) for h in hits if h and low.find(h.lower()) >= 0]
    if candidates:
        pos = min(candidates)
    start = max(0, pos - 120)
    return compact[start:start+length].strip()
