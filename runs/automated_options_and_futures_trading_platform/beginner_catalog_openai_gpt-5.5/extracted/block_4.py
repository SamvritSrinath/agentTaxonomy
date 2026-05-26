from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497  # TWS paper default. IB Gateway paper often uses 4002.
    ib_client_id: int = 77
    ib_readonly: bool = True
    ib_delayed_data: bool = True

    demo_mode: bool = False

    default_symbol: str = "SPY"
    drop_threshold_pct: float = 1.5
    lookback_seconds: int = 300

    cors_origins: str = "http://localhost:5173"

    class Config:
        env_prefix = "APP_"
        env_file = ".env"


settings = Settings()
