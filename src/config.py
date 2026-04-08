from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "agentops-triage-poc"
    environment: str = "local"
    log_level: str = "INFO"

    host: str = "127.0.0.1"
    port: int = 8000

    write_tools_enabled: bool = False

    max_tool_calls: int = Field(default=6, ge=1)
    tool_timeout_s: int = Field(default=3, ge=1)
    time_budget_s: int = Field(default=30, ge=1)
    llm_timeout_s: int = Field(default=10, ge=1)

    llm_provider: str = "mock"
    llm_model: str = "mock-model"
    llm_backend: str = "mock"
    llm_api_key: str | None = None

    repository_backend: str = "inmemory"
    sqlite_url: str = "sqlite:///./agentops_triage.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENTOPS_",
        extra="ignore",
    )


settings = Settings()



