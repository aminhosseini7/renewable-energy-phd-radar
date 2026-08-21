from crawler.sources import collect
from crawler.extractor import funding_score, deadline
from scoring import research_score
import pandas as pd
from datetime import datetime
from pathlib import Path

Path("reports").mkdir(exist_ok=True)

rows=[]

for item in collect():

    r,matched=research_score(item["text"])
    f,fwords=funding_score(item["text"])

    rows.append({
        "date":datetime.now().isoformat(),
        "source":item["source"],
        "country":item["country"],
        "research_score":r,
        "funding_score":f,
        "funding_terms":",".join(fwords),
        "deadline":deadline(item["text"]),
        "matched":",".join(matched),
        "url":item["url"]
    })

pd.DataFrame(rows).sort_values(
    ["funding_score","research_score"],
    ascending=False
).to_csv(
    "reports/opportunities.csv",
    index=False
)

print("Radar v6 finished")
