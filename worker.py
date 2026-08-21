from crawler.university import scan
from scoring.scorer import score
import pandas as pd
from pathlib import Path
from datetime import datetime

Path("reports").mkdir(exist_ok=True)

rows=[]

for item in scan():
    value, matches = score(item["text"])

    rows.append({
        "date": datetime.now().isoformat(),
        "university": item["university"],
        "country": item["country"],
        "fit_score": value,
        "matched_keywords": ", ".join(matches),
        "url": item["url"]
    })

pd.DataFrame(rows).sort_values(
    "fit_score",
    ascending=False
).to_csv(
    "reports/latest_matches.csv",
    index=False
)

print("Radar scan completed")
