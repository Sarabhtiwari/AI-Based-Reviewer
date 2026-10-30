from app.graph.client import get_driver

with get_driver().session() as s:
    print("Gupta + papers:")
    for r in s.run("""MATCH (a:Author {is_reviewer:true})-[:AUTHORED]->(p:Paper)
                      RETURN a.name AS name, count(p) AS papers"""):
        print(" ", r["name"], r["papers"])

    print("Hazarika:")
    for r in s.run("""MATCH (a:Author) WHERE a.name CONTAINS 'Hazarika'
                      RETURN a.name AS name, a.s2_id AS s2_id"""):
        print(" ", r["name"], r["s2_id"])

    print("Constraints:")
    for r in s.run("SHOW CONSTRAINTS"):
        print(" ", r["name"])