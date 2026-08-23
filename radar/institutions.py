from __future__ import annotations


def infer_institution(text: str, fallback: dict, institutions: list[dict]) -> dict:
    low = text.lower()
    matches = []
    for inst in institutions:
        for alias in inst.get("aliases", []):
            a = alias.lower()
            if len(a) <= 3:
                import re
                found = re.search(r"\b" + re.escape(a) + r"\b", low) is not None
            else:
                found = a in low
            if found:
                matches.append((len(a), inst))
    if matches:
        return sorted(matches, key=lambda x: -x[0])[0][1]
    name = fallback.get("university", "")
    for inst in institutions:
        if inst["name"] == name:
            return inst
    return {
        "name": name or fallback.get("name", "Unknown institution"),
        "country": fallback.get("country", ""),
        "city": fallback.get("city", ""),
        "priority": 60,
    }
