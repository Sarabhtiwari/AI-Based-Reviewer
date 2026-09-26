"""
Extracts research keywords/topics from a professor's PUBLIC papers using
Groq's API. Falls back to using the title when the abstract is missing.
"""

import re
import time
from openai import OpenAI
import json
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
    text = abstract.strip() if abstract and abstract.strip() else title.strip()
    if not text:
        return []

    max_keywords = max_keywords or settings.max_keywords_per_paper
    prompt = _PROMPT_TEMPLATE.format(max_keywords=max_keywords, text=text)

    response = _client.chat.completions.create(
        model=settings.groq_extraction_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=300,
    )

    raw_text = response.choices[0].message.content or ""
    cleaned = _strip_think_tags(raw_text)
    keywords = [kw.strip() for kw in cleaned.split(",") if kw.strip()]
    return keywords


def extract_keywords_for_papers(papers: list[dict], batch_size: int = 10) -> list[dict]:
    """
    Processes papers in batches -- one Groq call per batch instead of
    one per paper -- to drastically cut total request count and time.
    """
    for batch_start in range(0, len(papers), batch_size):
        batch = papers[batch_start:batch_start + batch_size]
        print(f"[keywords] batch {batch_start//batch_size + 1}: papers {batch_start+1}-{batch_start+len(batch)}")

        numbered_papers = "\n\n".join(
            f"[{i}] Title: {p.get('title','')}\nAbstract: {p.get('abstract','') or '(none)'}"
            for i, p in enumerate(batch)
        )

        prompt = f"""For each numbered paper below, extract {settings.max_keywords_per_paper} concise research keywords/topics (2-4 words each).

Return ONLY valid JSON, this exact shape, nothing else:
{{"0": ["keyword1", "keyword2", ...], "1": [...], ...}}

Papers:
{numbered_papers}
"""

        for attempt in range(2):
            try:
                response = _client.chat.completions.create(
                    model=settings.groq_extraction_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2500,
                )
                raw = _strip_think_tags(response.choices[0].message.content or "{}")
                json_match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
                result = json.loads(json_match.group(0) if json_match else raw)

                for i, paper in enumerate(batch):
                    paper["keywords"] = result.get(str(i), [])
                break
            except Exception as e:
                print(f"[keywords ERROR] batch failed: {e}")
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    time.sleep(5 * (attempt + 1))
                    continue
                for paper in batch:
                    paper["keywords"] = []
                break
        else:
            for paper in batch:
                paper["keywords"] = []

        time.sleep(2)  # pace between batches
    return papers