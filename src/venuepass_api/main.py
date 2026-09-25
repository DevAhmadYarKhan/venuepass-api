"""Create the FastAPI application and its infrastructure-level routes."""

from fastapi import FastAPI

# ASGI application imported by Uvicorn when the development server starts.
app = FastAPI(title="VenuePass API")


@app.get("/health")
async def health() -> dict[str, str]:
    """Confirm that the API process is running without querying dependencies."""
    return {"status": "ok"}
