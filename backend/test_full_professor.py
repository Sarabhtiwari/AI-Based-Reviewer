from app.connectors.professor_profile import get_full_professor_data

data = get_full_professor_data("RwCZSW4AAAAJ")

print("Name:", data["name"])
print("Semantic Scholar ID:", data["semantic_scholar_author_id"])
print("Error:", data.get("error"))
print("Papers:", len(data["publications"]))

unique = {}
for p in data["publications"]:
    for c in p["coauthors"]:
        if c.get("authorId"):
            unique[c["authorId"]] = c["name"]

print("Unique co-authors:", len(unique))
for aid, name in list(unique.items())[:40]:
    print(" -", name, aid)