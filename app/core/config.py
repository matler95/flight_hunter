from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Flight Hunter"
    database_url: str = "sqlite:///./data/flight_hunter.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
