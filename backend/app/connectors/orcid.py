"""Fetches a researcher's name, work titles and employers from the public ORCID API (no key needed)."""

import httpx
from app.config.settings import settings


def _get_record(orcid: str) -> dict:
    response = httpx.get(
        f"{settings.orcid_base_url}/{orcid}/record",
        headers={"Accept": "application/json"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _year(date_block) -> int | None:
    try:
        return int(((date_block or {}).get("year") or {}).get("value"))
    except (TypeError, ValueError):
        return None


def parse_institutions(record: dict) -> list[dict]:
    """Employers from the ORCID record. end_year None means current."""
    out = []
    groups = ((record.get("activities-summary") or {}).get("employments") or {}).get("affiliation-group", [])
    for group in groups:
        for summary in group.get("summaries", []):
            emp = summary.get("employment-summary") or {}
            org = emp.get("organization") or {}
            name = (org.get("name") or "").strip()
            if not name:
                continue
            ror = None
            dis = org.get("disambiguated-organization") or {}
            if (dis.get("disambiguation-source") or "").upper() == "ROR":
                ror = dis.get("disambiguated-organization-identifier")
            out.append({"name": name, "ror": ror, "end_year": _year(emp.get("end-date"))})
    return out


def fetch_institutions(orcid: str) -> list[dict]:
    return parse_institutions(_get_record(orcid))


def fetch_profile(orcid: str) -> dict:
    """Returns {"name", "titles", "institutions"}."""
    record = _get_record(orcid)

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

    return {"name": name, "titles": titles, "institutions": parse_institutions(record)}