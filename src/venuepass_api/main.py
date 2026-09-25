"""Create the FastAPI application and its infrastructure-level routes."""

from fastapi import FastAPI

from venuepass_api.routes import events_router

# ASGI application imported by Uvicorn when the development server starts.
app = FastAPI(title="VenuePass API")

# Feature routers keep resource endpoints separate from application bootstrap.
app.include_router(events_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Confirm that the API process is running without querying dependencies."""
    return {"status": "ok"}
