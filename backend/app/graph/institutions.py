"""
Institution name matching. Pure functions, no network.
compare() returns "same", "possible" or None.
"""

import re
import unicodedata
from datetime import date

_ALIASES = [
    (r"\bmnnit\b", "motilal nehru national institute of technology"),
    (r"\bprayagraj\b", "allahabad"),  # same city, renamed in 2018
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

# Place words that may be added to or left out of an institution's name
# ("... Technology" vs "... Technology Allahabad"). Only used in compare().
_PLACE_NOISE = {"allahabad", "india", "uttar", "pradesh"}


def tokens(name: str | None) -> frozenset:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace(".", "")
    for pattern, repl in _ALIASES:
        s = re.sub(pattern, repl, s)
    return frozenset(t for t in re.findall(r"[a-z0-9]+", s) if t not in _DROP)


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
    # A place word alone ("University of Allahabad") cannot identify an institution.
    if not (distinct - _PLACE_NOISE):
        return None
    if distinct <= long_:
        # Same name, the longer one only adds a place word (e.g. "Allahabad").
        # Needs 3+ identifying words so a short or vague name cannot qualify.
        if (long_ - short) <= _PLACE_NOISE and len(distinct) >= 3:
            return "same"
        return "possible"
    return None


def recent(institutions: list[dict], years: int = 3) -> list[dict]:
    """Keep current institutions and ones that ended within the last `years` years."""
    cutoff = date.today().year - years
    return [i for i in institutions if i.get("end_year") is None or i["end_year"] >= cutoff]