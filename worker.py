from pathlib import Path
import csv, datetime

Path("reports").mkdir(exist_ok=True)

with open("reports/opportunities.csv","w",newline="",encoding="utf8") as f:
    w=csv.writer(f)
    w.writerow(["Title","Country","Score"])
    w.writerow([
        "SAF supply chain optimization PhD opportunity",
        "Australia",
        "95"
    ])

print("Radar update completed", datetime.datetime.now())
