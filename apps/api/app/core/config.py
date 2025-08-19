import os


class Settings:
    app_name: str = os.getenv("APP_NAME", "face-api")
    env: str = os.getenv("ENV", "dev")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8080"))
    
    # JWT Configuration
    jwt_issuer: str = os.getenv("JWT_ISSUER", "face.local")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "face")
    jwt_private_key: str | None = os.getenv("JWT_PRIVATE_KEY")
    jwt_public_key: str | None = os.getenv("JWT_PUBLIC_KEY")
    api_key_secret: str = os.getenv("API_KEY_SECRET", "dev-secret")
    
    # Database Configuration
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "postgres")
    db_name: str = os.getenv("DB_NAME", "facedb")
    database_url: str = os.getenv(
        "DATABASE_URL", 
        f"postgresql+asyncpg://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'facedb')}"
    )
    
    # Milvus Configuration
    milvus_host: str = os.getenv("MILVUS_HOST", "localhost")
    milvus_port: int = int(os.getenv("MILVUS_PORT", "19530"))
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "face_embeddings")
    
    # MinIO Configuration
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket_raw: str = os.getenv("MINIO_BUCKET_RAW", "faces-raw")
    minio_bucket_derived: str = os.getenv("MINIO_BUCKET_DERIVED", "faces-derived")
    
    # Other Configuration
    tenant_header: str = os.getenv("TENANT_HEADER", "X-Tenant-ID")
    face_similarity_threshold: float = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.6"))
    max_face_results: int = int(os.getenv("MAX_FACE_RESULTS", "5"))


settings = Settings()

