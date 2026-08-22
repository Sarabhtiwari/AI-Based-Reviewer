"""
FastAPI application entrypoint.

Run with: uvicorn app.main:app --reload
Then visit http://127.0.0.1:8000/docs for interactive API docs (Swagger UI).
"""

from fastapi import FastAPI
from app.config.settings import ensure_directories
from app.api.professor_routes import router as professor_router
from app.api.matching_routes import router as matching_router

app = FastAPI(
    title="Reviewer Expertise Discovery API",
    description="Discovers reviewer expertise from public academic profiles.",
    version="0.1.0",
)

ensure_directories()

app.include_router(professor_router)
app.include_router(matching_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Reviewer Expertise Discovery API is running"}