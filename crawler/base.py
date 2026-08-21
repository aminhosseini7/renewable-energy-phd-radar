import requests
from bs4 import BeautifulSoup

def fetch(url):
    try:
        r=requests.get(
            url,
            timeout=20,
            headers={"User-Agent":"Renewable Energy PhD Radar"}
        )
        return BeautifulSoup(r.text,"html.parser").get_text(" ")
    except Exception:
        return ""
