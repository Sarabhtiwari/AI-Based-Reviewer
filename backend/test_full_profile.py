import json
from app.connectors.google_scholars import get_author_by_scholar_id
from app.nlp.keyword_extraction import extract_keywords_for_papers
from app.nlp.expertise_profile import build_expertise_profile

result = get_author_by_scholar_id("RwCZSW4AAAAJ")
papers_with_keywords = extract_keywords_for_papers(result["publications"])  # all papers this time
profile = build_expertise_profile(result["name"], papers_with_keywords)

print(json.dumps(profile, indent=2))