# Renewable Energy PhD Radar — Command Center

A free, GitHub-hosted PhD opportunity intelligence system built around Amin Hosseini's two-paper research trajectory:

1. Agricultural/bioenergy supply-chain network design under uncertainty.
2. Oilseed HEFA-SAF strategic planning with multi-objective and two-stage stochastic optimisation.

Target countries are intentionally fixed to:

- Netherlands
- Australia
- Canada
- Germany
- Sweden

The main dashboard is designed for **full-funding-first** PhD search and decision support.

## What this edition adds

### Command Center
The landing tab now shows:

- Apply-now queue
- Supervisor-contact queue
- Funding-verification queue
- Golden matches
- System/source health
- Research-frontier signals
- New/changed intelligence

### Next-paper / frontier score
Research Fit remains anchored to the two existing papers. A separate Frontier score identifies projects that could naturally extend that trajectory, including:

- multistage/adaptive stochastic optimisation
- joint demand/yield/price/policy uncertainty
- staged or modular investment
- multimodal rail/coastal-shipping logistics
- HEFA + FT + ATJ + PtL pathway portfolios
- hydrogen/energy-system integration
- harmonised LCA/carbon-policy analysis
- circular agri-bioeconomy
- Benders/decomposition for large-scale models

The Frontier score does **not** replace Research Fit; it rewards promising next-step novelty.

### Better crawler intelligence
The HTTP/crawler layer now includes:

- retry/backoff for transient 429/5xx failures
- canonical URL handling
- Schema.org `JobPosting` JSON-LD extraction
- structured title/description/salary/employment/deadline extraction when available
- remembered source-health scores and consecutive-failure warnings
- bounded parallel crawling

No paid API is used.

### Next-action engine
Every opportunity can be classified as:

- Apply now
- Contact supervisor
- Verify funding
- Deep review
- Monitor / contact
- Review
- Low priority

This uses research fit, funding certainty, supervisor fit, deadline, confidence and frontier potential.

### Golden matches
A Golden Match requires the combination of:

- confirmed/salaried funding
- high Research-DNA fit
- high decision priority
- strong extraction/data confidence
- active/non-expired status

### Application pack generator
Every opportunity has an **Application pack** button that creates locally in the browser:

- an email subject
- a supervisor/project email draft
- a research-fit paragraph for SOP/cover letter
- a compact decision brief
- a list of points that still need verification

Nothing is sent automatically and no external AI/API is called.

### Compare mode
Select up to three opportunities and compare:

- My Priority
- Research Fit
- Paper 1 / Paper 2 fit
- Next-paper potential
- funding
- supervisor fit
- country score
- data confidence
- deadline
- recommended next action

### Private tracker + backup
Application status and private notes are stored in browser `localStorage`, not the public repository.

You can export/import a private JSON backup containing:

- application tracker
- decision weights
- country weights
- theme preference

### GitHub alerts
The workflow can create:

- immediate GitHub Issues for exceptional new confirmed-funded matches
- one weekly digest Issue on Sunday when qualifying opportunities exist

## Daily workflow

`.github/workflows/radar.yml` performs:

1. checkout
2. Python setup
3. dependency installation
4. Research-DNA / decision-engine tests
5. JavaScript syntax validation
6. official-source scan
7. high-match + weekly Issue alerts
8. report/history commit
9. GitHub Pages deployment

Scheduled scan: **06:00 UTC daily**.

## Install / replace repository contents

Upload the **contents** of the ZIP to the repository root. Do not upload the ZIP itself.

GitHub Pages must use **GitHub Actions** as the deployment source.

Then either push to `main` or run manually:

`Actions → Daily PhD Radar Command Center → Run workflow`

## Main files

- `config/research_dna.yaml` — Paper 1, Paper 2, shared trajectory and next-paper frontier
- `config/countries.yaml` — five-country decision matrix
- `config/decision_weights.yaml` — default priority/country/alert weights
- `config/sources.yaml` — research and funding sources
- `config/supervisors.yaml` — curated supervisor watchlist
- `radar/http.py` — robust HTML + JSON-LD fetch layer
- `radar/scoring.py` — Research-DNA and frontier scoring
- `radar/decision.py` — priority/confidence/next-action logic
- `worker.py` — scan, state, history, command-center data and exports
- `index.html`, `app.js`, `style.css` — static dashboard

## Privacy

Repository reports are public if the GitHub repository is public. The application tracker, private notes, custom browser weights and generated application drafts are browser-local and are not committed by the workflow.
