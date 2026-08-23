from __future__ import annotations
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from pathlib import Path
import yaml

from radar.http import fetch
from radar.discovery import discover_links, heading_blocks, structured_candidates
from radar.scoring import research_score, signal_count
from radar.decision import (
    country_quality_score, funding_component, deadline_component, days_until_deadline,
    freshness_component, priority_score, supervisor_alignment, explain_match, title_is_non_phd,
    confidence_component, next_action, classify_opportunity, precision_gate, funding_certainty,
    actionability_score,
)
from radar.extract import extract_deadline, deadline_status, extract_funding, opening_signals, excerpt
from radar.storage import fingerprint, content_hash, read_json, write_json, now_iso
from radar.institutions import infer_institution

BASE = Path(__file__).resolve().parent
REPORTS = BASE / "reports"
DATA = BASE / "data"
REPORTS.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

with open(BASE / "config/research_dna.yaml", encoding="utf-8") as f:
    dna = yaml.safe_load(f)
with open(BASE / "config/sources.yaml", encoding="utf-8") as f:
    source_cfg = yaml.safe_load(f)
with open(BASE / "config/supervisors.yaml", encoding="utf-8") as f:
    supervisors_cfg = yaml.safe_load(f)["supervisors"]
with open(BASE / "config/institutions.yaml", encoding="utf-8") as f:
    institutions = yaml.safe_load(f)["institutions"]
with open(BASE / "config/countries.yaml", encoding="utf-8") as f:
    countries_cfg = yaml.safe_load(f)["countries"]
with open(BASE / "config/decision_weights.yaml", encoding="utf-8") as f:
    decision_cfg = yaml.safe_load(f)

target_countries = [c["name"] for c in countries_cfg]
country_priorities = {c["name"]: int(c.get("priority", 80)) for c in countries_cfg}
country_scores = {
    c["name"]: country_quality_score(c, decision_cfg.get("country_weights", {}))
    for c in countries_cfg
}
priority_weights = decision_cfg.get("priority_weights", {})

SCAN = now_iso()
previous = read_json(str(REPORTS / "opportunities.json"), [])
prev_by_fp = {x.get("fingerprint"): x for x in previous if x.get("fingerprint")}
history = read_json(str(DATA / "history.json"), {})
source_health_state = read_json(str(DATA / "source_health.json"), {})
supervisor_history = read_json(str(DATA / "supervisor_history.json"), {})

opportunities: dict[str, dict] = {}
funding_routes: dict[str, dict] = {}
source_status: list[dict] = []
page_cache: dict[str, object] = {}
opp_lock = Lock()
cache_lock = Lock()
filter_stats = Counter()

DOCTORAL_TERMS = [
    "PhD", "doctoral", "doctorate", "doctoral student", "doctoral researcher",
    "research associate / PhD", "Doktorand", "Promotion", "PhD student",
]


def funding_for_source(text: str, source: dict) -> dict:
    funding = extract_funding(text, dna)
    model = source.get("funding_model", "")
    evidence = list(funding.get("evidence", []))
    level = funding.get("level", "Unknown")
    if model in {"salaried", "guaranteed_package"}:
        if level != "Confirmed":
            level = "Confirmed"
            evidence.append("salaried/guaranteed PhD funding model")
    elif model == "competitive_full_funding" and level == "Unknown":
        level = "Competitive"
        evidence.append("competitive full-funding route")
    return {
        **funding,
        "level": level,
        "evidence": list(dict.fromkeys(evidence))[:8],
        "model": model or "unverified",
        "eligible": level in {"Confirmed", "Competitive"},
    }


def process_research_candidate(title: str, text: str, url: str, source: dict, kind: str, structured_meta: dict | None = None):
    if not text or len(text) < 80:
        return
    if title_is_non_phd(title):
        return

    score = research_score(text, dna)
    signals = signal_count(text, dna.get("opportunity_signals", []))
    if signals < int(source.get("min_signal", 1)):
        with opp_lock:
            filter_stats["insufficient_opportunity_signal"] += 1
        return
    if source.get("requires_doctoral_signal") and signal_count(text, DOCTORAL_TERMS) < 1:
        with opp_lock:
            filter_stats["missing_doctoral_signal"] += 1
        return
    if score["research_fit"] < 30 or max(score["paper1_score"], score["paper2_score"]) < 28:
        with opp_lock:
            filter_stats["low_research_fit"] += 1
        return

    gate = precision_gate(score, title, text, source.get("source_type", ""))
    if not gate["passed"]:
        with opp_lock:
            filter_stats["precision_gate"] += 1
        return

    inst = infer_institution(text, source, institutions)
    country = inst.get("country", source.get("country", ""))
    if country not in target_countries:
        return

    opportunity_type = classify_opportunity(source, kind)
    funding = funding_for_source(text, source)
    funding_check = funding_certainty(funding, source, text, opportunity_type)
    deadline, deadline_evidence = extract_deadline(text)
    fp = fingerprint(title or source["name"], url)
    old = prev_by_fp.get(fp, {})
    first_seen = old.get("first_seen") or history.get(fp, {}).get("first_seen") or SCAN
    new_hash = content_hash(text)
    changed = bool(old) and old.get("content_hash") != new_hash

    status_value = deadline_status(deadline)
    is_new = fp not in prev_by_fp and fp not in history
    is_changed = changed
    supervisor = supervisor_alignment(score, text, inst.get("name", ""), supervisors_cfg, dna)
    confidence = confidence_component(
        text=text, source=source, institution=inst, funding=funding,
        deadline_evidence=deadline_evidence, kind=kind, stale=False,
    )
    action = next_action(
        research_fit=int(score["research_fit"]), funding_level=funding["level"], funding_model=funding["model"],
        supervisor_score=int(supervisor.get("score", 0)), deadline_iso=deadline, status=status_value,
        confidence=confidence, is_new=is_new, frontier_score=int(score.get("frontier_score", 0)),
        opportunity_type=opportunity_type, funding_certainty_score=int(funding_check["score"]),
    )
    components = {
        "research_fit": int(score["research_fit"]),
        "frontier": int(score.get("frontier_score", 0)),
        "funding": int(funding_check["score"]),
        "supervisor": int(supervisor.get("score", 0)),
        "institution": int(inst.get("priority", 60)),
        "country": int(country_scores.get(country, 60)),
        "deadline": deadline_component(deadline, status_value),
        "confidence": confidence,
        "newness": freshness_component(is_new, is_changed),
    }
    reasons, watchouts, continuation = explain_match(score, funding, supervisor, deadline, status_value)

    rec = {
        "fingerprint": fp,
        "title": (title or source["name"]).strip()[:500],
        "source": source["name"],
        "university": inst.get("name", ""),
        "country": country,
        "city": inst.get("city", source.get("city", "")),
        "institution_priority": int(inst.get("priority", 60)),
        "country_priority": country_priorities.get(country, 70),
        "country_score": int(country_scores.get(country, 60)),
        "kind": kind,
        "opportunity_type": opportunity_type,
        "precision_tier": gate["tier"],
        "precision_reason": gate["reason"],
        "core_dimensions": gate["core_dimensions"],
        "url": url,
        **score,
        "funding": funding["level"],
        "funding_evidence": funding["evidence"],
        "funding_amounts": funding["amounts"],
        "funding_model": funding["model"],
        "funding_eligible": funding["eligible"],
        "funding_score": components["funding"],
        "funding_certainty": int(funding_check["score"]),
        "funding_verdict": funding_check["verdict"],
        "strict_funding_verified": bool(funding_check["strict_verified"]),
        "deadline": deadline,
        "deadline_evidence": deadline_evidence,
        "days_to_deadline": days_until_deadline(deadline),
        "deadline_score": components["deadline"],
        "status": status_value,
        "potential_supervisor": supervisor.get("name", ""),
        "supervisor_score": components["supervisor"],
        "supervisor_confirmed_on_page": bool(supervisor.get("confirmed_on_page")),
        "data_confidence": confidence,
        "priority_components": components,
        "fit_reasons": reasons,
        "watchouts": watchouts,
        "continuation_label": continuation,
        "next_action": action["action"],
        "action_rank": action["rank"],
        "action_reason": action["reason"],
        "excerpt": excerpt(text, score["keyword_hits"] or ["PhD"]),
        "first_seen": first_seen,
        "last_seen": SCAN,
        "is_new": is_new,
        "is_changed": is_changed,
        "stale": False,
        "content_hash": new_hash,
        "structured": kind == "structured_job",
        "date_posted": (structured_meta or {}).get("date_posted", ""),
        "employment_type": (structured_meta or {}).get("employment_type", ""),
    }
    rec["strategic_score"] = priority_score(components, priority_weights)
    rec["actionability_score"] = actionability_score(
        research_fit=int(rec["research_fit"]), funding_certainty_score=int(rec["funding_certainty"]),
        confidence=int(rec["data_confidence"]), opportunity_type=rec["opportunity_type"],
        deadline_score=int(rec["deadline_score"]), supervisor_score=int(rec["supervisor_score"]),
    )
    rec["golden_match"] = bool(
        rec["status"] != "expired"
        and rec["strict_funding_verified"]
        and rec["opportunity_type"] in {"Direct vacancy", "Funded project"}
        and rec["research_fit"] >= 78
        and rec["strategic_score"] >= 82
        and rec["data_confidence"] >= 62
    )

    with opp_lock:
        cur = opportunities.get(fp)
        if cur is None or (rec["strategic_score"], rec["research_fit"], rec["data_confidence"]) > (
            cur.get("strategic_score", 0), cur.get("research_fit", 0), cur.get("data_confidence", 0)
        ):
            opportunities[fp] = rec


def _process_page(page, source: dict, primary_kind: str, allow_page_candidate: bool = True):
    structured_count = 0
    for item in structured_candidates(page):
        process_research_candidate(item["title"], item["text"], item["url"], source, "structured_job", item)
        structured_count += 1
    if allow_page_candidate:
        process_research_candidate(page.title, page.text, page.url, source, primary_kind)
    return structured_count


def scan_research_source(source: dict):
    fetched = 0
    structured_count = 0
    seed = fetch(source["url"])
    if not seed:
        return {
            "source": source["name"], "url": source["url"], "country": source.get("country", ""),
            "ok": False, "pages_fetched": 0, "matches": 0, "structured_jobs": 0, "checked_at": SCAN,
        }
    fetched += 1
    with cache_lock:
        page_cache[seed.url] = seed
    structured_count += _process_page(
        seed, source, "source_page", allow_page_candidate=bool(source.get("treat_seed_as_candidate", True))
    )
    for block in heading_blocks(seed):
        process_research_candidate(block["title"], block["text"], block["url"], source, "section")

    if source.get("crawl_links", False):
        links = discover_links(
            seed, source.get("allowed_domains", []), source_cfg.get("discovery_terms", []),
            int(source.get("max_links", 25)),
            boost_terms=source.get("boost_terms", []), exclude_terms=source.get("exclude_terms", []),
        )
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(fetch, link["url"]): link for link in links}
            for fut in as_completed(futs):
                page = fut.result()
                if not page:
                    continue
                fetched += 1
                with cache_lock:
                    page_cache[page.url] = page
                structured_count += _process_page(page, source, "discovered_page")

    with opp_lock:
        source_matches = sum(1 for x in opportunities.values() if x.get("source") == source["name"])
    return {
        "source": source["name"], "url": source["url"], "country": source.get("country", ""),
        "ok": True, "pages_fetched": fetched, "matches": source_matches,
        "structured_jobs": structured_count, "checked_at": SCAN,
    }


def scan_funding_source(source: dict):
    page = fetch(source["url"])
    if not page:
        return {
            "source": source["name"], "url": source["url"], "country": source.get("country", ""),
            "ok": False, "pages_fetched": 0, "matches": 0, "structured_jobs": 0, "checked_at": SCAN,
        }
    with cache_lock:
        page_cache[page.url] = page
    inst = infer_institution(page.text, source, institutions)
    country = inst.get("country", source.get("country", ""))
    if country not in target_countries:
        return {
            "source": source["name"], "url": source["url"], "country": country,
            "ok": True, "pages_fetched": 1, "matches": 0, "structured_jobs": 0, "checked_at": SCAN,
        }
    funding = funding_for_source(page.text, source)
    deadline, evidence = extract_deadline(page.text)
    fp = fingerprint(source["name"], page.url)
    confidence = confidence_component(
        text=page.text, source=source, institution=inst, funding=funding,
        deadline_evidence=evidence, kind="funding_page", stale=False,
    )
    funding_routes[fp] = {
        "fingerprint": fp,
        "title": source["name"],
        "university": inst.get("name", source.get("university", "")),
        "country": country,
        "city": inst.get("city", source.get("city", "")),
        "priority": int(inst.get("priority", 60)),
        "country_priority": country_priorities.get(country, 70),
        "url": page.url,
        "funding": funding["level"],
        "funding_evidence": funding["evidence"],
        "funding_amounts": funding["amounts"],
        "funding_model": funding["model"],
        "funding_eligible": funding["eligible"],
        "deadline": deadline,
        "deadline_evidence": evidence,
        "status": deadline_status(deadline),
        "excerpt": excerpt(page.text, funding["evidence"] or ["scholarship"]),
        "checked_at": SCAN,
        "country_score": int(country_scores.get(country, 60)),
        "data_confidence": confidence,
        "score": round(
            0.40 * int(inst.get("priority", 60))
            + 0.18 * country_scores.get(country, 60)
            + 0.35 * funding_component(funding["level"], funding["model"])
            + 0.07 * confidence
        ),
    }
    return {
        "source": source["name"], "url": source["url"], "country": source.get("country", ""),
        "ok": True, "pages_fetched": 1, "matches": 1, "structured_jobs": len(page.structured_jobs), "checked_at": SCAN,
    }


with ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(scan_research_source, source) for source in source_cfg.get("sources", [])]
    for fut in as_completed(futs):
        source_status.append(fut.result())
with ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(scan_funding_source, source) for source in source_cfg.get("funding_sources", [])]
    for fut in as_completed(futs):
        source_status.append(fut.result())

# Source-health memory: broken dynamic pages should be visible instead of silently degrading the radar.
for st in source_status:
    key = fingerprint(st.get("source", ""), st.get("url", ""))
    prev = source_health_state.get(key, {})
    scans = int(prev.get("scans", 0)) + 1
    successes = int(prev.get("successes", 0)) + (1 if st.get("ok") else 0)
    failures = 0 if st.get("ok") else int(prev.get("consecutive_failures", 0)) + 1
    ratio = successes / scans if scans else 0
    health = round(max(5, min(100, 65 * ratio + (35 if st.get("ok") else max(0, 25 - 8 * failures)))))
    label = "healthy" if health >= 80 else ("watch" if health >= 55 else "degraded")
    st["health_score"] = health
    st["health_label"] = label
    st["consecutive_failures"] = failures
    source_health_state[key] = {
        "source": st.get("source", ""), "url": st.get("url", ""), "scans": scans,
        "successes": successes, "consecutive_failures": failures, "health_score": health,
        "last_ok": SCAN if st.get("ok") else prev.get("last_ok", ""),
        "last_checked": SCAN,
    }

# Carry missing prior opportunities for up to 7 scans so transient page failures do not erase useful records.
for fp, old in prev_by_fp.items():
    if fp in opportunities:
        continue
    misses = int(history.get(fp, {}).get("misses", 0)) + 1
    if misses <= 7 and old.get("status") != "expired":
        carry = dict(old)
        carry["is_new"] = False
        carry["is_changed"] = False
        carry["stale"] = True
        carry["misses"] = misses
        carry.setdefault("frontier_score", 0)
        carry.setdefault("frontier_themes", [])
        carry.setdefault("frontier_dimensions", {})
        carry["data_confidence"] = max(15, int(carry.get("data_confidence", 55)) - 25)
        components = dict(carry.get("priority_components", {}))
        components.setdefault("research_fit", int(carry.get("research_fit", 0)))
        components.setdefault("frontier", int(carry.get("frontier_score", 0)))
        components.setdefault("funding", int(carry.get("funding_score", 0)))
        components.setdefault("supervisor", int(carry.get("supervisor_score", 0)))
        components.setdefault("institution", int(carry.get("institution_priority", 60)))
        components.setdefault("country", int(carry.get("country_score", 60)))
        components.setdefault("deadline", int(carry.get("deadline_score", 25)))
        components["confidence"] = carry["data_confidence"]
        components["newness"] = 5
        carry["priority_components"] = components
        carry["strategic_score"] = priority_score(components, priority_weights)
        carry["golden_match"] = False
        carry["next_action"] = "Monitor"
        carry["action_rank"] = 35
        carry["action_reason"] = "This record was not rediscovered in the current scan; verify the source before acting."
        opportunities[fp] = carry

opp_list = list(opportunities.values())
opp_list.sort(key=lambda x: (
    x.get("status") == "expired",
    -int(x.get("action_rank", 0)),
    -int(x.get("strategic_score", 0)),
    -int(x.get("research_fit", 0)),
    x.get("deadline") or "9999-12-31",
))

# Supervisor radar with change detection.
def scan_supervisor(s):
    with cache_lock:
        cached = page_cache.get(s["url"])
    page = cached or fetch(s["url"])
    live_text = page.text if page else ""
    combined = live_text + " " + s.get("focus", "")
    score = research_score(combined, dna)
    inst = next((i for i in institutions if i["name"] == s["university"]), {"priority": 60})
    funding = extract_funding(live_text, dna) if live_text else {"level": "Unknown", "evidence": [], "amounts": []}
    country_priority = country_priorities.get(s.get("country", ""), 70)
    country_score_value = int(country_scores.get(s.get("country", ""), 60))
    signals = opening_signals(live_text, dna) if live_text else []
    shash = content_hash(live_text) if live_text else ""
    skey = fingerprint(s.get("name", ""), s.get("url", ""))
    old = supervisor_history.get(skey, {})
    changed = bool(old.get("content_hash")) and bool(shash) and old.get("content_hash") != shash
    opening_changed = changed and old.get("opening_signals", []) != signals
    confidence = 88 if page else 35
    sup_components = {
        "research_fit": int(score["research_fit"]),
        "frontier": int(score.get("frontier_score", 0)),
        "funding": funding_component(funding["level"], ""),
        "supervisor": 100,
        "institution": int(inst.get("priority", 60)),
        "country": country_score_value,
        "deadline": 25,
        "confidence": confidence,
        "newness": 70 if opening_changed else (40 if changed else 10),
    }
    rec = {
        **s, **score,
        "institution_priority": int(inst.get("priority", 60)),
        "country_priority": country_priority,
        "country_score": country_score_value,
        "opening_signals": signals,
        "funding": funding["level"],
        "funding_evidence": funding["evidence"],
        "excerpt": excerpt(live_text or s.get("focus", ""), score["keyword_hits"] or [s.get("focus", "")]),
        "page_ok": bool(page), "checked_at": SCAN,
        "data_confidence": confidence,
        "is_changed": changed,
        "opening_signal_changed": opening_changed,
        "priority_components": sup_components,
        "strategic_score": priority_score(sup_components, priority_weights),
    }
    supervisor_history[skey] = {
        "name": s.get("name", ""), "url": s.get("url", ""), "content_hash": shash,
        "opening_signals": signals, "last_checked": SCAN,
        "last_changed": SCAN if changed else old.get("last_changed", ""),
    }
    return rec


supervisor_report = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(scan_supervisor, s) for s in supervisors_cfg if s.get("country") in target_countries]
    for fut in as_completed(futs):
        supervisor_report.append(fut.result())
supervisor_report.sort(key=lambda x: (
    -int(bool(x.get("opening_signal_changed"))),
    -int(x.get("strategic_score", 0)),
    -int(x.get("research_fit", 0)),
))

# History / change tracking.
new_items, changed_items = [], []
for x in opp_list:
    fp = x["fingerprint"]
    misses = int(x.get("misses", 0)) if x.get("stale") else 0
    history[fp] = {
        "title": x["title"], "url": x["url"], "first_seen": x["first_seen"], "last_seen": x.get("last_seen", SCAN),
        "last_score": x["research_fit"], "last_status": x["status"], "content_hash": x.get("content_hash", ""), "misses": misses,
    }
    if x.get("is_new"):
        new_items.append(x)
    if x.get("is_changed"):
        changed_items.append(x)

active = [x for x in opp_list if x.get("status") != "expired"]
eligible_active = [x for x in active if x.get("funding_eligible")]
strict_funded_active = [x for x in active if x.get("strict_funding_verified")]
golden = [x for x in active if x.get("golden_match")]
action_counts = Counter(x.get("next_action", "Unknown") for x in active)
opportunity_type_counts = Counter(x.get("opportunity_type", "Opportunity lead") for x in active)
configured_research_universities = {s.get("university", "") for s in source_cfg.get("sources", []) if s.get("university")}
coverage_gaps = [
    {"university": i.get("name", ""), "country": i.get("country", ""), "priority": int(i.get("priority", 0))}
    for i in institutions
    if int(i.get("priority", 0)) >= 88 and i.get("name") not in configured_research_universities
]
coverage_gaps.sort(key=lambda x: (-x["priority"], x["country"], x["university"]))
frontier_counts = Counter()
for x in active:
    if int(x.get("research_fit", 0)) >= 60:
        for theme in x.get("frontier_themes", [])[:3]:
            frontier_counts[theme] += 1

source_warnings = [
    {k: st.get(k) for k in ["source", "country", "url", "health_score", "health_label", "consecutive_failures"]}
    for st in source_status if int(st.get("health_score", 0)) < 55
]
command_center = {
    "checked_at": SCAN,
    "golden_matches": sorted(golden, key=lambda x: (-x.get("strategic_score", 0), -x.get("research_fit", 0)))[:8],
    "action_counts": dict(action_counts),
    "frontier_theme_counts": dict(frontier_counts.most_common()),
    "top_frontier": sorted(active, key=lambda x: (-int(x.get("frontier_score", 0)), -int(x.get("research_fit", 0))))[:8],
    "recent_new": sorted(new_items, key=lambda x: -int(x.get("strategic_score", 0)))[:8],
    "recent_changed": sorted(changed_items, key=lambda x: -int(x.get("strategic_score", 0)))[:8],
    "source_warnings": source_warnings,
    "supervisor_changes": [x for x in supervisor_report if x.get("opening_signal_changed") or x.get("is_changed")][:8],
    "top_actionable": sorted(active, key=lambda x: (-int(x.get("actionability_score", 0)), -int(x.get("strategic_score", 0))))[:10],
    "opportunity_type_counts": dict(opportunity_type_counts),
    "precision_filter_counts": dict(filter_stats),
    "coverage_gaps": coverage_gaps[:12],
}

status = {
    "checked_at": SCAN,
    "sources_total": len(source_status),
    "sources_ok": sum(1 for s in source_status if s["ok"]),
    "pages_fetched": sum(int(s["pages_fetched"]) for s in source_status),
    "structured_jobs_found": sum(int(s.get("structured_jobs", 0)) for s in source_status),
    "opportunities": len(opp_list),
    "active_opportunities": len(active),
    "new_opportunities": len(new_items),
    "changed_opportunities": len(changed_items),
    "high_matches": sum(1 for x in active if x["research_fit"] >= 75),
    "frontier_matches": sum(1 for x in active if int(x.get("frontier_score", 0)) >= 40),
    "golden_matches": len(golden),
    "apply_now": action_counts.get("Apply now", 0),
    "full_funding_eligible": len(eligible_active),
    "confirmed_funding": sum(1 for x in active if x.get("funding") == "Confirmed"),
    "strict_funding_verified": len(strict_funded_active),
    "average_actionability": round(sum(int(x.get("actionability_score", 0)) for x in active) / len(active), 1) if active else 0,
    "opportunity_type_counts": dict(opportunity_type_counts),
    "precision_filter_counts": dict(filter_stats),
    "precision_rejects": int(filter_stats.get("precision_gate", 0)),
    "coverage_gaps": coverage_gaps[:12],
    "funding_routes": len(funding_routes),
    "target_countries": target_countries,
    "country_coverage": {c: {
        "sources": sum(1 for st in source_status if st.get("country") == c),
        "sources_ok": sum(1 for st in source_status if st.get("country") == c and st.get("ok")),
        "opportunities": sum(1 for x in active if x.get("country") == c),
        "funding_eligible": sum(1 for x in eligible_active if x.get("country") == c),
        "strict_funded": sum(1 for x in strict_funded_active if x.get("country") == c),
        "golden": sum(1 for x in golden if x.get("country") == c),
        "supervisors": sum(1 for x in supervisor_report if x.get("country") == c),
    } for c in target_countries},
    "country_profiles": [{**c, "country_score": int(country_scores.get(c["name"], 0))} for c in countries_cfg],
    "default_priority_weights": priority_weights,
    "country_metric_weights": decision_cfg.get("country_weights", {}),
    "alert_config": decision_cfg.get("alerts", {}),
    "weekly_digest_config": decision_cfg.get("weekly_digest", {}),
    "supervisors_monitored": len(supervisor_report),
    "supervisor_changes": sum(1 for x in supervisor_report if x.get("opening_signal_changed") or x.get("is_changed")),
    "source_warnings": len(source_warnings),
    "sources": sorted(source_status, key=lambda x: (target_countries.index(x.get("country")) if x.get("country") in target_countries else 99, -int(x.get("health_score", 0)))),
}

write_json(str(REPORTS / "opportunities.json"), opp_list)
write_json(str(REPORTS / "supervisors.json"), supervisor_report)
write_json(str(REPORTS / "funding_routes.json"), sorted(funding_routes.values(), key=lambda x: (-x["score"], x.get("deadline") or "9999-12-31")))
write_json(str(REPORTS / "changes.json"), {"new": new_items, "changed": changed_items, "checked_at": SCAN})
write_json(str(REPORTS / "command_center.json"), command_center)
write_json(str(REPORTS / "status.json"), status)
write_json(str(DATA / "history.json"), history)
write_json(str(DATA / "source_health.json"), source_health_state)
write_json(str(DATA / "supervisor_history.json"), supervisor_history)

fields = [
    "title", "university", "country", "city", "research_fit", "paper1_score", "paper2_score", "trajectory_score",
    "frontier_score", "frontier_themes", "strategic_score", "actionability_score", "data_confidence", "next_action", "action_rank", "golden_match",
    "opportunity_type", "precision_tier", "funding_score", "funding_certainty", "funding_verdict", "strict_funding_verified",
    "supervisor_score", "potential_supervisor", "institution_priority", "country_score", "funding", "funding_model",
    "funding_eligible", "deadline", "days_to_deadline", "status", "continuation_label", "keyword_hits", "url", "first_seen", "last_seen",
    "is_new", "is_changed", "stale", "structured",
]
with open(REPORTS / "opportunities.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for x in opp_list:
        row = {k: x.get(k, "") for k in fields}
        row["keyword_hits"] = "; ".join(x.get("keyword_hits", []))
        row["frontier_themes"] = "; ".join(x.get("frontier_themes", []))
        w.writerow(row)

print(
    f"Scan complete: {len(opp_list)} opportunities, {len(new_items)} new, {len(golden)} golden, "
    f"{action_counts.get('Apply now', 0)} apply-now, {len(supervisor_report)} supervisors, "
    f"{status['pages_fetched']} pages, {status['structured_jobs_found']} structured jobs."
)
