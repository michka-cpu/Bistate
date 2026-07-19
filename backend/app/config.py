from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bistate API"
    database_url: str = "sqlite:///./bistate.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
