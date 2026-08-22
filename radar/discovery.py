from __future__ import annotations
from .http import absolutize, allowed_domain, Page

BAD_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".mp4")


def discover_links(page: Page, domains: list[str], terms: list[str], max_links: int = 25) -> list[dict]:
    ranked, seen = [], set()
    terms_l = [x.lower() for x in terms]
    for a in page.soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = absolutize(page.url, href)
        if url in seen or url.lower().endswith(BAD_EXT) or not allowed_domain(url, domains):
            continue
        anchor = " ".join(a.stripped_strings).strip()
        hay = (anchor + " " + url).lower()
        score = sum(1 for t in terms_l if t in hay)
        if score == 0:
            continue
        seen.add(url)
        ranked.append((score, {"url": url, "anchor": anchor[:300]}))
    ranked.sort(key=lambda x: (-x[0], x[1]["url"]))
    return [x[1] for x in ranked[:max_links]]


def heading_blocks(page: Page, max_blocks: int = 50) -> list[dict]:
    out = []
    for h in page.soup.find_all(["h2","h3","h4"]):
        title = " ".join(h.stripped_strings).strip()
        if not title:
            continue
        pieces = [title]
        node, steps = h.find_next_sibling(), 0
        while node is not None and steps < 8:
            if getattr(node, "name", None) in ["h2","h3","h4"]:
                break
            if hasattr(node, "stripped_strings"):
                txt = " ".join(node.stripped_strings).strip()
                if txt:
                    pieces.append(txt)
            node = node.find_next_sibling()
            steps += 1
        text = " ".join(pieces)
        if len(text) >= 90:
            url = page.url + (("#" + h.get("id")) if h.get("id") else "")
            out.append({"title": title[:500], "text": text[:24000], "url": url})
        if len(out) >= max_blocks:
            break
    return out
