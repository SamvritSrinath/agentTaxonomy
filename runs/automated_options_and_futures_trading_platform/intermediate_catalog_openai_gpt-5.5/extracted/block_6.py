from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./trades.db"

    brokerage_ws_url: str = "wss://api.brokerage.com/live"
    watch_symbol: str = "SPY"
    option_contract_symbol: str = "SPY_PUT_DEMO"

    order_quantity: int = 10
    drop_threshold_pct: float = 2.0
    lookback_minutes: int = 60

    # Safe modes only:
    # paper  -> automatically records paper fill
    # manual -> creates pending recommendation for manual approval
    auto_trade_mode: str = "paper"

    disable_feed: bool = False
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
