from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return the service status for uptime checks and the web dashboard."""
    return {"status": "ok"}
