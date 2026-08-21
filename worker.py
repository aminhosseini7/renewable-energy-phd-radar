from crawler.fetcher import fetch
from crawler.discovery import find_vacancy_links
from crawler.extractor import deadline,funding,title
from engine.ranking import rank
from database.storage import init
import yaml,pandas as pd
from pathlib import Path

init()
Path("reports").mkdir(exist_ok=True)

with open("config/sources.yaml",encoding="utf8") as f:
    sources=yaml.safe_load(f)["sources"]

rows=[]

for s in sources:
    text=fetch(s["url"])
    score,matches=rank(text)

    rows.append({
        "source":s["name"],
        "country":s["country"],
        "title":title(text),
        "score":score,
        "funding":funding(text),
        "deadline":deadline(text),
        "vacancy_signals":str(find_vacancy_links(text)[:5]),
        "matches":", ".join(matches),
        "url":s["url"]
    })

pd.DataFrame(rows).sort_values(
    "score",
    ascending=False
).to_csv(
    "reports/opportunities.csv",
    index=False
)

print("Radar v12 completed")
