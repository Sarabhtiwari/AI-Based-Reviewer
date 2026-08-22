"""
Fetches a professor's Google Scholar publication list.

Two-part approach, deliberately split by reliability needs:

1. NAME: fetched via a direct HTTP request to the profile page and parsed
   from a fixed HTML location (Google Scholar always renders the profile
   owner's name inside a <div id="gsc_prf_in">). This is deterministic --
   no guessing involved, so it's always correct.

2. PUBLICATIONS: fetched via Tavily (cleans/extracts page text) and parsed
   by a Groq LLM, since the publication table's structure varies more and
   benefits from an LLM's ability to handle messy/inconsistent formatting.

Why not use the LLM for the name too: an earlier version let the model
guess the profile owner's name from co-author frequency in the raw text,
which produced a DIFFERENT (wrong) name on a repeated run for the same
scholar_id. Names must be extracted deterministically, not inferred.
"""

import json
import re
import httpx
from tavily import TavilyClient
from openai import OpenAI
from app.config.settings import settings

_tavily_client = TavilyClient(api_key=settings.tavily_api_key)

_groq_client = OpenAI(
    api_key=settings.groq_api_key,
    base_url=settings.groq_base_url,
)

_PARSE_PUBLICATIONS_PROMPT = """The text below is raw content scraped from a
Google Scholar profile page. Extract ONLY the list of publications (ignore
any names of people -- the name is handled separately).

Return ONLY valid JSON in this exact shape, nothing else -- no preamble,
no markdown code fences, no explanation, no <think> tags:

{{
  "publications": [
    {{"title": "string", "year": "string or null", "abstract": "string or empty"}}
  ]
}}

Raw page content:
{content}
"""

# Google blocks requests without a browser-like User-Agent header.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _fetch_scholar_name(scholar_id: str) -> str:
    """
    Directly fetches the Google Scholar profile page HTML and extracts the
    profile owner's name from the fixed <div id="gsc_prf_in"> element.
    Deterministic -- no LLM guessing involved.
    """
    profile_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"

    response = httpx.get(profile_url, headers=_BROWSER_HEADERS, timeout=30.0)
    response.raise_for_status()
    html = response.text

    match = re.search(r'<div id="gsc_prf_in">(.*?)</div>', html)
    if not match:
        return "Unknown"

    # Strip any nested HTML tags from the matched name text
    name = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return name or "Unknown"


def _fetch_publications_via_tavily(scholar_id: str) -> list[dict]:
    """
    Uses Tavily to fetch the profile page content, then Groq to parse
    just the publications list out of the raw scraped text.
    """
    profile_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"

    tavily_result = _tavily_client.extract(urls=[profile_url])
    results = tavily_result.get("results", [])
    if not results:
        raise ValueError(f"Tavily returned no content for scholar_id={scholar_id}")

    raw_content = results[0].get("raw_content", "")
    prompt = _PARSE_PUBLICATIONS_PROMPT.format(content=raw_content[:6000])

    response = _groq_client.chat.completions.create(
        model=settings.groq_extraction_model,  # non-reasoning model -- faster, fits token limits
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
    )

    raw_text = response.choices[0].message.content or "{}"
    cleaned_text = _strip_think_tags(raw_text)

    json_match = re.search(r"\{.*\}", cleaned_text, flags=re.DOTALL)
    json_candidate = json_match.group(0) if json_match else cleaned_text

    try:
        parsed = json.loads(json_candidate)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse model output as JSON. Raw output was:\n{cleaned_text}"
        ) from e

    return parsed.get("publications", [])


def get_author_by_scholar_id(scholar_id: str) -> dict:
    """
    Given a Google Scholar ID, returns the author's name (fetched
    deterministically) and list of publications (fetched via Tavily + Groq).
    """
    name = _fetch_scholar_name(scholar_id)
    publications = _fetch_publications_via_tavily(scholar_id)

    return {
        "name": name,
        "scholar_id": scholar_id,
        "publications": publications,
    }