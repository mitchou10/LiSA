from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    app_name: str = "LiSA API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # PostgreSQL (async driver)
    database_url: str = "postgresql+asyncpg://lisa:lisa@db:5432/lisa"
    db_echo: bool = False

    # Celery / Redis (task dispatch to worker services)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # CORS
    cors_origins: list[str] = ["*"]

    # Authentication (local JWT)
    jwt_secret: str = "change-me-in-production-with-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # 12 hours

    # Machine-to-machine token used by the worker (and other backend services)
    # to call the API without a user login. When set, a request presenting this
    # value as a Bearer token is treated as a service account with admin rights.
    service_token: str | None = None

    # Default admin seeded at startup if it does not exist.
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_email: str | None = None

    # Auth provider: "local" (JWT issued by this app) or "keycloak" (validate
    # OIDC bearer tokens against a Keycloak realm via its JWKS endpoint).
    auth_provider: str = "local"
    keycloak_server_url: str | None = None  # e.g. https://kc.example.com
    keycloak_realm: str | None = None
    keycloak_client_id: str | None = None
    keycloak_admin_role: str = "admin"

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def keycloak_issuer(self) -> str | None:
        if not self.keycloak_server_url or not self.keycloak_realm:
            return None
        base = self.keycloak_server_url.rstrip("/")
        return f"{base}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str | None:
        issuer = self.keycloak_issuer
        return f"{issuer}/protocol/openid-connect/certs" if issuer else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
