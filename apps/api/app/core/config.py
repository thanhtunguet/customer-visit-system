import os


import os
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    
    # Find .env file relative to this config file
    # Structure: apps/api/app/core/config.py -> apps/api/.env
    current_file = Path(__file__)
    api_root = current_file.parent.parent.parent  # Go up from app/core/ to apps/api/
    env_file = api_root / ".env"
    
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✓ Loaded environment variables from {env_file}")
    else:
        print(f"⚠ No .env file found at {env_file} - using system environment variables only")
        
except ImportError:
    print("⚠ python-dotenv not installed - using system environment variables only")


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
    database_echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"
    
    # Milvus Configuration
    milvus_host: str = os.getenv("MILVUS_HOST", "localhost")
    milvus_port: int = int(os.getenv("MILVUS_PORT", "19530"))
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "face_embeddings")
    milvus_user: str | None = os.getenv("MILVUS_USER")
    milvus_password: str | None = os.getenv("MILVUS_PASSWORD") 
    milvus_secure: bool = os.getenv("MILVUS_SECURE", "false").lower() == "true"
    
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
    
    # Customer face gallery settings
    max_face_images: int = int(os.getenv("MAX_FACE_IMAGES", "5"))
    min_face_confidence_to_save: float = float(os.getenv("MIN_FACE_CONFIDENCE_TO_SAVE", "0.7"))

    # Identity assignment / clustering knobs
    embedding_distance_thr: float = float(os.getenv("EMBEDDING_DISTANCE_THR", "0.85"))
    merge_distance_thr: float = float(os.getenv("MERGE_DISTANCE_THR", "0.90"))
    merge_margin: float = float(os.getenv("MERGE_MARGIN", "0.04"))
    min_cluster_samples: int = int(os.getenv("MIN_CLUSTER_SAMPLES", "1"))
    min_track_length: int = int(os.getenv("MIN_TRACK_LENGTH", "1"))
    temporal_hysteresis_secs: float = float(os.getenv("TEMPORAL_HYSTERESIS_SECS", "3.0"))
    quality_min_score: float = float(os.getenv("QUALITY_MIN_SCORE", "0.6"))


settings = Settings()
