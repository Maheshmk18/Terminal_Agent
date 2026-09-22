from fastapi import APIRouter, Response, status

from app.api.schemas import HealthResponse, ReadinessCheck, ReadinessResponse
from app.config import get_settings

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(version=VERSION)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(response: Response) -> ReadinessResponse:
    settings = get_settings()
    checks = [_check_api_key(settings), _check_working_dir(settings)]
    is_ready = all(check.passed for check in checks)

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(ready=is_ready, checks=checks)


def _check_api_key(settings) -> ReadinessCheck:
    if settings.has_api_key:
        return ReadinessCheck(name="groq_api_key", passed=True, detail="configured")
    return ReadinessCheck(
        name="groq_api_key",
        passed=False,
        detail="GROQ_API_KEY is missing, copy .env.example to .env and set it",
    )


def _check_working_dir(settings) -> ReadinessCheck:
    path = settings.working_dir
    if path.is_dir():
        return ReadinessCheck(name="working_dir", passed=True, detail=str(path))
    return ReadinessCheck(
        name="working_dir",
        passed=False,
        detail=f"not a directory: {path}",
    )
