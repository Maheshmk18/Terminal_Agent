from fastapi import HTTPException, Request, status

from app.graph.runtime import AgentRuntime


def get_runtime(request: Request) -> AgentRuntime:
    runtime = getattr(request.app.state, "runtime", None)

    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent is not available, check GROQ_API_KEY and restart",
        )

    return runtime
