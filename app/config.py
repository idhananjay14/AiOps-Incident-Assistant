from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    failure_mode: str = "normal"
    database_url: str = "postgresql+psycopg://aiops:aiops@localhost:5432/aiops"
    prometheus_url: str = "http://localhost:9090"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
