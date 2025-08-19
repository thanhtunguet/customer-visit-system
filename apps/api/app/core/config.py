import os


class Settings:
    app_name: str = os.getenv("APP_NAME", "face-api")
    env: str = os.getenv("ENV", "dev")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8080"))
    jwt_issuer: str = os.getenv("JWT_ISSUER", "face.local")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "face")
    jwt_private_key: str | None = os.getenv("JWT_PRIVATE_KEY")
    jwt_public_key: str | None = os.getenv("JWT_PUBLIC_KEY")
    api_key_secret: str = os.getenv("API_KEY_SECRET", "dev-secret")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/postgres")
    tenant_header: str = os.getenv("TENANT_HEADER", "X-Tenant-ID")


settings = Settings()

