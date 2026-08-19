from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Flight Hunter"
    database_url: str = "sqlite:///./data/flight_hunter.db"
    default_currency: str = "PLN"
    provider_min_interval_seconds: float = 10
    provider_results_per_query: int = 10
    max_offers_to_verify: int = 10
    daily_search_hour: int = 8
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
