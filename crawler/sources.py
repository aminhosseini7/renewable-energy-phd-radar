import yaml
from crawler.base import fetch

def collect():

    with open("config/sources.yaml",encoding="utf8") as f:
        sources=yaml.safe_load(f)["sources"]

    results=[]

    for s in sources:
        text=fetch(s["url"])

        results.append({
            "source":s["name"],
            "country":s["country"],
            "url":s["url"],
            "text":text
        })

    return results
