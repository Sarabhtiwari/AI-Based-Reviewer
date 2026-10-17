"""Fetches a researcher's name + work titles from the public ORCID API (no key needed)."""

import httpx
from app.config.settings import settings


def fetch_profile(orcid: str) -> dict:
    """Returns {"name": str | None, "titles": list[str]}."""
    response = httpx.get(
        f"{settings.orcid_base_url}/{orcid}/record",
        headers={"Accept": "application/json"},
        timeout=30.0,
    )
    response.raise_for_status()
    record = response.json()

    name_block = (record.get("person") or {}).get("name") or {}
    given = ((name_block.get("given-names") or {}).get("value")) or ""
    family = ((name_block.get("family-name") or {}).get("value")) or ""
    name = f"{given} {family}".strip() or None

    titles, seen = [], set()
    groups = ((record.get("activities-summary") or {}).get("works") or {}).get("group", [])
    for group in groups:
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        title = (((summaries[0].get("title") or {}).get("title") or {}).get("value")) or ""
        title = title.strip()
        if title and title.lower() not in seen:
            seen.add(title.lower())
            titles.append(title)

    return {"name": name, "titles": titles}