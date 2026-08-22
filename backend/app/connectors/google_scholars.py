"""
Fetches a professor's Google Scholar publication list using Tavily (a
search/fetch API) to retrieve the raw profile page content, then a Groq
LLM to parse that raw text into structured paper entries.

Why this approach instead of scraping libraries like `scholarly`:
Google Scholar has no official API. Rather than depending on a scraping
library tied to Google's exact HTML structure (which breaks when Google
changes their page layout), we fetch the page content via Tavily and let
an LLM (via Groq) extract structured fields from the text. This is more
resilient and reuses infrastructure already used elsewhere in this project
for public-data processing.

This only touches PUBLIC data (a public Google Scholar profile), so
there's no confidentiality concern here.
"""

import json
import re
from tavily import TavilyClient
from openai import OpenAI
from app.config.settings import settings

_tavily_client = TavilyClient(api_key=settings.tavily_api_key)

_groq_client = OpenAI(
    api_key=settings.groq_api_key,
    base_url=settings.groq_base_url,
)

_PARSE_PROMPT_TEMPLATE = """The text below is raw content scraped from a
Google Scholar profile page. Extract the professor's name and their list
of publications.

Return ONLY valid JSON in this exact shape, nothing else -- no preamble,
no markdown code fences, no explanation, no <think> tags:

{{
  "name": "string",
  "publications": [
    {{"title": "string", "year": "string or null", "abstract": "string or empty"}}
  ]
}}

Raw page content:
{content}
"""


def _strip_think_tags(text: str) -> str:
    """
    Some Groq-hosted models (e.g. qwen3.6) emit a <think>...</think> block
    before their actual answer. This strips that out so we're left with
    just the model's final output (ideally clean JSON).
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def get_author_by_scholar_id(scholar_id: str) -> dict:
    """
    Given a Google Scholar ID (the string after 'user=' in a profile URL),
    fetches the profile page via Tavily and parses it into structured data
    using a Groq-hosted LLM.

    Example:
        >>> get_author_by_scholar_id("ABC123XYZ")
        {"name": "...", "scholar_id": "...", "publications": [...]}
    """
    profile_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"

    tavily_result = _tavily_client.extract(urls=[profile_url])

    results = tavily_result.get("results", [])
    if not results:
        raise ValueError(f"Tavily returned no content for scholar_id={scholar_id}")

    raw_content = results[0].get("raw_content", "")

    prompt = _PARSE_PROMPT_TEMPLATE.format(content=raw_content[:15000])  # cap length

    response = _groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=8000,  # reasoning models "think" before answering -- needs headroom
    )

    raw_text = response.choices[0].message.content or "{}"
    cleaned_text = _strip_think_tags(raw_text)

    # Fallback: if <think> was never closed (response got cut off), or there's
    # stray text around the JSON, extract just the {...} block.
    json_match = re.search(r"\{.*\}", cleaned_text, flags=re.DOTALL)
    json_candidate = json_match.group(0) if json_match else cleaned_text

    try:
        parsed = json.loads(json_candidate)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse model output as JSON. Raw output was:\n{cleaned_text}"
        ) from e

    parsed["scholar_id"] = scholar_id
    return parsed