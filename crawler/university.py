import yaml
from crawler.base import fetch

def sources():
    with open("config/universities.yaml",encoding="utf8") as f:
        return yaml.safe_load(f)["sources"]

def scan():
    results=[]

    for item in sources():
        text=fetch(item["url"])

        results.append({
            "university": item["name"],
            "country": item["country"],
            "url": item["url"],
            "text": text[:5000]
        })

    return results
