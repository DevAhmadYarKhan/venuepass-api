"""Collect the HTTP routers exposed by the VenuePass API."""

from venuepass_api.routes.events import router as events_router

__all__ = ["events_router"]
