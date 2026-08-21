import yaml
from crawler.base import fetch

def collect():

    with open("config/sources.yaml",encoding="utf8") as f:
        sources=yaml.safe_load(f)["sources"]

    result=[]

    for s in sources:

        result.append({
            "source":s["name"],
            "country":s["country"],
            "url":s["url"],
            "text":fetch(s["url"])
        })

    return result
