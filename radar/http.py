from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urljoin, urldefrag, urlparse
import requests
from bs4 import BeautifulSoup

USER_AGENT = "RenewableEnergyPhDRadar/3.0 (+https://github.com/aminhosseini7/renewable-energy-phd-radar)"

@dataclass
class Page:
    url: str
    title: str
    text: str
    soup: BeautifulSoup
    status_code: int

def clean_url(url: str) -> str:
    url, _ = urldefrag(url.strip())
    return url

def allowed_domain(url: str, domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in domains)

def absolutize(base: str, href: str) -> str:
    return clean_url(urljoin(base, href))

def fetch(url: str, timeout: int = 7) -> Page | None:
    try:
        r = requests.get(url, timeout=(5, timeout), allow_redirects=True, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if "html" not in ctype and "xhtml" not in ctype:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "form"]):
            tag.decompose()
        title = ""
        if soup.find("h1"):
            title = " ".join(soup.find("h1").stripped_strings)
        elif soup.title:
            title = " ".join(soup.title.stripped_strings)
        text = " ".join(soup.stripped_strings)
        return Page(str(r.url), title[:500], text[:220000], soup, r.status_code)
    except Exception:
        return None
