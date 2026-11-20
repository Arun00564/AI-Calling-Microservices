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

    # JWT_SECRET_KEY: str
    # JWT_ALGORITHM: str = "HS256"
    # JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Auth Service
    AUTH_SERVICE_URL: str | None = None
    AUTH_SERVICE_TIMEOUT: float = 5.0
    AUTH_SERVICE_API_PREFIX: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()


# from pydantic_settings import BaseSettings, SettingsConfigDict

# import json
# from pathlib import Path

# from pydantic import model_validator
# from pydantic_settings import BaseSettings, SettingsConfigDict

# BASE_DIR = Path(__file__).resolve().parent.parent
# ENV_FILE = BASE_DIR / ".env"


# def parse_allowed_origins(raw: str | None) -> list[str]:
#     """Turn the CORS_ALLOWED_ORIGINS setting into a clean origin list.

#     Two forms are accepted so an operator can use whichever is convenient:

#         CORS_ALLOWED_ORIGINS=["https://qa-apis.nexby.ai","http://localhost:3000"]
#         CORS_ALLOWED_ORIGINS=https://qa-apis.nexby.ai,http://localhost:3000

#     Origins are normalised the way browsers report them: quotes and spaces
#     removed, no trailing slash (an origin never has one, and a trailing slash
#     in this list silently fails to match every real Origin header).
#     """
#     raw = (raw or "").strip()
#     if not raw:
#         return []

#     if raw.startswith("["):
#         try:
#             values = json.loads(raw)
#         except ValueError:
#             # A JSON-looking but malformed value should not take the whole
#             # service down: fall back to the comma-separated interpretation.
#             values = raw.strip("[]").split(",")
#     else:
#         values = raw.split(",")

#     if not isinstance(values, list):
#         return []

#     origins: list[str] = []
#     for value in values:
#         origin = str(value).strip().strip("\"'").strip().rstrip("/")
#         if origin and origin not in origins:
#             origins.append(origin)
#     return origins


# class Settings(BaseSettings):
#     APP_NAME: str = "Voice Calling API"
#     DEBUG: bool = True

#     DATABASE_URL: str

#     REDIS_URL: str = "redis://localhost:6379/0"

#     PLIVO_AUTH_ID: str
#     PLIVO_AUTH_TOKEN: str
#     PLIVO_AGENT_FLOW_BASE_URL: str

#     VOIZEMATIC_BASE_URL: str
#     VOIZEMATIC_API_KEY: str
#     VOIZEMATIC_PURCHASE_ENABLED: bool = False
#     WEBHOOK_ENCRYPTION_KEY: str

#     JWT_SECRET_KEY: str
#     JWT_ALGORITHM: str = "HS256"
#     JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

#     AUTH_SERVICE_URL: str | None = None
#     AUTH_SERVICE_TIMEOUT: float = 5.0
#     AUTH_SERVICE_API_PREFIX: str = "/api/v1"

#     model_config = SettingsConfigDict(
#         env_file=".env",
#         extra="ignore",
#     )

#       # --- CORS -----------------------------------------------------
#     # Browser origins allowed to call this API. Accepts either a JSON array
#     # (["https://a", "https://b"]) or a comma-separated list (https://a,https://b).
#     # An empty value disables the CORS middleware entirely. Use "*" to allow
#     # any origin (credentials are then disabled, per the CORS spec).
#     CORS_ALLOWED_ORIGINS: str = ""

#     @model_validator(mode="after")
#     def _check_auth_mode(self):
#         if self.ENVIRONMENT == "production" and self.AUTH_MODE == "mock":
#             raise ValueError(
#                 "AUTH_MODE='mock' is not allowed when ENVIRONMENT='production'. "
#                 "Refusing to start."
#             )
#         return self

#     @property
#     def auth_service_root(self) -> str:
#         prefix = self.AUTH_SERVICE_API_PREFIX.strip()
#         if prefix and not prefix.startswith("/"):
#             prefix = "/" + prefix
#         return prefix.rstrip("/")

#     @property
#     def cors_allowed_origins(self) -> list[str]:
#         return parse_allowed_origins(self.CORS_ALLOWED_ORIGINS)

#     model_config = SettingsConfigDict(
#         env_file=ENV_FILE,
#         extra="ignore",
#     )


# settings = Settings()
