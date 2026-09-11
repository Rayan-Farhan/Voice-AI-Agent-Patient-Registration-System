from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.patients import router as patients_router
from app.db import init_db
from app.errors import register_exception_handlers
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup rather than at import time, so importing the
    module for tests or tooling does not touch a real database."""
    init_db()
    yield


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        lifespan=lifespan,
        title="Patient Registration API",
        description="Backend for a Vapi voice agent that registers patients by phone.",
        version="1.0.0",
    )

    register_exception_handlers(app)
    app.include_router(patients_router)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness probe, and the target of the keep-alive cron that stops the
        free-tier host from sleeping between reviewer calls."""
        return {"status": "ok"}

    return app


app = create_app()
