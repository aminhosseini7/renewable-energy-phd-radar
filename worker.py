import json
from pathlib import Path
from datetime import datetime
from radar.scoring import score

Path('reports').mkdir(exist_ok=True)

samples=[
{
"title":"Sustainable Aviation Fuel supply chain optimization using MILP",
"university":"University of Queensland",
"country":"Australia"
},
{
"title":"Biomass renewable energy stochastic optimization",
"university":"German Research University",
"country":"Germany"
}
]

for x in samples:
    x['score']=score(x['title'])

Path('reports/opportunities.json').write_text(
json.dumps(samples,indent=2),
encoding='utf8'
)

print("Radar scan finished", datetime.now())