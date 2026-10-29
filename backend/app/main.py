"""
FastAPI application entrypoint.

Run with: uvicorn app.main:app --reload --reload-dir app
Then visit http://127.0.0.1:8000/docs for interactive API docs (Swagger UI).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config.settings import ensure_directories
from app.api.professor_routes import router as professor_router
from app.api.matching_routes import router as matching_router
from app.graph.client import close_driver
from app.graph.schema import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_schema()
    except Exception as e:  # keep Chroma-only routes usable if Neo4j is down
        print(f"[graph] WARNING: could not initialise Neo4j schema: {e}")
    yield
    close_driver()


app = FastAPI(
    title="Reviewer Expertise Discovery API",
    description="Discovers reviewer expertise from public academic profiles.",
    version="0.1.0",
    lifespan=lifespan,
)

ensure_directories()

app.include_router(professor_router)
app.include_router(matching_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Reviewer Expertise Discovery API is running"}