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

    # Schema migrations (Alembic) applied at startup.
    run_migrations: bool = True

    # Redis pub/sub channel used to tell workers a detection profile changed.
    profile_channel: str = "lisa:detection-profiles"

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
    # Optional in-network URL used to fetch the JWKS (defaults to server URL).
    keycloak_internal_url: str | None = None
    keycloak_realm: str | None = None
    keycloak_client_id: str | None = None
    keycloak_admin_role: str = "admin"
    # BFF: the backend is a confidential OIDC client; tokens stay server-side
    # (Redis) and the browser only holds an opaque HttpOnly session cookie.
    keycloak_client_secret: str | None = None
    # Public URLs, used to build the fixed OAuth2 redirect_uri and post-login
    # / post-logout redirects.
    backend_public_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8080"
    session_cookie_name: str = "lisa_session"
    session_cookie_secure: bool = True
    session_cookie_samesite: str = "lax"
    session_ttl_seconds: int = 7 * 24 * 60 * 60

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def keycloak_token_base(self) -> str | None:
        """Realm base URL the backend uses to reach Keycloak (in-network)."""
        base = self.keycloak_internal_url or self.keycloak_server_url
        if not base or not self.keycloak_realm:
            return None
        return f"{base.rstrip('/')}/realms/{self.keycloak_realm}"

    @property
    def oidc_callback_url(self) -> str:
        return (
            f"{self.backend_public_url.rstrip('/')}{self.api_v1_prefix}/auth/callback"
        )

    @property
    def keycloak_issuer(self) -> str | None:
        if not self.keycloak_server_url or not self.keycloak_realm:
            return None
        base = self.keycloak_server_url.rstrip("/")
        return f"{base}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str | None:
        if not self.keycloak_realm:
            return None
        base = self.keycloak_internal_url or self.keycloak_server_url
        if not base:
            return None
        return (
            f"{base.rstrip('/')}/realms/{self.keycloak_realm}"
            "/protocol/openid-connect/certs"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
