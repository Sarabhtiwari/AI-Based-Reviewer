"""Run from backend:  python -m scripts.check_ingest 0000-0002-6375-8615"""
import sys
from app.connectors.professor_profile import get_full_professor_data
from app.graph.ingest import ingest_professor
from app.graph.client import get_driver

data = get_full_professor_data(sys.argv[1])
assert not data.get("error"), data["error"]

for run in (1, 2):  # twice, to prove no duplicates
    print(f"run {run}:", ingest_professor(data))

with get_driver().session() as s:
    print("Author nodes:", s.run("MATCH (a:Author) RETURN count(a) AS n").single()["n"])
    print("Paper nodes:", s.run("MATCH (p:Paper) RETURN count(p) AS n").single()["n"])
    print("AUTHORED edges:", s.run("MATCH ()-[r:AUTHORED]->() RETURN count(r) AS n").single()["n"])