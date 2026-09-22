import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_apply_when_env_is_empty():
    settings = Settings(_env_file=None)

    assert settings.llm_model == "llama-3.3-70b-versatile"
    assert settings.max_iterations == 10
    assert settings.app_port == 8000


def test_has_api_key_is_false_for_blank_value():
    assert Settings(_env_file=None, GROQ_API_KEY="   ").has_api_key is False
    assert Settings(_env_file=None, GROQ_API_KEY="gsk_test").has_api_key is True


def test_working_dir_becomes_absolute():
    settings = Settings(_env_file=None, WORKING_DIR=".")
    assert settings.working_dir.is_absolute()


def test_invalid_log_level_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, LOG_LEVEL="LOUD")


def test_log_level_is_uppercased():
    assert Settings(_env_file=None, LOG_LEVEL="debug").log_level == "DEBUG"


def test_out_of_range_values_are_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, LLM_TEMPERATURE=5.0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, MAX_ITERATIONS=0)
