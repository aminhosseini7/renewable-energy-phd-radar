# Renewable Energy PhD Radar v3

A free monitoring system for funded PhD opportunities in:

- Biomass / bioenergy / biofuel supply chains
- Renewable energy supply-chain network design
- Sustainable optimization
- Robust and stochastic optimization
- Agricultural residues and circular bioeconomy

## Features

- Daily automated scan using GitHub Actions
- Configurable university sources
- Research-fit scoring
- Funding signal detection
- SQLite storage
- Streamlit dashboard
- CSV reports

No paid API is required.

## Local run

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
python worker.py
streamlit run app.py
```

## GitHub Actions

After pushing to GitHub:

Repository -> Actions -> enable workflow.

The radar runs daily and updates reports/latest_matches.csv.
