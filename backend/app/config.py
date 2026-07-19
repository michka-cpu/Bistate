from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bistate API"
    database_url: str = "sqlite:///./bistate.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    upload_dir: str = "./uploads"
    live_providers_enabled: bool = False
    provider_timeout_seconds: float = 8
    provider_retry_count: int = 2
    fema_api_url: str | None = None
    census_api_key: str | None = None
    assessor_api_key: str | None = None
    parcel_api_key: str | None = None
    schools_api_key: str | None = None
    zoning_api_key: str | None = None
    str_regulations_api_key: str | None = None
    routing_api_key: str | None = None
    places_api_key: str | None = None
    walkscore_api_key: str | None = None
    airdna_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
