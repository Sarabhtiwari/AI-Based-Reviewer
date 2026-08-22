"""
Extracts research keywords/topics from a professor's PUBLIC papers using
Groq's API. Falls back to using the title when the abstract is missing
(common for Google Scholar-sourced papers where abstracts aren't scraped).

Why this is safe to send to a cloud API:
This module must ONLY ever be called with text from already-published,
public papers. It must NEVER be called with text from the confidential
unpublished paper -- that stays local, handled separately in app/embeddings/.
"""

import re
from openai import OpenAI
from app.config.settings import settings

_client = OpenAI(
    api_key=settings.groq_api_key,
    base_url=settings.groq_base_url,
)

_PROMPT_TEMPLATE = """You are helping build a research-expertise profile.
Given the paper info below, extract {max_keywords} concise research
keywords/topics (2-4 words each) that best describe its subject matter.

Return ONLY a comma-separated list, nothing else -- no numbering, no
preamble, no explanation, no <think> tags.

Paper info:
{text}
"""


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_keywords(title: str, abstract: str = "", max_keywords: int | None = None) -> list[str]:
    """
    Takes a paper's title (required) and abstract (optional) and returns
    a list of keyword strings. Uses the abstract when available for
    richer extraction; falls back to title-only otherwise.
    """
    text = abstract.strip() if abstract and abstract.strip() else title.strip()

    if not text:
        return []

    max_keywords = max_keywords or settings.max_keywords_per_paper
    prompt = _PROMPT_TEMPLATE.format(max_keywords=max_keywords, text=text)

    response = _client.chat.completions.create(
        model=settings.groq_extraction_model,  # non-reasoning model, fast + cheap
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=300,
    )

    raw_text = response.choices[0].message.content or ""
    cleaned = _strip_think_tags(raw_text)
    keywords = [kw.strip() for kw in cleaned.split(",") if kw.strip()]
    return keywords


def extract_keywords_for_papers(papers: list[dict]) -> list[dict]:
    """
    Batch version: takes a list of paper dicts (each with 'title' and
    optionally 'abstract' keys) and adds a 'keywords' key to each one.
    """
    for paper in papers:
        paper["keywords"] = extract_keywords(
            title=paper.get("title", ""),
            abstract=paper.get("abstract", ""),
        )
    return papers