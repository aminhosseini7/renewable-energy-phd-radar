# Renewable Energy PhD Radar — Research-DNA Edition

This version is designed around **two papers** that define the candidate's academic identity:

1. **Energy-Aware Dual-Channel agricultural supply chain network design under uncertainty**
   - agricultural supply-chain network design
   - biomass / agricultural residues / biofuel
   - multi-period and multi-product optimisation
   - cost and energy-consumption objectives
   - scenario-based robust optimisation
   - augmented epsilon-constraint
   - Lagrangian relaxation

2. **Planning Australia’s oilseed-based HEFA-SAF supply chain: Cost–emission trade-offs and two-stage stochastic investment planning**
   - sustainable aviation fuel (SAF) and HEFA
   - Carinata, Camelina and Canola
   - spatial multi-period MILP
   - feedstock allocation, biorefinery location/capacity/investment timing and airport delivery
   - lifecycle emissions and cost–emission Pareto analysis
   - epsilon-constraint method
   - two-stage stochastic programming under demand uncertainty

## What is different from the earlier radar

The program no longer uses one flat keyword list. Every page is scored independently against:

- Paper 1 fit
- Paper 2 fit
- the shared research trajectory
- institution/location priority
- funding evidence

Generic renewable-energy pages and generic OR pages are capped unless they also contain the relevant domain/network signals. Irrelevant battery/materials/electrochemistry topics receive explicit penalties.

## Dashboard tabs

- **Opportunities** — live research projects and PhD vacancies
- **Supervisors** — monitored academics rescored against both papers
- **Funding routes** — scholarship/admission pages tracked separately
- **Research DNA** — the two-paper academic profile used by the engine
- **Scan status** — which sources were reachable and how many pages were scanned

## Run

Use GitHub Actions → **Daily PhD Radar + Deploy** → Run workflow.

The scheduled workflow scans daily, commits `reports/` and `data/history.json`, and deploys GitHub Pages in the same job so the dashboard does not depend on a second workflow being triggered by the bot commit.

## Files to edit if you want to expand later

- `config/research_dna.yaml` — scoring ontology derived from the two papers
- `config/sources.yaml` — official PhD/project/funding pages
- `config/supervisors.yaml` — professor watchlist
- `config/institutions.yaml` — location/institution priorities

No paid API key is required.
