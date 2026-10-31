"""Uniqueness constraints. Idempotent: safe to run on every startup."""

from app.graph.client import get_driver

_CONSTRAINTS = [
    "CREATE CONSTRAINT author_s2_id IF NOT EXISTS FOR (a:Author) REQUIRE a.s2_id IS UNIQUE",
    "CREATE CONSTRAINT paper_paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE",
    "CREATE CONSTRAINT institution_key IF NOT EXISTS FOR (i:Institution) REQUIRE i.key IS UNIQUE",
]


def init_schema() -> None:
    with get_driver().session() as session:
        for statement in _CONSTRAINTS:
            session.run(statement)