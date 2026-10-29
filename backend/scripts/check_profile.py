"""
Manual check: run the profile pipeline for one professor and print the result.
Run from the backend folder:  python -m scripts.check_profile RwCZSW4AAAAJ
"""

import sys
from app.connectors.professor_profile import get_full_professor_data

identifier = sys.argv[1] if len(sys.argv) > 1 else "RwCZSW4AAAAJ"

r = get_full_professor_data(identifier)

print("name:", r.get("name"))
print("s2 author id:", r.get("semantic_scholar_author_id"))
print("error:", r.get("error"))
print("match_percent:", r.get("match_percent"))
print("papers_dropped:", r.get("papers_dropped"))
print("papers kept:", len(r.get("publications", [])))
for p in r.get("publications", [])[:10]:
    print("-", p.get("paper_id"), "|", p.get("year"), "|", p.get("title"))


from app.connectors import semantic_scholar
all_papers = semantic_scholar.fetch_author_papers("121948183")
kept = {p["paper_id"] for p in r["publications"]}
print("\nDROPPED:")
for p in all_papers:
    if p["paper_id"] not in kept:
        print("-", p["year"], "|", p["title"])