"""
Shows how many titles each side has, and WHERE the missing ones live on Semantic Scholar.
Run from the backend folder (PowerShell):
    $env:PYTHONPATH = "."
    python scripts/check_split_profile.py <ORCID or Scholar ID> <SEMANTIC_SCHOLAR_AUTHOR_ID>
Example:
    python scripts/check_split_profile.py 0000-0002-5467-3812 2284639276
"""
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

from app.connectors import semantic_scholar as ss
from app.connectors.professor_profile import _normalize, MIN_MATCH_PERCENT

MAX_LOOKUPS = 30   # each lookup takes about 1.1 s

identifier, s2_id = sys.argv[1], sys.argv[2]
identifier, source = _normalize(identifier)
src = source.__name__.split(".")[-1]

profile = source.fetch_profile(identifier)
titles = profile["titles"]
print(f"1) OWN LIST ({src}): name={profile['name']!r}")
print(f"   {len(titles)} distinct titles"
      + ("  (Google Scholar: only the first 100 are read)" if src == "google_scholar" else ""))

papers = ss.fetch_author_papers(s2_id)
result = ss.filter_papers_by_titles(papers, titles)
print(f"\n2) SEMANTIC SCHOLAR author {s2_id}: {len(papers)} papers on this one profile")
print(f"   {result['kept']} of them are on your own list")
print(f"   match = {result['match_percent']}% of your {len(titles)} titles (limit is {MIN_MATCH_PERCENT:.0f}%)")

known = {ss._norm_title(p.get("title")) for p in result["papers"]}
missing = [t for t in titles
           if not any(SequenceMatcher(None, ss._norm_title(t), k).ratio() >= 0.92 for k in known)]
print(f"\n3) {len(missing)} of your titles are NOT on profile {s2_id}.")
if not missing:
    sys.exit()

surname = [w for w in re.findall(r"[a-z0-9]+", (profile["name"] or "").lower()) if len(w) >= 2][-1]
where, not_found = Counter(), 0
print(f"   Looking up up to {MAX_LOOKUPS} of them on Semantic Scholar (about {MAX_LOOKUPS} seconds)...\n")
for t in missing[:MAX_LOOKUPS]:
    r = ss._get(f"{ss._BASE}/paper/search", {"query": t, "fields": "title,authors", "limit": 1})
    if r is None or r.status_code != 200:
        print("   [no answer]", t[:70]); continue
    data = r.json().get("data", [])
    if not data or SequenceMatcher(None, ss._norm_title(data[0].get("title")), ss._norm_title(t)).ratio() < 0.85:
        not_found += 1
        print("   [not on Semantic Scholar]", t[:70]); continue
    ids = [a["authorId"] for a in data[0].get("authors", [])
           if a.get("authorId") and surname in ss._name_tokens(a.get("name"))]
    for i in ids:
        where[i] += 1
    print(f"   found, same-surname author id(s) {ids}:", t[:60])

print("\n4) RESULT")
print(f"   not on Semantic Scholar at all : {not_found}")
for i, n in where.most_common(5):
    flag = "  <- the profile you used" if i == str(s2_id) else ""
    print(f"   author id {i} holds {n} of the missing titles{flag}")
others = [i for i, _ in where.most_common(5) if i != str(s2_id)]
if others:
    print("\n   Semantic Scholar has split this person into several profiles.")
    print("   Open each id at semanticscholar.org/author/<id>; if they are the same person, index with:")
    print(f"   {sys.argv[1]}={s2_id}+" + "+".join(others[:2]))