from __future__ import annotations
from datetime import date
from math import sqrt
import re
from .scoring import research_score, contains


def weighted_score(values: dict[str, float], weights: dict[str, float]) -> int:
    total_w = sum(max(0.0, float(weights.get(k, 0))) for k in values)
    if total_w <= 0:
        return 0
    total = sum(
        max(0.0, float(weights.get(k, 0))) * max(0.0, min(100.0, float(v)))
        for k, v in values.items()
    )
    return max(0, min(100, round(total / total_w)))


def country_quality_score(country_cfg: dict, country_weights: dict) -> int:
    return weighted_score(country_cfg.get("decision_metrics", {}), country_weights)


def funding_component(level: str, model: str = "") -> int:
    if model in {"salaried", "guaranteed_package"}:
        return 100
    if level == "Confirmed":
        return 94
    if model == "competitive_full_funding" or level == "Competitive":
        return 66
    return 0


def days_until_deadline(deadline_iso: str, today: date | None = None) -> int | None:
    if not deadline_iso:
        return None
    try:
        d = date.fromisoformat(deadline_iso)
    except Exception:
        return None
    return (d - (today or date.today())).days


def deadline_component(deadline_iso: str, status: str, today: date | None = None) -> int:
    if status == "expired":
        return 0
    days = days_until_deadline(deadline_iso, today=today)
    if days is None:
        return 25
    if days < 0:
        return 0
    if days <= 7:
        return 100
    if days <= 14:
        return 92
    if days <= 30:
        return 78
    if days <= 60:
        return 58
    if days <= 120:
        return 40
    return 28


def freshness_component(is_new: bool, is_changed: bool) -> int:
    if is_new:
        return 100
    if is_changed:
        return 70
    return 10


def confidence_component(*, text: str, source: dict, institution: dict, funding: dict,
                         deadline_evidence: str, kind: str, stale: bool = False) -> int:
    """How trustworthy/actionable the extracted metadata is, not research quality."""
    score = 42
    if source.get("university"):
        score += 12
    elif institution.get("name"):
        score += 7
    if source.get("funding_model") in {"salaried", "guaranteed_package", "competitive_full_funding"}:
        score += 10
    if funding.get("evidence"):
        score += 10
    if funding.get("amounts"):
        score += 4
    if deadline_evidence:
        score += 8
    if kind in {"discovered_page", "structured_job"}:
        score += 8
    elif kind == "section":
        score += 3
    if len(text or "") > 1600:
        score += 5
    if stale:
        score -= 28
    return max(0, min(100, score))


def priority_score(components: dict[str, int], weights: dict[str, int]) -> int:
    return weighted_score(components, weights)


def _cosine(v1: list[float], v2: list[float]) -> float:
    num = sum(a * b for a, b in zip(v1, v2))
    den = sqrt(sum(a * a for a in v1)) * sqrt(sum(b * b for b in v2))
    return num / den if den else 0.0


def supervisor_alignment(opportunity_score: dict, opportunity_text: str, university: str,
                         supervisors: list[dict], dna: dict) -> dict:
    if not university:
        return {
            "score": 0,
            "name": "",
            "confirmed_on_page": False,
            "reason": "No institution-specific supervisor match available.",
        }

    opp_vec = [
        float(opportunity_score.get("paper1_score", 0)),
        float(opportunity_score.get("paper2_score", 0)),
        float(opportunity_score.get("trajectory_score", 0)),
        float(opportunity_score.get("frontier_score", 0)),
    ]
    opp_hits = {str(x).lower() for x in opportunity_score.get("keyword_hits", [])}
    best = None
    for s in supervisors:
        if s.get("university") != university:
            continue
        sup_score = research_score(s.get("focus", ""), dna)
        sup_vec = [
            sup_score["paper1_score"],
            sup_score["paper2_score"],
            sup_score["trajectory_score"],
            sup_score.get("frontier_score", 0),
        ]
        vector_sim = _cosine(opp_vec, sup_vec) * 100
        sup_hits = {str(x).lower() for x in sup_score.get("keyword_hits", [])}
        union = opp_hits | sup_hits
        overlap = (len(opp_hits & sup_hits) / len(union) * 100) if union else 0
        score = round(0.75 * vector_sim + 0.25 * overlap)
        confirmed = contains(opportunity_text, s.get("name", "")) if s.get("name") else False
        if confirmed:
            score = max(96, score)
        item = {
            "score": max(0, min(100, score)),
            "name": s.get("name", ""),
            "confirmed_on_page": confirmed,
            "reason": "Named on opportunity page" if confirmed else "Research-DNA alignment within the same institution",
        }
        if best is None or item["score"] > best["score"]:
            best = item
    return best or {
        "score": 0,
        "name": "",
        "confirmed_on_page": False,
        "reason": "No curated supervisor at this institution.",
    }


def explain_match(score: dict, funding: dict, supervisor: dict, deadline_iso: str, status: str) -> tuple[list[str], list[str], str]:
    p1, p2, tr = score.get("paper1_score", 0), score.get("paper2_score", 0), score.get("trajectory_score", 0)
    reasons: list[str] = []
    gaps: list[str] = []

    if p1 >= 75 and p2 >= 75:
        continuation = "Direct bridge across both papers"
        reasons.append("Connects both academic pillars: bioenergy/agricultural SCND and SAF/HEFA strategic planning.")
    elif p2 >= max(75, p1 + 8):
        continuation = "Strong continuation of Paper 2"
        reasons.append("Strong continuation of HEFA-SAF, spatial network design, lifecycle emissions or stochastic investment planning.")
    elif p1 >= 75:
        continuation = "Strong continuation of Paper 1"
        reasons.append("Strong continuation of agricultural/biomass supply-chain network design and optimisation under uncertainty.")
    elif tr >= 65:
        continuation = "Strong research-trajectory fit"
        reasons.append("Extends the shared operations-research trajectory across renewable-fuel supply chains.")
    else:
        continuation = "Adjacent research fit"

    dimensions = []
    for prefix, values in [
        ("Paper 1", score.get("paper1_dimensions", {})),
        ("Paper 2", score.get("paper2_dimensions", {})),
    ]:
        for name, val in values.items():
            if val >= 8:
                dimensions.append((val, f"{prefix} {name.replace('_', ' ')}"))
    dimensions.sort(reverse=True)
    if dimensions:
        reasons.append("Strongest dimensions: " + ", ".join(label for _, label in dimensions[:4]) + ".")

    if score.get("frontier_score", 0) >= 35:
        themes = [str(x).replace("_", " ") for x in score.get("frontier_themes", [])[:3]]
        if themes:
            reasons.append("Next-paper potential: " + ", ".join(themes) + ".")

    if funding.get("level") == "Confirmed":
        reasons.append("Funding evidence is confirmed/salaried on the source or guaranteed by the configured funding model.")
    elif funding.get("level") == "Competitive":
        gaps.append("Full funding is competitive rather than guaranteed; verify tuition coverage and living stipend before applying.")
    else:
        gaps.append("Full funding is not verified; keep this outside the main shortlist until evidence appears.")

    if supervisor.get("score", 0) >= 70:
        qualifier = "named on the page" if supervisor.get("confirmed_on_page") else "potential same-institution match"
        reasons.append(f"Supervisor alignment: {supervisor.get('name')} ({qualifier}).")
    else:
        gaps.append("No strong supervisor match is currently identified from the curated watchlist.")

    if status == "expired":
        gaps.append("Deadline has passed.")
    elif not deadline_iso:
        gaps.append("No reliable deadline was detected; check the official page manually.")

    return reasons[:7], gaps[:5], continuation


def next_action(*, research_fit: int, funding_level: str, funding_model: str, supervisor_score: int,
                deadline_iso: str, status: str, confidence: int, is_new: bool, frontier_score: int) -> dict:
    days = days_until_deadline(deadline_iso)
    if status == "expired":
        return {"action": "Archive", "rank": 0, "reason": "Deadline has passed."}

    confirmed = funding_model in {"salaried", "guaranteed_package"} or funding_level == "Confirmed"
    competitive = funding_model == "competitive_full_funding" or funding_level == "Competitive"

    if confirmed and research_fit >= 78 and confidence >= 65 and (days is None or days <= 60):
        urgency = " immediately" if days is not None and days <= 21 else ""
        return {"action": "Apply now", "rank": 100, "reason": f"High research fit + confirmed funding; prepare application{urgency}."}
    if research_fit >= 80 and supervisor_score >= 72 and competitive:
        return {"action": "Contact supervisor", "rank": 88, "reason": "Very strong fit with a potential supervisor; clarify project fit and scholarship path."}
    if research_fit >= 75 and funding_level == "Unknown":
        return {"action": "Verify funding", "rank": 76, "reason": "Research match is strong, but full funding is not yet verified."}
    if confirmed and research_fit >= 68 and frontier_score >= 35:
        return {"action": "Deep review", "rank": 72, "reason": "Funded and strategically novel; read the full project before deciding."}
    if research_fit >= 70 and supervisor_score >= 60:
        return {"action": "Monitor / contact", "rank": 62, "reason": "Promising research trajectory and supervisor alignment, but not yet an immediate application."}
    if is_new and research_fit >= 60:
        return {"action": "Review", "rank": 48, "reason": "New adjacent match; inspect before it is deprioritised."}
    return {"action": "Low priority", "rank": 20, "reason": "Keep for reference unless funding or fit evidence improves."}


NON_PHD_TITLE_TERMS = [
    "master thesis", "master's thesis", "masters thesis", "msc thesis",
    "bachelor thesis", "bachelor's thesis", "bsc thesis",
    "postdoc", "postdoctoral", "internship", "student assistant",
    "research fellow", "senior research fellow", "lecturer", "professor",
    "technician", "laboratory assistant",
]
DOCTORAL_TITLE_TERMS = ["phd", "doctorate", "doktorand", "promotion"]


def title_is_non_phd(title: str) -> bool:
    low = (title or "").lower()
    negative = any(t in low for t in NON_PHD_TITLE_TERMS)
    explicit_doctoral = (
        any(t in low for t in DOCTORAL_TITLE_TERMS)
        or re.search(r"\bdoctoral\s+(?:student|researcher|candidate)\b", low) is not None
    )
    return bool(negative and not explicit_doctoral)
