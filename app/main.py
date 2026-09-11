from fastapi import FastAPI

from app.logging_config import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Patient Registration API",
        description="Backend for a Vapi voice agent that registers patients by phone.",
        version="1.0.0",
    )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness probe, and the target of the keep-alive cron that stops the
        free-tier host from sleeping between reviewer calls."""
        return {"status": "ok"}

    return app


app = create_app()
