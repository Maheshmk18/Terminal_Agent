from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.api.schemas import ErrorResponse
from app.config import get_settings
from app.core.exceptions import TerminalAgentError
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level, use_json=not settings.debug)

    logger.info(
        "starting",
        model=settings.llm_model,
        working_dir=str(settings.working_dir),
        api_key_set=settings.has_api_key,
    )

    if not settings.has_api_key:
        logger.warning("groq_api_key_missing", hint="agent routes will fail until set")

    yield

    logger.info("shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Terminal Agent",
        description="A terminal agent powered by open-source models via LangGraph",
        version=health.VERSION,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.include_router(health.router)

    @app.exception_handler(TerminalAgentError)
    async def handle_agent_error(request: Request, exc: TerminalAgentError) -> JSONResponse:
        logger.error("agent_error", error=type(exc).__name__, detail=str(exc))
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error=type(exc).__name__, detail=str(exc)).model_dump(),
        )

    return app


app = create_app()
