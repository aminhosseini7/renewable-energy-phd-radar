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
