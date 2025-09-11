# Tech Stack

## Backend

- **Framework**: FastAPI (Python 3.11+)
- **Database**: 
    - **Primary**: PostgreSQL (v13+) for metadata and application data.
    - **Vector Database**: Milvus (v2.3+) for face embedding storage and similarity search.
- **Object Storage**: MinIO (S3-compatible) for storing raw and processed images.
- **Async Operations**: `asyncio` for concurrent operations.
- **ORM**: SQLAlchemy for database interactions.
- **Migrations**: Alembic for database schema migrations.

## Frontend

- **Framework**: React (v18+)
- **Language**: TypeScript
- **Build Tool**: Vite
- **UI Library**: Ant Design (AntD) v5
- **Styling**: Tailwind CSS
- **Routing**: React Router v6
- **API Communication**: Axios

## Infrastructure & Deployment

- **Containerization**: Docker
- **Orchestration**: Docker Compose (for development), Kubernetes (for production)
- **CI/CD**: (Not specified, but `Makefile` provides build and test commands)

## Testing

- **Backend**: `pytest` with `pytest-asyncio`
- **Frontend**: (Not specified, likely Jest or Vitest could be added)
