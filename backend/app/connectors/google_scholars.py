"""
Fetches a professor's Google Scholar publication list using Tavily (a
search/fetch API) to retrieve the raw profile page content, then Grok
to parse that raw text into structured paper entries.

Why this approach instead of scraping libraries like `scholarly`:
Google Scholar has no official API. Rather than depending on a scraping
library tied to Google's exact HTML structure (which breaks when Google
changes their page layout), we fetch the page content via Tavily and let
an LLM (Grok) extract structured fields from the text. This is more
resilient and reuses infrastructure (Grok) already used elsewhere in
this project for public-data keyword extraction.

This only touches PUBLIC data (a public Google Scholar profile), so
there's no confidentiality concern here.
"""

import json
from tavily import TavilyClient
from openai import OpenAI
from app.config.settings import settings

_tavily_client = TavilyClient(api_key=settings.tavily_api_key)

_grok_client = OpenAI(
    api_key=settings.grok_api_key,
    base_url=settings.grok_base_url,
)

_PARSE_PROMPT_TEMPLATE = """The text below is raw content scraped from a
Google Scholar profile page. Extract the professor's name and their list
of publications.

Return ONLY valid JSON in this exact shape, nothing else -- no preamble,
no markdown code fences:

{{
  "name": "string",
  "publications": [
    {{"title": "string", "year": "string or null", "abstract": "string or empty"}}
  ]
}}

Raw page content:
{content}
"""


def get_author_by_scholar_id(scholar_id: str) -> dict:
    """
    Given a Google Scholar ID (the string after 'user=' in a profile URL),
    fetches the profile page via Tavily and parses it into structured data
    using Grok.

    Example:
        >>> get_author_by_scholar_id("ABC123XYZ")
        {"name": "...", "scholar_id": "...", "publications": [...]}
    """
    profile_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"

    tavily_result = _tavily_client.extract(urls=[profile_url])

    # Tavily's extract() returns a list of results; grab the raw content text
    results = tavily_result.get("results", [])
    if not results:
        raise ValueError(f"Tavily returned no content for scholar_id={scholar_id}")

    raw_content = results[0].get("raw_content", "")

    prompt = _PARSE_PROMPT_TEMPLATE.format(content=raw_content[:15000])  # cap length

    response = _grok_client.chat.completions.create(
        model=settings.grok_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    raw_text = response.choices[0].message.content or "{}"
    parsed = json.loads(raw_text)

    parsed["scholar_id"] = scholar_id
    return parsed