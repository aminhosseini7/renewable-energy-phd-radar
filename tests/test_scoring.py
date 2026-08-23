import yaml, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from radar.scoring import research_score
from radar.extract import extract_deadline, extract_funding

with open(ROOT / "config/research_dna.yaml", encoding="utf-8") as f:
    dna = yaml.safe_load(f)

p1 = """
Funded PhD in agricultural biomass and biofuel supply chain network design. The project develops a multi-period MILP
and scenario-based robust optimization model under demand uncertainty, using augmented epsilon-constraint and
Lagrangian relaxation to minimize cost and energy consumption.
"""
s1 = research_score(p1, dna)
assert s1["paper1_score"] >= 80, s1
assert s1["research_fit"] >= 70, s1

p2 = """
PhD: sustainable aviation fuel (SAF) HEFA supply-chain network design using Carinata and Camelina. Spatial multi-period
MILP will optimize biorefinery location, airport delivery, lifecycle emissions, and two-stage stochastic refinery investment
under demand uncertainty using epsilon-constraint Pareto analysis.
"""
s2 = research_score(p2, dna)
assert s2["paper2_score"] >= 85, s2
assert s2["research_fit"] >= 75, s2

irrelevant = "PhD scholarship in lithium-ion battery materials, electrochemistry, cathode chemistry and solid-state batteries."
s3 = research_score(irrelevant, dna)
assert s3["research_fit"] < 30, s3

text = "Fully funded PhD. Stipend AUD 40,000 per annum. Applications close 23 September 2026."
d, _ = extract_deadline(text)
assert d == "2026-09-23", d
f = extract_funding(text, dna)
assert f["level"] == "Confirmed", f
print("All scoring tests passed")

# Five-country scope must remain exact: no accidental expansion beyond the user's target list.
with open(ROOT / "config/countries.yaml", encoding="utf-8") as f:
    countries = yaml.safe_load(f)["countries"]
expected_countries = ["Netherlands", "Australia", "Canada", "Germany", "Sweden"]
assert [c["name"] for c in countries] == expected_countries, countries

with open(ROOT / "config/sources.yaml", encoding="utf-8") as f:
    sources_cfg = yaml.safe_load(f)
research_countries = {s["country"] for s in sources_cfg["sources"]}
funding_countries = {s["country"] for s in sources_cfg["funding_sources"]}
assert research_countries == set(expected_countries), research_countries
assert funding_countries == set(expected_countries), funding_countries
assert any(s["country"] == "Germany" and s.get("funding_model") == "salaried" for s in sources_cfg["sources"])
assert any(s["country"] == "Sweden" and s.get("funding_model") == "salaried" for s in sources_cfg["sources"])

# Deadline and salaried-PhD funding language common on German/Swedish vacancy pages.
d2, _ = extract_deadline("Application deadline: 30 Sep 2026")
assert d2 == "2026-09-30", d2
d3, _ = extract_deadline("Bewerbungsfrist: 30.09.2026")
assert d3 == "2026-09-30", d3
f2 = extract_funding("Employed as a doctoral student with doctoral student salary SEK 33,000 per month.", dna)
assert f2["level"] == "Confirmed", f2
assert any("SEK" in x for x in f2["amounts"]), f2

print("Five-country full-funding configuration tests passed")

from datetime import date
from radar.decision import (
    country_quality_score, funding_component, deadline_component,
    priority_score, supervisor_alignment, title_is_non_phd
)

with open(ROOT / "config/decision_weights.yaml", encoding="utf-8") as f:
    decision = yaml.safe_load(f)
with open(ROOT / "config/countries.yaml", encoding="utf-8") as f:
    country_rows = yaml.safe_load(f)["countries"]

nl = next(c for c in country_rows if c["name"] == "Netherlands")
assert country_quality_score(nl, decision["country_weights"]) >= 80
assert funding_component("Confirmed", "salaried") == 100
assert funding_component("Competitive", "competitive_full_funding") < 80
assert deadline_component("2026-09-01", "open", today=date(2026,8,23)) >= 70
assert deadline_component("2026-08-20", "expired", today=date(2026,8,23)) == 0

components = {"research_fit":90,"funding":100,"supervisor":80,"institution":90,"country":85,"deadline":80,"newness":100}
p = priority_score(components, decision["priority_weights"])
assert p >= 88, p

assert title_is_non_phd("Postdoctoral researcher in sustainable aviation fuel")
assert not title_is_non_phd("PhD / doctoral researcher in sustainable aviation fuel")

with open(ROOT / "config/supervisors.yaml", encoding="utf-8") as f:
    sup_cfg = yaml.safe_load(f)["supervisors"]
align = supervisor_alignment(s2, p2, "University of Toronto", sup_cfg, dna)
assert align["score"] >= 50, align
assert align["name"], align

print("Decision-engine tests passed")

# Command Center / frontier intelligence.
frontier_text = """
Funded PhD in sustainable aviation fuel supply-chain planning using a multistage stochastic MILP with joint demand,
yield and price uncertainty. The project studies adaptive biorefinery capacity expansion, rail and coastal shipping,
and a technology portfolio combining HEFA, Fischer-Tropsch and power-to-liquid with harmonised LCA and carbon policy.
Benders decomposition will be developed for the large-scale model.
"""
s4 = research_score(frontier_text, dna)
assert s4["frontier_score"] >= 60, s4
assert "advanced_uncertainty" in s4["frontier_themes"], s4

from radar.decision import confidence_component, next_action
source = {"university":"Example University","funding_model":"salaried"}
inst = {"name":"Example University"}
fund = {"level":"Confirmed","model":"salaried","evidence":["salary"],"amounts":["EUR 3,000 per month"]}
conf = confidence_component(text=frontier_text*3, source=source, institution=inst, funding=fund,
                            deadline_evidence="Application deadline: 30 Sep 2026", kind="structured_job", stale=False)
assert conf >= 85, conf
act = next_action(research_fit=88, funding_level="Confirmed", funding_model="salaried", supervisor_score=75,
                  deadline_iso="2026-09-30", status="open", confidence=conf, is_new=True, frontier_score=s4["frontier_score"])
assert act["action"] == "Apply now", act

# JSON-LD JobPosting extraction should turn structured job metadata into a usable candidate.
from bs4 import BeautifulSoup
from radar.http import _extract_structured_jobs
html = '''<html><head><script type="application/ld+json">{
"@context":"https://schema.org","@type":"JobPosting","title":"PhD in SAF stochastic supply chains",
"description":"Fully funded doctoral position using HEFA and MILP.","validThrough":"2026-10-15",
"employmentType":"FULL_TIME","hiringOrganization":{"name":"Example University"},
"baseSalary":{"currency":"EUR","value":3500},"url":"https://example.org/jobs/123"}</script></head><body></body></html>'''
jobs = _extract_structured_jobs(BeautifulSoup(html,"html.parser"), "https://example.org/jobs")
assert len(jobs) == 1, jobs
assert jobs[0]["title"].startswith("PhD in SAF"), jobs
assert "Application deadline: 2026-10-15" in jobs[0]["text"], jobs

print("Command Center intelligence tests passed")
iso_deadline, _ = extract_deadline("Application deadline: 2026-10-15")
assert iso_deadline == "2026-10-15", iso_deadline
