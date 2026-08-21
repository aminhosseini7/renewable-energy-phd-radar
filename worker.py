from radar.fetch import fetch
from radar.ranking import score
from radar.extract import funding,deadline,title
from database.history import init
import yaml,pandas as pd
from pathlib import Path

init()
Path("reports").mkdir(exist_ok=True)

with open("config/sources.yaml",encoding="utf8") as f:
    sources=yaml.safe_load(f)["sources"]

rows=[]

for s in sources:
    text=fetch(s["url"])
    sc,hits=score(text)
    rows.append({
        "source":s["name"],
        "country":s["country"],
        "title":title(text),
        "score":sc,
        "funding":funding(text),
        "deadline":deadline(text),
        "matches":", ".join(hits),
        "url":s["url"]
    })

pd.DataFrame(rows).sort_values("score",ascending=False).to_csv("reports/opportunities.csv",index=False)

print("PRO RADAR COMPLETE")
