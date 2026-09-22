from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    llm_model: str = Field(default="llama-3.3-70b-versatile", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, gt=0, alias="LLM_MAX_TOKENS")

    max_iterations: int = Field(default=10, gt=0, le=50, alias="MAX_ITERATIONS")
    command_timeout_seconds: int = Field(default=30, gt=0, alias="COMMAND_TIMEOUT_SECONDS")
    max_output_chars: int = Field(default=8000, gt=0, alias="MAX_OUTPUT_CHARS")
    working_dir: Path = Field(default=Path("."), alias="WORKING_DIR")

    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, gt=0, lt=65536, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")

    @field_validator("working_dir")
    @classmethod
    def resolve_working_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        level = value.upper()
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
