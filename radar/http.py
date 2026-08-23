from __future__ import annotations
from dataclasses import dataclass, field
from urllib.parse import urljoin, urldefrag, urlparse
import json
import time
import requests
from bs4 import BeautifulSoup

USER_AGENT = "RenewableEnergyPhDRadar/5.0 (+https://github.com/aminhosseini7/renewable-energy-phd-radar)"

@dataclass
class Page:
    url: str
    title: str
    text: str
    soup: BeautifulSoup
    status_code: int
    structured_jobs: list[dict] = field(default_factory=list)


def clean_url(url: str) -> str:
    url, _ = urldefrag((url or "").strip())
    return url


def allowed_domain(url: str, domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in domains)


def absolutize(base: str, href: str) -> str:
    return clean_url(urljoin(base, href))


def _plain_html(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return " ".join(BeautifulSoup(str(value), "html.parser").stripped_strings)


def _walk_jsonld(obj):
    if isinstance(obj, list):
        for item in obj:
            yield from _walk_jsonld(item)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            yield from _walk_jsonld(obj["@graph"])
        yield obj


def _extract_structured_jobs(soup: BeautifulSoup, base_url: str) -> list[dict]:
    out = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for obj in _walk_jsonld(data):
            typ = obj.get("@type", "") if isinstance(obj, dict) else ""
            types = typ if isinstance(typ, list) else [typ]
            if not any(str(t).lower() == "jobposting" for t in types):
                continue
            title = _plain_html(obj.get("title") or obj.get("name"))
            desc = _plain_html(obj.get("description"))
            org = obj.get("hiringOrganization") or {}
            org_name = _plain_html(org.get("name") if isinstance(org, dict) else org)
            location = _plain_html(obj.get("jobLocation"))
            salary = _plain_html(obj.get("baseSalary"))
            emp = _plain_html(obj.get("employmentType"))
            valid = _plain_html(obj.get("validThrough"))
            posted = _plain_html(obj.get("datePosted"))
            direct = obj.get("url") or obj.get("sameAs") or base_url
            if isinstance(direct, list):
                direct = direct[0] if direct else base_url
            url = absolutize(base_url, str(direct))
            text = " ".join(x for x in [title, desc, org_name, location, salary, emp, posted, f"Application deadline: {valid}" if valid else ""] if x)
            out.append({
                "title": title[:500] or "Structured job posting",
                "text": text[:220000],
                "url": url,
                "valid_through": valid,
                "date_posted": posted,
                "organization": org_name,
                "location": location,
                "salary": salary,
                "employment_type": emp,
            })
    # De-duplicate repeated JSON-LD blocks.
    uniq = {}
    for item in out:
        key = (item.get("title", "").lower(), item.get("url", "").lower())
        uniq[key] = item
    return list(uniq.values())


def fetch(url: str, timeout: int = 15, retries: int = 3) -> Page | None:
    last_error = None
    for attempt in range(max(1, retries)):
        try:
            r = requests.get(
                url,
                timeout=(6, timeout),
                allow_redirects=True,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                },
            )
            if r.status_code in {429, 500, 502, 503, 504} and attempt + 1 < retries:
                time.sleep(0.7 * (2 ** attempt))
                continue
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").lower()
            if "html" not in ctype and "xhtml" not in ctype:
                return None

            soup = BeautifulSoup(r.text, "html.parser")
            structured_jobs = _extract_structured_jobs(soup, str(r.url))

            # Canonical URL helps de-duplication when portals add tracking parameters.
            canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
            final_url = absolutize(str(r.url), canonical.get("href")) if canonical and canonical.get("href") else str(r.url)

            for tag in soup(["script", "style", "noscript", "svg", "form"]):
                tag.decompose()
            title = ""
            if soup.find("h1"):
                title = " ".join(soup.find("h1").stripped_strings)
            elif soup.title:
                title = " ".join(soup.title.stripped_strings)
            text = " ".join(soup.stripped_strings)
            return Page(clean_url(final_url), title[:500], text[:220000], soup, r.status_code, structured_jobs)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (2 ** attempt))
    return None
