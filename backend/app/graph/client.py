"""Single shared Neo4j driver, created on first use."""

from neo4j import GraphDatabase
from app.config.settings import settings

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_lifetime=200,   # recycle connections before Aura drops them
            keep_alive=True,
        )
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None