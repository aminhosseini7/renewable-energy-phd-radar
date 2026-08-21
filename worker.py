from crawler.sources import collect
from crawler.extractor import find_deadline, funding_level
from crawler.vacancy_parser import extract_title, extract_supervisor
from scoring import score
import pandas as pd
from pathlib import Path
from datetime import datetime

Path("reports").mkdir(exist_ok=True)

rows=[]

for item in collect():

    s, matches=score(item["text"])

    rows.append({
        "date":datetime.now().isoformat(),
        "source":item["source"],
        "country":item["country"],
        "title":extract_title(item["text"]),
        "supervisor":extract_supervisor(item["text"]),
        "research_score":s,
        "funding":funding_level(item["text"]),
        "deadline":find_deadline(item["text"]),
        "matched":",".join(matches),
        "url":item["url"]
    })


pd.DataFrame(rows).sort_values(
    ["research_score"],
    ascending=False
).to_csv(
    "reports/opportunities.csv",
    index=False
)

print("v7 completed")
