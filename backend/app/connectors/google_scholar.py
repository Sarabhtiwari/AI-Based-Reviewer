"""Scrapes a public Google Scholar profile: name + paper titles. Nothing else."""

import re
import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_profile(scholar_id: str, max_papers: int = 100) -> dict:
    """Returns {"name": str | None, "titles": list[str]}. One request."""
    url = (
        f"https://scholar.google.com/citations?user={scholar_id}"
        f"&hl=en&cstart=0&pagesize={max_papers}"
    )
    response = httpx.get(url, headers=_HEADERS, timeout=30.0)
    response.raise_for_status()
    html = response.text

    name_match = re.search(r'<div id="gsc_prf_in">(.*?)</div>', html)
    name = re.sub(r"<[^>]+>", "", name_match.group(1)).strip() if name_match else None

    raw_titles = re.findall(r'<a[^>]*class="gsc_a_at"[^>]*>(.*?)</a>', html)
    titles = [re.sub(r"<[^>]+>", "", t).strip() for t in raw_titles if t.strip()]

    return {"name": name or None, "titles": titles}