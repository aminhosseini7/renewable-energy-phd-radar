from __future__ import annotations
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def issue_exists(marker: str) -> bool:
    search = run(["gh", "issue", "list", "--state", "all", "--search", marker, "--json", "number"])
    if search.returncode != 0:
        return False
    try:
        return bool(json.loads(search.stdout or "[]"))
    except Exception:
        return False


def create_high_match_alerts(cfg: dict) -> int:
    acfg = cfg.get("alerts", {})
    if not acfg.get("enabled", True):
        print("High-match GitHub issue alerts disabled.")
        return 0
    changes_path = ROOT / "reports/changes.json"
    if not changes_path.exists():
        return 0
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    items = changes.get("new", []) if isinstance(changes, dict) else []
    threshold = int(acfg.get("minimum_priority", 84))
    min_fit = int(acfg.get("minimum_research_fit", 74))
    require_confirmed = bool(acfg.get("require_confirmed_funding", True))
    cap = int(acfg.get("max_issues_per_scan", 5))

    qualified = []
    for x in items:
        if x.get("status") == "expired":
            continue
        if int(x.get("strategic_score", 0)) < threshold or int(x.get("research_fit", 0)) < min_fit:
            continue
        if require_confirmed and x.get("funding") != "Confirmed":
            continue
        qualified.append(x)
    qualified.sort(key=lambda x: (-int(x.get("action_rank", 0)), -int(x.get("strategic_score", 0)), -int(x.get("research_fit", 0))))

    created = 0
    for x in qualified[:cap]:
        fp = x.get("fingerprint", "")
        marker = f"Radar-ID:{fp}"
        if issue_exists(marker):
            continue

        title = f"🔥 {x.get('strategic_score', 0)} · {x.get('next_action','Review')} · {x.get('country','')} · {x.get('title','PhD opportunity')}"
        if len(title) > 240:
            title = title[:237] + "..."
        reasons = "\n".join(f"- {r}" for r in x.get("fit_reasons", [])[:6]) or "- Strong Research-DNA match"
        frontier = ", ".join(str(t).replace("_", " ") for t in x.get("frontier_themes", [])[:3]) or "—"
        body = f"""A new high-priority fully funded PhD match was detected by the radar.

**Next action:** {x.get('next_action', 'Review')} — {x.get('action_reason','')}  
**Research fit:** {x.get('research_fit', 0)}/100  
**Paper 1:** {x.get('paper1_score', 0)}/100  
**Paper 2:** {x.get('paper2_score', 0)}/100  
**Next-paper potential:** {x.get('frontier_score', 0)}/100 ({frontier})  
**Priority:** {x.get('strategic_score', 0)}/100  
**Data confidence:** {x.get('data_confidence', 0)}/100  
**Funding:** {x.get('funding', 'Unknown')} ({x.get('funding_model','')})  
**Country:** {x.get('country','')}  
**University:** {x.get('university','')}  
**Deadline:** {x.get('deadline') or 'not detected'}  
**Potential supervisor:** {x.get('potential_supervisor') or 'not identified'}

### Why it matches
{reasons}

### Official source
{x.get('url','')}

`{marker}`
"""
        res = run(["gh", "issue", "create", "--title", title, "--body", body])
        if res.returncode == 0:
            created += 1
        else:
            print("Issue creation failed:", res.stderr.strip())
    print(f"High-match alerts: {created} created from {len(qualified)} qualifying new matches.")
    return created


def create_weekly_digest(cfg: dict) -> int:
    dcfg = cfg.get("weekly_digest", {})
    if not dcfg.get("enabled", False):
        return 0
    now = datetime.now(timezone.utc)
    if now.weekday() != int(dcfg.get("weekday_utc", 6)):
        print("Not weekly-digest day; skipping digest.")
        return 0

    opportunities_path = ROOT / "reports/opportunities.json"
    if not opportunities_path.exists():
        return 0
    items = json.loads(opportunities_path.read_text(encoding="utf-8"))
    min_priority = int(dcfg.get("minimum_priority", 72))
    eligible_only = bool(dcfg.get("full_funding_eligible_only", True))
    top_n = int(dcfg.get("top_n", 10))
    xs = [
        x for x in items
        if x.get("status") != "expired"
        and int(x.get("strategic_score", 0)) >= min_priority
        and (not eligible_only or x.get("funding_eligible"))
    ]
    xs.sort(key=lambda x: (-int(x.get("action_rank", 0)), -int(x.get("strategic_score", 0)), -int(x.get("research_fit", 0))))
    xs = xs[:top_n]
    if not xs:
        print("Weekly digest has no qualifying opportunities.")
        return 0

    iso_year, iso_week, _ = now.isocalendar()
    marker = f"Weekly-Radar:{iso_year}-W{iso_week:02d}"
    if issue_exists(marker):
        print("Weekly digest already exists.")
        return 0

    rows = []
    for i, x in enumerate(xs, 1):
        deadline = x.get("deadline") or "—"
        rows.append(
            f"{i}. **{x.get('title','PhD opportunity')}** — {x.get('university','')} ({x.get('country','')})  \n"
            f"   Priority **{x.get('strategic_score',0)}** · Fit **{x.get('research_fit',0)}** · Frontier **{x.get('frontier_score',0)}** · "
            f"Funding **{x.get('funding','Unknown')}** · Deadline **{deadline}** · Action **{x.get('next_action','Review')}**  \n"
            f"   {x.get('url','')}"
        )
    body = f"""## Weekly PhD Radar digest

Top full-funding-eligible opportunities after Research-DNA, funding, supervisor, country, frontier and confidence scoring.

{"\n\n".join(rows)}

Open the dashboard for comparison, application-pack drafting and private tracking.

`{marker}`
"""
    title = f"📬 Weekly PhD Radar · {iso_year}-W{iso_week:02d} · Top {len(xs)}"
    res = run(["gh", "issue", "create", "--title", title, "--body", body])
    if res.returncode == 0:
        print("Weekly digest issue created.")
        return 1
    print("Weekly digest issue failed:", res.stderr.strip())
    return 0


def main() -> int:
    if not os.environ.get("GH_TOKEN"):
        print("GH_TOKEN not available; skipping GitHub issue alerts.")
        return 0
    cfg = yaml.safe_load((ROOT / "config/decision_weights.yaml").read_text(encoding="utf-8"))
    create_high_match_alerts(cfg)
    create_weekly_digest(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
