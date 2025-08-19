# Code Style & Conventions

## Python Code Style

### Formatting & Tools
- **Black** for code formatting (automatic)
- **ruff** for linting (configured in Makefile)
- **mypy** for type checking
- **pytest** for testing

### Code Conventions
- **Type Hints**: Required for all function parameters and return values
- **Pydantic Models**: Used for data validation and serialization
- **Async/Await**: FastAPI endpoints use async functions
- **Import Organization**: Use `from __future__ import annotations` for forward references

### Python Example
```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CustomerProfile(BaseModel):
    tenant_id: str
    customer_id: str
    name: Optional[str] = None
    first_seen: datetime
    last_seen: Optional[datetime] = None
```

### File Naming
- Snake case for Python files: `face_detector.py`
- Package directories with `__init__.py`
- Test files prefixed with `test_`: `test_events.py`

## TypeScript/React Code Style

### Formatting & Tools
- **ESLint** for linting
- **Prettier** for code formatting
- **TypeScript** strict mode enabled

### Code Conventions
- **Strict TypeScript**: All variables and functions typed
- **React Functional Components** with hooks
- **Ant Design** components for UI consistency
- **Tailwind CSS** for styling

### TypeScript Example
```typescript
interface CustomerProfile {
  tenant_id: string;
  customer_id: string;
  name?: string;
  first_seen: string;
  last_seen?: string;
}

const CustomerCard: React.FC<{ customer: CustomerProfile }> = ({ customer }) => {
  return <div className="p-4 border rounded">{customer.name}</div>;
};
```

### File Naming
- PascalCase for React components: `CustomerCard.tsx`
- camelCase for utilities: `apiClient.ts`
- kebab-case for CSS files: `customer-card.css`

## Database Conventions

### Table Naming
- Snake case: `customer_profiles`, `visit_records`
- Plural form for entity tables
- Foreign key suffixes: `_id`

### Migration Files
- Numbered prefixes: `001_init.sql`, `002_add_indexes.sql`
- Descriptive names for migrations

## API Conventions

### REST Endpoints
- Versioned paths: `/v1/customers`, `/v1/events/face`
- HTTP methods: GET, POST, PUT, DELETE
- Consistent error responses with HTTP status codes

### JSON Schema
- Versioned contracts: `Event.FaceDetected.v1.json`
- Camel case for JSON properties
- Required fields explicitly defined

## Git Conventions

### Commit Messages
- **Conventional Commits** format
- Examples: `feat: add customer CRUD endpoints`, `fix: resolve JWT validation issue`

### Branch Naming
- Feature branches: `feature/customer-management`
- Bug fixes: `fix/jwt-validation`
- Keep branches short-lived

## Project Structure Conventions

### Directory Organization
- Apps in `/apps/` (api, worker, web)
- Shared code in `/packages/`
- Infrastructure in `/infra/`
- Documentation in `/docs/`

### Configuration
- Environment-based configuration
- Sensible defaults for development
- 12-factor app principles