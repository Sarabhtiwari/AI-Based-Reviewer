"""Run from backend:  python -m scripts.diagnose 0009-0005-9538-6616"""
import sys
from app.connectors import orcid, semantic_scholar

oid = sys.argv[1]

print("STAGE 1: ORCID record")
try:
    p = orcid.fetch_profile(oid)
except Exception as e:
    print("  FAILED:", e)
    print("  -> ORCID does not exist or is not public. Wrong ID.")
    raise SystemExit
print("  name:", p["name"])
print("  works listed:", len(p["titles"]))
print("  employers:", p["institutions"])
if not p["name"] or not p["titles"]:
    print("  -> STOPS HERE: no name or no public works. Pipeline error 'No name/titles found'.")
    raise SystemExit

print("\nSTAGE 2: match to a Semantic Scholar author (takes ~15 s)")
aid = semantic_scholar.find_author_id_via_titles(p["name"], p["titles"])
print("  S2 author id:", aid)
if not aid:
    print("  -> STOPS HERE: 'Could not confidently match'. Fewer than 2 of the first 8 titles pointed to one author.")
    raise SystemExit

print("\nSTAGE 3: papers and title filter (takes ~1 min)")
papers = semantic_scholar.fetch_author_papers(aid)
r = semantic_scholar.filter_papers_by_titles(papers, p["titles"])
print("  S2 papers fetched:", len(papers), "| kept:", r["kept"], "| match_percent:", r["match_percent"])
if r["match_percent"] < 30:
    print("  -> STOPS HERE: below the 30% safety limit, so the profile is refused.")
else:
    print("  -> OK. Indexing should work.")