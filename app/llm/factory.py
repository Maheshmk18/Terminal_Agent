from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.config import Settings, get_settings
from app.core.exceptions import ConfigurationError


def build_llm(settings: Settings | None = None) -> BaseChatModel:
    settings = settings or get_settings()

    if not settings.has_api_key:
        raise ConfigurationError(
            "GROQ_API_KEY is not set, copy .env.example to .env and add your key"
        )

    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=60,
        max_retries=2,
    )
