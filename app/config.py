from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    failure_mode: str = "normal"
    database_url: str = "postgresql+psycopg://aiops:aiops@localhost:5432/aiops"
    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"
    deployment_version: str = "0.1.0"
    deployment_commit: str | None = None
    deployment_deployed_at: str | None = None
    deployment_description: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
