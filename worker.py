from __future__ import annotations
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from pathlib import Path
from datetime import datetime, timezone
import yaml

from radar.http import fetch
from radar.discovery import discover_links, heading_blocks
from radar.scoring import research_score, signal_count, strategic_score, funding_score
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

SCAN = now_iso()
previous = read_json(str(REPORTS / "opportunities.json"), [])
prev_by_fp = {x.get("fingerprint"): x for x in previous if x.get("fingerprint")}
history = read_json(str(DATA / "history.json"), {})

opportunities: dict[str, dict] = {}
funding_routes: dict[str, dict] = {}
source_status = []
page_cache = {}
opp_lock = Lock()
cache_lock = Lock()


def process_research_candidate(title: str, text: str, url: str, source: dict, kind: str):
    if not text or len(text) < 80:
        return
    score = research_score(text, dna)
    signals = signal_count(text, dna.get("opportunity_signals", []))
    if signals < int(source.get("min_signal", 1)):
        return
    if score["research_fit"] < 30 or max(score["paper1_score"], score["paper2_score"]) < 28:
        return

    inst = infer_institution(text, source, institutions)
    funding = extract_funding(text, dna)
    deadline, deadline_evidence = extract_deadline(text)
    fp = fingerprint(title or source["name"], url)
    old = prev_by_fp.get(fp, {})
    first_seen = old.get("first_seen") or history.get(fp, {}).get("first_seen") or SCAN
    changed = bool(old) and old.get("content_hash") != content_hash(text)

    rec = {
        "fingerprint": fp,
        "title": (title or source["name"]).strip()[:500],
        "source": source["name"],
        "university": inst.get("name", ""),
        "country": inst.get("country", source.get("country", "")),
        "city": inst.get("city", source.get("city", "")),
        "institution_priority": int(inst.get("priority", 60)),
        "kind": kind,
        "url": url,
        **score,
        "funding": funding["level"],
        "funding_evidence": funding["evidence"],
        "funding_amounts": funding["amounts"],
        "deadline": deadline,
        "deadline_evidence": deadline_evidence,
        "status": deadline_status(deadline),
        "excerpt": excerpt(text, score["keyword_hits"] or ["PhD"]),
        "first_seen": first_seen,
        "last_seen": SCAN,
        "is_new": fp not in prev_by_fp and fp not in history,
        "is_changed": changed,
        "stale": False,
        "content_hash": content_hash(text),
    }
    rec["strategic_score"] = strategic_score(rec["research_fit"], rec["institution_priority"], rec["funding"])
    with opp_lock:
        cur = opportunities.get(fp)
        if cur is None or (rec["strategic_score"], rec["research_fit"]) > (cur["strategic_score"], cur["research_fit"]):
            opportunities[fp] = rec


def scan_research_source(source: dict):
    before = len(opportunities)
    fetched = 0
    seed = fetch(source["url"])
    if not seed:
        return {"source": source["name"], "url": source["url"], "country": source.get("country", ""), "ok": False, "pages_fetched": 0, "matches": 0, "checked_at": SCAN}
    fetched += 1
    with cache_lock:
        page_cache[seed.url] = seed
    # Seed page and meaningful blocks are both evaluated.
    process_research_candidate(seed.title, seed.text, seed.url, source, "source_page")
    for block in heading_blocks(seed):
        process_research_candidate(block["title"], block["text"], block["url"], source, "section")

    if source.get("crawl_links", False):
        links = discover_links(seed, source.get("allowed_domains", []), source_cfg.get("discovery_terms", []), int(source.get("max_links", 25)))
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(fetch, link["url"]): link for link in links}
            for fut in as_completed(futs):
                page = fut.result()
                if not page:
                    continue
                fetched += 1
                with cache_lock:
                    page_cache[page.url] = page
                process_research_candidate(page.title or futs[fut]["anchor"], page.text, page.url, source, "discovered_page")
    return {"source": source["name"], "url": source["url"], "country": source.get("country", ""), "ok": True, "pages_fetched": fetched, "matches": len(opportunities)-before, "checked_at": SCAN}


def scan_funding_source(source: dict):
    page = fetch(source["url"])
    if not page:
        return {"source": source["name"], "url": source["url"], "country": source.get("country", ""), "ok": False, "pages_fetched": 0, "matches": 0, "checked_at": SCAN}
    with cache_lock:
        page_cache[page.url] = page
    inst = infer_institution(page.text, source, institutions)
    funding = extract_funding(page.text, dna)
    deadline, evidence = extract_deadline(page.text)
    fp = fingerprint(source["name"], page.url)
    funding_routes[fp] = {
        "fingerprint": fp,
        "title": source["name"],
        "university": inst.get("name", source.get("university", "")),
        "country": inst.get("country", source.get("country", "")),
        "city": inst.get("city", source.get("city", "")),
        "priority": int(inst.get("priority", 60)),
        "url": page.url,
        "funding": funding["level"],
        "funding_evidence": funding["evidence"],
        "funding_amounts": funding["amounts"],
        "deadline": deadline,
        "deadline_evidence": evidence,
        "status": deadline_status(deadline),
        "excerpt": excerpt(page.text, funding["evidence"] or ["scholarship"]),
        "checked_at": SCAN,
        "score": round(0.65*int(inst.get("priority",60)) + 0.35*funding_score(funding["level"])),
    }
    return {"source": source["name"], "url": source["url"], "country": source.get("country", ""), "ok": True, "pages_fetched": 1, "matches": 1, "checked_at": SCAN}


with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(scan_research_source, source) for source in source_cfg.get("sources", [])]
    for fut in as_completed(futs):
        source_status.append(fut.result())
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(scan_funding_source, source) for source in source_cfg.get("funding_sources", [])]
    for fut in as_completed(futs):
        source_status.append(fut.result())

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
        opportunities[fp] = carry

opp_list = list(opportunities.values())
opp_list.sort(key=lambda x: (x.get("status") == "expired", -int(x.get("strategic_score",0)), -int(x.get("research_fit",0)), x.get("deadline") or "9999-12-31"))

# Supervisor radar: score live profile text plus curated focus, while keeping page availability explicit.
def scan_supervisor(s):
    with cache_lock:
        cached = page_cache.get(s["url"])
    page = cached or fetch(s["url"])
    live_text = page.text if page else ""
    combined = live_text + " " + s.get("focus", "")
    score = research_score(combined, dna)
    inst = next((i for i in institutions if i["name"] == s["university"]), {"priority":60})
    funding = extract_funding(live_text, dna) if live_text else {"level":"Unknown","evidence":[],"amounts":[]}
    return {
        **s, **score,
        "institution_priority": int(inst.get("priority",60)),
        "opening_signals": opening_signals(live_text, dna) if live_text else [],
        "funding": funding["level"],
        "funding_evidence": funding["evidence"],
        "excerpt": excerpt(live_text or s.get("focus",""), score["keyword_hits"] or [s.get("focus","")]),
        "page_ok": bool(page), "checked_at": SCAN,
        "strategic_score": strategic_score(score["research_fit"], int(inst.get("priority",60)), funding["level"]),
    }

supervisor_report = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(scan_supervisor, s) for s in supervisors_cfg]
    for fut in as_completed(futs):
        supervisor_report.append(fut.result())
supervisor_report.sort(key=lambda x: (-x["strategic_score"], -x["research_fit"]))

# History / change tracking
new_items, changed_items = [], []
for x in opp_list:
    fp = x["fingerprint"]
    misses = int(x.get("misses",0)) if x.get("stale") else 0
    history[fp] = {
        "title": x["title"], "url": x["url"], "first_seen": x["first_seen"], "last_seen": x.get("last_seen", SCAN),
        "last_score": x["research_fit"], "last_status": x["status"], "content_hash": x.get("content_hash", ""), "misses": misses,
    }
    if x.get("is_new"):
        new_items.append(x)
    if x.get("is_changed"):
        changed_items.append(x)

status = {
    "checked_at": SCAN,
    "sources_total": len(source_status),
    "sources_ok": sum(1 for s in source_status if s["ok"]),
    "pages_fetched": sum(int(s["pages_fetched"]) for s in source_status),
    "opportunities": len(opp_list),
    "active_opportunities": sum(1 for x in opp_list if x["status"] != "expired"),
    "new_opportunities": len(new_items),
    "changed_opportunities": len(changed_items),
    "high_matches": sum(1 for x in opp_list if x["research_fit"] >= 75 and x["status"] != "expired"),
    "funding_routes": len(funding_routes),
    "supervisors_monitored": len(supervisor_report),
    "sources": source_status,
}

write_json(str(REPORTS / "opportunities.json"), opp_list)
write_json(str(REPORTS / "supervisors.json"), supervisor_report)
write_json(str(REPORTS / "funding_routes.json"), sorted(funding_routes.values(), key=lambda x: (-x["score"], x.get("deadline") or "9999-12-31")))
write_json(str(REPORTS / "changes.json"), {"new": new_items, "changed": changed_items, "checked_at": SCAN})
write_json(str(REPORTS / "status.json"), status)
write_json(str(DATA / "history.json"), history)

fields = ["title","university","country","city","research_fit","paper1_score","paper2_score","trajectory_score","strategic_score","funding","deadline","status","keyword_hits","url","first_seen","last_seen","is_new","is_changed","stale"]
with open(REPORTS / "opportunities.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for x in opp_list:
        row = {k: x.get(k, "") for k in fields}
        row["keyword_hits"] = "; ".join(x.get("keyword_hits", []))
        w.writerow(row)

print(f"Scan complete: {len(opp_list)} opportunities, {len(new_items)} new, {len(supervisor_report)} supervisors, {status['pages_fetched']} pages fetched.")
