"""Fetches a researcher's name, work titles and employers from the public ORCID API (no key needed)."""

import time

import httpx
from app.config.settings import settings


def _get_record(orcid: str, attempts: int = 3) -> dict:
    """
    Fetch the ORCID record. Network errors/timeouts and HTTP 429/5xx are retried with a
    growing pause. A real answer such as 404 (ID not found) is raised at once, unchanged,
    so the caller can tell "wrong ID" from "ORCID not reachable".
    """
    last_error: Exception | None = None
    response = None
    for attempt in range(attempts):
        try:
            response = httpx.get(
                f"{settings.orcid_base_url}/{orcid}/record",
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
        except (httpx.TransportError, OSError) as e:   # timeout, connection failed
            last_error, response = e, None
            time.sleep(2 * (attempt + 1))
            continue
        if response.status_code == 429 or response.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        break

    if response is None:
        raise last_error if last_error else RuntimeError("No response from ORCID")
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
    """Returns all distinct publicly visible work titles and institutions in the ORCID record."""
    record = _get_record(orcid)

    name_block = (record.get("person") or {}).get("name") or {}
    given = ((name_block.get("given-names") or {}).get("value")) or ""
    family = ((name_block.get("family-name") or {}).get("value")) or ""
    name = f"{given} {family}".strip() or None

    titles, seen = [], set()
    groups = ((record.get("activities-summary") or {}).get("works") or {}).get("group", [])
    for group in groups:
        # Examine every public work summary, not only the group's first record.
        for summary in group.get("work-summary", []):
            title = (((summary.get("title") or {}).get("title") or {}).get("value")) or ""
            title = title.strip()
            normalized = " ".join(title.casefold().split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                titles.append(title)

    return {"name": name, "titles": titles, "institutions": parse_institutions(record)}