from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisDepth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"

    @property
    def max_files(self) -> int:
        return {"quick": 15, "standard": 30, "deep": 75}[self.value]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM
    gemini_api_key: SecretStr = SecretStr("")
    llm_model: str = "gemini/gemini-2.5-flash"
    llm_temperature: float = 0.2
    llm_max_retries: int = 3

    # GitHub
    github_token: SecretStr = SecretStr("")

    # LangSmith
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "codebase-onboarding-agent"
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Application
    log_level: str = "INFO"
    analysis_max_files: int = 75
    clone_dir: Path = Path("/tmp/onboarding-agent-repos")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
