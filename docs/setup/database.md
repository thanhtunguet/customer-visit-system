# Database Management

This document describes the database management workflow for the Face Recognition API.

## Development Approach

In development phase, we use a **code-first approach** where:
- Database schema is defined in Python models (`app/models/database.py`)
- No migration files are needed - tables are created directly from models
- Database can be recreated fresh anytime during development

## Database Models

All database models are defined in `app/models/database.py`:

- **User** - System users with roles (system_admin, tenant_admin, site_manager, worker)
- **Tenant** - Multi-tenant organization structure
- **Site** - Physical locations within tenants
- **Camera** - RTSP/Webcam devices with enhanced management fields
- **CameraSession** - Lease-based camera assignment tracking
- **Staff** - Employee records for recognition
- **StaffFaceImage** - Multiple face images per staff member
- **Customer** - Visitor records
- **CustomerFaceImage** - Customer face gallery for tracking
- **Visit** - Detection events with session deduplication
- **Worker** - Face processing worker nodes
- **ApiKey** - API access keys

## Database Commands

### Using Make Commands

```bash
# Create tables if they don't exist (safe)
make db-init

# Drop and recreate all tables (destructive)
make db-reset

# Force fresh database (no confirmation prompt)
make db-fresh
```

### Using Python Script Directly

```bash
cd apps/api
source .venv/bin/activate

# Initialize database
python scripts/db_manage.py init

# Reset database (with confirmation)
python scripts/db_manage.py reset

# Force reset without confirmation
python scripts/db_manage.py fresh --force
```

## Automatic Initialization

The API automatically creates database tables on startup when running in development mode (`ENV=dev`).

This happens in `app/main.py` during the FastAPI lifespan startup:

```python
# Initialize database in development mode
if settings.env == "dev":
    from .core.db_init import init_database
    await init_database(drop_existing=False)
```

## Starting Fresh

To start with a completely clean database:

```bash
# Drop and recreate all tables, then start API
make db-fresh
make api-dev
```

## Default Data

The database initialization automatically creates:
- **System Admin User**: 
  - Username: `admin`
  - Password: `admin123`
  - Email: `admin@system.local`

## Migration Strategy

- **Development Phase**: Use code-first approach (current)
- **Production Phase**: Generate proper Alembic migrations before first deployment
- **Post-Production**: Use standard Alembic migration workflow

## Configuration

Database settings are configured in `app/core/config.py`:

```python
# Database Configuration
db_host: str = os.getenv("DB_HOST", "localhost")
db_port: int = int(os.getenv("DB_PORT", "5432"))
db_user: str = os.getenv("DB_USER", "postgres")
db_password: str = os.getenv("DB_PASSWORD", "postgres") 
db_name: str = os.getenv("DB_NAME", "facedb")
database_echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"
```

Set `DATABASE_ECHO=true` to see SQL queries during development.