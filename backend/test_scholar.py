import json
from app.connectors.google_scholars import get_author_by_scholar_id

result = get_author_by_scholar_id("RwCZSW4AAAAJ")
print(json.dumps(result, indent=2))