from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import websocket
from app.api.routes import chat, health, session
from app.api.schemas import ErrorResponse
from app.config import get_settings
from app.core.exceptions import ConfigurationError, TerminalAgentError
from app.core.logging import configure_logging, get_logger
from app.graph.runtime import AgentRuntime
from app.graph.workflow import build_graph

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level, use_json=not settings.debug)

    logger.info(
        "starting",
        model=settings.llm_model,
        working_dir=str(settings.working_dir),
    )

    app.state.runtime = _build_runtime()

    yield

    logger.info("shutting down")


def _build_runtime() -> AgentRuntime | None:
    try:
        return AgentRuntime(build_graph())
    except ConfigurationError as error:
        logger.warning("agent_unavailable", reason=str(error))
        return None


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
    app.include_router(chat.router)
    app.include_router(session.router)
    app.include_router(websocket.router)

    @app.exception_handler(TerminalAgentError)
    async def handle_agent_error(request: Request, exc: TerminalAgentError) -> JSONResponse:
        logger.error("agent_error", error=type(exc).__name__, detail=str(exc))
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error=type(exc).__name__, detail=str(exc)).model_dump(),
        )

    return app


app = create_app()
