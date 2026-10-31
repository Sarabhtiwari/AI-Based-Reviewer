"""
Run from backend:
  python -m scripts.check_institutions                        (offline name-matching test)
  python -m scripts.check_institutions 0000-0002-6375-8615    (also shows ORCID employers + graph)
"""
import sys
from app.graph.institutions import compare

CASES = [
    ("IIT Bombay", "Indian Institute of Technology Bombay", "same"),
    ("Professor, IIT Bombay", "IIT Bombay", "same"),
    ("IIT Bombay", "IIT Delhi", None),
    ("IIT Madras", "IIT Mandi", None),
    ("Université de Montréal", "University of Montreal", "same"),
    ("MIT", "Massachusetts Institute of Technology", "same"),
    ("Stanford University", "Stanford University School of Medicine", "possible"),
    ("Stanford University", "New York University", None),
    ("Indian Institute of Technology Bombay, Mumbai, India", "IIT Bombay", "possible"),
    ("IIT Bombay", "Indian Institute ofTechnology Bombay", "same"),
]
bad = 0
for a, b, expected in CASES:
    got = compare({"name": a}, {"name": b})
    ok = got == expected
    bad += not ok
    print("OK  " if ok else "FAIL", f"{a!r} vs {b!r} -> {got} (expected {expected})")
print("\nname matching:", "all passed" if not bad else f"{bad} FAILED")

if len(sys.argv) > 1:
    from app.connectors import orcid
    from app.graph.client import get_driver

    print("\nORCID employers:")
    for inst in orcid.fetch_institutions(sys.argv[1]):
        print(" ", inst)

    print("\nStored in graph:")
    with get_driver().session() as s:
        for r in s.run("""MATCH (r:Author {is_reviewer:true})-[a:AFFILIATED_WITH]->(i:Institution)
                          RETURN r.name AS who, i.name AS inst, a.end_year AS end_year ORDER BY who"""):
            print(f"  {r['who']} -> {r['inst']} (ended: {r['end_year'] or 'current'})")