"""
Conflict-of-interest (COI) check. Compares author ID strings only,
never paper content.

Three outcomes, so "not checked" never looks like "safe":
  conflict   - a conflict was found
  unverified - we could not fully check (author not found, or no data)
  clear      - everything was checked and nothing was found
"""


def parse_coauthor_ids(coauthor_id_string: str) -> set[str]:
    if not coauthor_id_string:
        return set()
    return {cid.strip() for cid in coauthor_id_string.split(",") if cid.strip()}


def check_conflict(
    paper_authors: list[dict],          # [{"name", "authorId" or None}, ...]
    reviewer_coauthor_ids: set[str],
    reviewer_author_id: str | None = None,
) -> dict:
    resolved = {a["authorId"]: a["name"] for a in paper_authors if a.get("authorId")}
    unresolved = [a["name"] for a in paper_authors if not a.get("authorId")]

    # 1. Reviewer is themselves an author of the paper
    if reviewer_author_id and reviewer_author_id in resolved:
        return {"status": "conflict",
                "reasons": ["Reviewer is listed as an author of this paper"]}

    # 2. Reviewer has co-authored with a paper author
    shared = set(resolved) & reviewer_coauthor_ids
    if shared:
        names = ", ".join(resolved[i] for i in shared)
        return {"status": "conflict",
                "reasons": [f"Has co-authored with paper author(s): {names}"]}

    # No conflict found. Was everything actually checkable?
    reasons = []
    if not paper_authors:
        reasons.append("No paper authors were provided")
    if unresolved:
        reasons.append("Could not find on Semantic Scholar: " + ", ".join(unresolved))
    if not reviewer_coauthor_ids:
        reasons.append("No co-author data stored for this reviewer")

    if reasons:
        return {"status": "unverified", "reasons": reasons}
    return {"status": "clear", "reasons": []}