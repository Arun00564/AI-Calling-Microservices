from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Voice Calling API"
    DEBUG: bool = True

    DATABASE_URL: str

    REDIS_URL: str = "redis://localhost:6379/0"

    PLIVO_AUTH_ID: str
    PLIVO_AUTH_TOKEN: str
    PLIVO_AGENT_FLOW_BASE_URL: str

    VOIZEMATIC_BASE_URL: str
    VOIZEMATIC_API_KEY: str
    VOIZEMATIC_PURCHASE_ENABLED: bool = False
    WEBHOOK_ENCRYPTION_KEY: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
