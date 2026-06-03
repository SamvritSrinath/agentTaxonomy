from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Cancer Genomics Platform"
    DATABASE_URL: str = "postgresql+psycopg2://genomics:genomics@localhost:5432/genomics"
    SECRET_KEY: str = "dev-only-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 200
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8000", "http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
