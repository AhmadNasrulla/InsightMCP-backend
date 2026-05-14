from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_DB: str = "assignment3"
    PG_APP_USER: str = "postgres"
    PG_APP_PASSWORD: str = "123"

    PG_RO_USER: str = "mcp_readonly"
    PG_RO_PASSWORD: str = "readonly_demo_pw_change_me"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 1440

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    QUERY_TIMEOUT_SECONDS: int = 10
    QUERY_DEFAULT_LIMIT: int = 100
    QUERY_MAX_LIMIT: int = 1000

    SCHEMA_NAME: str = "retail_dw"

    @property
    def app_dsn(self) -> str:
        return (
            f"host={self.PG_HOST} port={self.PG_PORT} dbname={self.PG_DB} "
            f"user={self.PG_APP_USER} password={self.PG_APP_PASSWORD}"
        )

    @property
    def ro_dsn(self) -> str:
        return (
            f"host={self.PG_HOST} port={self.PG_PORT} dbname={self.PG_DB} "
            f"user={self.PG_RO_USER} password={self.PG_RO_PASSWORD}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
