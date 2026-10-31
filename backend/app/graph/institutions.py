"""
Institution name matching. Pure functions, no network.
compare() returns "same", "possible" or None.
"""

import re
import unicodedata
from datetime import date

_ALIASES = [
    (r"\biisc\b", "indian institute of science"),
    (r"\biiit\b", "indian institute of information technology"),
    (r"\biit\b", "indian institute of technology"),
    (r"\bnit\b", "national institute of technology"),
    (r"\bmit\b", "massachusetts institute of technology"),
    (r"\bnyu\b", "new york university"),
    (r"\bbits\b", "birla institute of technology and science"),
    (r"\b(universite|universitat|universidad|universita|univ)\b", "university"),
    (r"\binst\b", "institute"),
    (r"\bdept\b", "department"),
]

# Words that carry no identity ("of", job titles) are dropped completely.
_DROP = {"the", "of", "and", "for", "at", "in", "de", "la", "du", "des",
         "professor", "associate", "assistant", "lecturer", "dr", "prof", "phd", "head",
         "director", "senior", "researcher", "scientist", "postdoc", "student",
         "emeritus", "visiting", "adjunct"}

# Words that are too common to prove two names are the same place.
_GENERIC = {"university", "institute", "college", "school", "department", "faculty",
            "center", "centre", "laboratory", "lab", "research", "academy"}
# Words that sometimes appear glued to a stop-word, e.g. "ofTechnology"
_UNGLUE = {"technology", "science", "sciences", "engineering", "medicine", "management",
           "education", "design", "arts", "health", "research", "applied", "information",
           "computer", "business"}


def _unglue(token: str) -> str:
    for prefix in ("of", "the", "and", "for"):
        if token.startswith(prefix) and token[len(prefix):] in _UNGLUE:
            return token[len(prefix):]
    return token


def tokens(name: str | None) -> frozenset:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace(".", "")
    for pattern, repl in _ALIASES:
        s = re.sub(pattern, repl, s)
    found = (_unglue(t) for t in re.findall(r"[a-z0-9]+", s))
    return frozenset(t for t in found if t not in _DROP)


def key(name: str | None) -> str:
    return " ".join(sorted(tokens(name)))


def compare(a: dict, b: dict) -> str | None:
    """a, b = {"name": str, "ror": str | None, ...}"""
    if a.get("ror") and a.get("ror") == b.get("ror"):
        return "same"
    ta, tb = tokens(a.get("name")), tokens(b.get("name"))
    if not ta or not tb:
        return None
    if ta == tb:
        return "same"
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    distinct = short - _GENERIC
    if distinct and distinct <= long_:
        return "possible"
    return None


def recent(institutions: list[dict], years: int = 3) -> list[dict]:
    """Keep current institutions and ones that ended within the last `years` years."""
    cutoff = date.today().year - years
    return [i for i in institutions if i.get("end_year") is None or i["end_year"] >= cutoff]