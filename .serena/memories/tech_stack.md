# Tech Stack

## Backend (API Service)
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.111.0 
- **Database**: PostgreSQL with SQLAlchemy 2.0.30 + AsyncPG
- **Authentication**: PyJWT 2.8.0 with RS256
- **Password Hashing**: Passlib with bcrypt
- **Migrations**: Alembic 1.13.2
- **HTTP Client**: httpx 0.27.0
- **Vector Database**: PyMilvus 2.4.5
- **Object Storage**: MinIO 7.2.7
- **Scheduling**: APScheduler 3.10.4
- **Face Processing**: OpenCV 4.10.0.84, Pillow 10.4.0, NumPy 1.26.4

## Worker Service
- **Language**: Python 3.11+
- **Computer Vision**: OpenCV 4.10.0.84
- **Face Detection**: YuNet (default), RetinaFace (optional)
- **Face Embeddings**: InsightFace 0.7.3 with ArcFace
- **ML Runtime**: ONNXRuntime 1.16.3 (aarch64), PyTorch+MPS fallback
- **Image Processing**: scikit-image 0.22.0, Pillow 10.4.0
- **HTTP Client**: httpx 0.27.0

## Frontend (Web Interface)
- **Language**: TypeScript
- **Framework**: React 18.2.0
- **Bundler**: Vite 5.2.0
- **UI Library**: Ant Design 5.16.0
- **Styling**: Tailwind CSS 3.4.4
- **Charts**: Recharts 2.12.0
- **Routing**: React Router 6.22.0
- **HTTP Client**: Axios 1.6.0
- **Date Handling**: Day.js 1.11.0

## Development & Testing
- **Testing**: pytest 8.2.2, pytest-asyncio 0.23.7
- **Code Formatting**: black (via Makefile)
- **Package Management**: pip, npm/yarn/pnpm (auto-detected)
- **Containerization**: Docker with multi-arch buildx
- **Orchestration**: Docker Compose, Kubernetes

## Infrastructure
- **Database**: PostgreSQL 16
- **Vector DB**: Milvus v2.4.5 standalone
- **Object Storage**: MinIO (S3-compatible)
- **Container Registry**: Docker Hub/Custom registry
- **Platform**: macOS (arm64), Linux (production)