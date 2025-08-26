# Code Style and Conventions

## Python Code Style
- **Type Hints**: Extensive use of typing annotations (from `__future__ import annotations`)
- **Pydantic Models**: Used for request/response validation and serialization
- **SQLAlchemy**: Declarative base models with proper relationships
- **Async/Await**: Async patterns throughout FastAPI application
- **Enums**: Python enums for constants (CameraType, UserRole, etc.)
- **Password Hashing**: Passlib with bcrypt context
- **UUID Generation**: String-based UUIDs for primary keys
- **Timestamps**: UTC datetime with auto-update patterns

## Python Naming Conventions
- **Variables/Functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Files/Modules**: snake_case
- **Database Tables**: snake_case with descriptive names

## Database Conventions
- **Primary Keys**: String-based UUIDs (64 chars)
- **Foreign Keys**: Proper CASCADE relationships
- **Timestamps**: created_at, updated_at with auto-management
- **Enums**: PostgreSQL enums for constrained values
- **Indexes**: Proper indexing for performance
- **RLS**: Row Level Security for multi-tenancy

## TypeScript/React Conventions
- **Components**: PascalCase functional components
- **Props**: Interface definitions with proper typing
- **Hooks**: React hooks pattern with proper dependency arrays
- **Styling**: Tailwind CSS classes with Ant Design components
- **File Structure**: Feature-based organization

## API Conventions
- **REST Endpoints**: Proper HTTP verbs and status codes
- **Request/Response**: Pydantic models for validation
- **Error Handling**: Structured error responses
- **Authentication**: JWT Bearer tokens with role-based access
- **Versioning**: /v1 prefix for API endpoints

## Docker Conventions
- **Multi-stage Builds**: Separate build and runtime stages
- **Multi-arch**: arm64 and amd64 support
- **Health Checks**: Proper health check endpoints
- **Security**: Non-root users in containers

## Testing Conventions
- **File Names**: test_*.py pattern
- **Fixtures**: pytest fixtures for setup/teardown
- **Async Tests**: pytest-asyncio for async test functions
- **Mocking**: pytest-mock for dependency mocking
- **Coverage**: Aim for 80%+ test coverage