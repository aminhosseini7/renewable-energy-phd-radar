from __future__ import annotations
import re


def contains(text: str, term: str) -> bool:
    low = (text or "").lower()
    t = (term or "").lower().strip()
    if not t:
        return False
    if len(t) <= 4 and t.replace("/", "").isalpha():
        return re.search(r"\b" + re.escape(t) + r"\b", low, re.I) is not None
    return t in low


def dimension_score(text: str, cfg: dict) -> tuple[int, list[str]]:
    raw, hits = 0, []
    for term, weight in cfg.get("terms", {}).items():
        if contains(text, str(term)):
            raw += int(weight)
            hits.append(str(term))
    return min(raw, int(cfg.get("max", 100))), hits


def score_paper(text: str, cfg: dict) -> dict:
    total, dims, hits_by_dim = 0, {}, {}
    for name, dcfg in cfg.get("dimensions", {}).items():
        val, hits = dimension_score(text, dcfg)
        dims[name] = val
        hits_by_dim[name] = hits
        total += val
    active = {k for k, v in dims.items() if v > 0}
    for syn in cfg.get("synergy", []):
        if all(x in active for x in syn.get("requires", [])):
            total += int(syn.get("bonus", 0))
    return {"score": min(100, total), "dimensions": dims, "hits": hits_by_dim}


def score_trajectory(text: str, cfg: dict) -> dict:
    total, dims, all_hits = 0, {}, []
    for name, dcfg in cfg.get("dimensions", {}).items():
        val, hits = dimension_score(text, dcfg)
        dims[name] = val
        total += val
        all_hits += hits
    return {"score": min(100, total), "dimensions": dims, "hits": list(dict.fromkeys(all_hits))}


def score_frontier(text: str, cfg: dict | None) -> dict:
    """Score how strongly a project extends the natural next-paper frontier.

    Frontier score is deliberately separate from Research Fit. A project can be an
    excellent direct continuation of the two papers without containing a novel
    extension, and vice versa.
    """
    cfg = cfg or {}
    total, dims, hits_by_dim, all_hits = 0, {}, {}, []
    for name, dcfg in cfg.get("dimensions", {}).items():
        val, hits = dimension_score(text, dcfg)
        dims[name] = val
        hits_by_dim[name] = hits
        total += val
        all_hits.extend(hits)
    active = {k for k, v in dims.items() if v > 0}
    for syn in cfg.get("synergy", []):
        if all(x in active for x in syn.get("requires", [])):
            total += int(syn.get("bonus", 0))
    score = max(0, min(100, total))
    strongest = sorted(dims.items(), key=lambda x: -x[1])
    strongest = [k for k, v in strongest if v > 0][:3]
    return {
        "frontier_score": score,
        "frontier_dimensions": dims,
        "frontier_hits": list(dict.fromkeys(all_hits))[:20],
        "frontier_themes": strongest,
    }


def research_score(text: str, dna: dict) -> dict:
    p1 = score_paper(text, dna["papers"]["paper1"])
    p2 = score_paper(text, dna["papers"]["paper2"])
    tr = score_trajectory(text, dna["trajectory"])
    frontier = score_frontier(text, dna.get("frontier"))

    penalty, penalty_hits = 0, []
    for term, weight in dna.get("negative_terms", {}).items():
        if contains(text, str(term)):
            penalty += int(weight)
            penalty_hits.append(str(term))

    hi, lo = max(p1["score"], p2["score"]), min(p1["score"], p2["score"])
    portfolio = round(0.55 * hi + 0.25 * lo + 0.20 * tr["score"] - penalty)
    portfolio = max(0, min(100, portfolio))

    # Guard against generic OR or generic renewable-energy pages becoming false high matches.
    domain_signal = max(p1["dimensions"].get("domain", 0), p2["dimensions"].get("domain", 0))
    network_signal = max(
        p1["dimensions"].get("network", 0),
        p2["dimensions"].get("network", 0),
        tr["dimensions"].get("supply_chain", 0),
    )
    method_signal = max(
        p1["dimensions"].get("optimization", 0),
        p2["dimensions"].get("investment_methods", 0),
        tr["dimensions"].get("quantitative_methods", 0),
    )
    if domain_signal < 7:
        portfolio = min(portfolio, 58)
    if network_signal < 6 and method_signal < 8:
        portfolio = min(portfolio, 52)

    all_hits = []
    for obj in (p1, p2):
        for vals in obj["hits"].values():
            all_hits += vals
    all_hits += tr["hits"]

    why = []
    for label, obj in [("Paper 1", p1), ("Paper 2", p2)]:
        strong = sorted(obj["dimensions"].items(), key=lambda x: -x[1])[:3]
        strong = [f"{k} {v}" for k, v in strong if v > 0]
        if strong:
            why.append(f"{label}: " + ", ".join(strong))

    return {
        "research_fit": portfolio,
        "paper1_score": p1["score"],
        "paper2_score": p2["score"],
        "trajectory_score": tr["score"],
        "paper1_dimensions": p1["dimensions"],
        "paper2_dimensions": p2["dimensions"],
        "trajectory_dimensions": tr["dimensions"],
        "keyword_hits": list(dict.fromkeys(all_hits))[:24],
        "penalty_hits": penalty_hits,
        "why_match": why,
        **frontier,
    }


def signal_count(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if contains(text, t))


def funding_score(level: str) -> int:
    return {"Confirmed": 100, "Competitive": 70, "Unknown": 20}.get(level, 20)


def strategic_score(research_fit: int, institution_priority: int, funding_level: str, country_priority: int = 80) -> int:
    """Legacy helper retained for compatibility with external scripts."""
    return max(0, min(100, round(
        0.74 * research_fit
        + 0.08 * institution_priority
        + 0.08 * country_priority
        + 0.10 * funding_score(funding_level)
    )))
