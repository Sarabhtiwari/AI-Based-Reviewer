"""
Shows exactly why "no paper matching the titles" happens.
Run from the backend folder:
    python scripts/check_fetch.py <ID> <SEMANTIC_SCHOLAR_AUTHOR_ID>
Example:
    python scripts/check_fetch.py 0000-0002-6375-8615 121948183
"""
import sys
from app.connectors import semantic_scholar
from app.connectors.professor_profile import _normalize

identifier, s2_id = sys.argv[1], sys.argv[2]
identifier, source = _normalize(identifier)

profile = source.fetch_profile(identifier)
titles = profile["titles"]
print(f"1) OWN LIST from {source.__name__.split('.')[-1]}: name={profile['name']!r}, {len(titles)} titles")
for t in titles[:5]:
    print("     -", t)

papers = semantic_scholar.fetch_author_papers(s2_id)
print(f"\n2) SEMANTIC SCHOLAR author {s2_id}: {len(papers)} papers fetched")
for p in papers[:5]:
    print("     -", p.get("title"))

if not papers:
    print("\n=> The fetch returned NOTHING. Likely rate limit (429) or a failed request.")
    print("   Wait a few minutes and run again, or look at the uvicorn log for 429 lines.")
    sys.exit()

result = semantic_scholar.filter_papers_by_titles(papers, titles)
print(f"\n3) MATCHED: {len(result['papers'])} papers, match_percent={result['match_percent']}")
print("   dropped:", result.get("dropped"))

if not result["papers"]:
    print("\n=> Papers were fetched but none matches your own list.")
    print("   Compare the two lists above: are they different papers, or only spelled differently?")