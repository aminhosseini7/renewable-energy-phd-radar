from crawler.base import fetch
from crawler.extractor import funding,deadline
from engine.matcher import score
from database.db import init,exists
import yaml,pandas as pd
from datetime import datetime
from pathlib import Path

init()
Path('reports').mkdir(exist_ok=True)

with open('config/sources.yaml',encoding='utf8') as f:
    sources=yaml.safe_load(f)['sources']

rows=[]

for s in sources:

    text=fetch(s['url'])
    fit,hits=score(text)

    rows.append({
        'date':datetime.now().isoformat(),
        'source':s['name'],
        'country':s['country'],
        'score':fit,
        'funding':funding(text),
        'deadline':deadline(text),
        'matches':', '.join(hits),
        'url':s['url']
    })


pd.DataFrame(rows).sort_values(
    'score',
    ascending=False
).to_csv(
    'reports/opportunities.csv',
    index=False
)

print('v11 completed')
