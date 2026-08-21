# Renewable Energy PhD Funding Radar

Personal PhD funding monitoring system for:

- Biomass / bioenergy / biofuel supply chains
- Renewable energy supply chain network design
- Sustainable optimization
- Robust/stochastic optimization
- Agricultural residues and circular bioeconomy

## Setup

1. Install Python 3.11+
2. Create environment:

python -m venv venv

Windows:
venv\Scripts\activate

3. Install packages:

pip install -r requirements.txt

4. Run dashboard:

streamlit run app.py

5. Run crawler manually:

python worker.py

## Daily automation

Use Windows Task Scheduler or Linux cron to run worker.py every day.

## Future improvements

- Telegram alerts
- Playwright browser crawler
- Google Scholar/OpenAlex supervisor discovery
- Email notifications
