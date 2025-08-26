# Admin Account Management

This document describes how to manage admin accounts in the face recognition system.

## Quick Start

The easiest way to create an admin account is using the interactive script:

```bash
# From project root
make init-admin

# Or directly
cd apps/api && bash scripts/init-admin.sh create-admin
```

## Available Commands

### 1. Create Admin Account

**Interactive mode (recommended):**
```bash
make init-admin
```

**Direct mode:**
```bash
cd apps/api
python scripts/init_admin.py create \
  --username admin \
  --email admin@example.com \
  --password securepassword123 \
  --first-name System \
  --last-name Administrator
```

### 2. Reset Password

**Via Makefile:**
```bash
make reset-password username=admin password=newpassword123
```

**Direct mode:**
```bash
cd apps/api
python scripts/init_admin.py reset-password admin newpassword123

# Or using shell script
bash scripts/init-admin.sh reset-password admin newpassword123
```

### 3. List All Users

```bash
make list-users

# Or directly
cd apps/api
python scripts/init_admin.py list
```

## Script Features

### Security Features
- Password input is hidden during interactive creation
- Password confirmation to prevent typos
- Validates that passwords are not empty
- Uses bcrypt hashing for secure password storage

### Error Handling
- Checks for existing users before creation
- Validates database connection
- Provides clear success/error messages
- Proper transaction rollback on errors

### User Information
- Creates system admin users (not tied to specific tenants)
- Sets email as verified by default
- Records creation timestamps
- Generates unique UUID for each user

## User Roles

The system supports these user roles:

- **system_admin**: Full system access, can manage all tenants
- **tenant_admin**: Manages specific tenant and its sites
- **site_manager**: Manages specific sites within a tenant
- **worker**: API access for worker processes

Admin accounts created by this script are always `system_admin` role.

## Database Requirements

The script will automatically create database tables if they don't exist. It requires:

- PostgreSQL connection configured via environment variables
- Database schema as defined in the Alembic migrations

## Environment Setup

Ensure these environment variables are set (usually in `.env`):

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=facedb
DB_USER=postgres
DB_PASSWORD=postgres
```

## Troubleshooting

### "No password supplied" error
Check that `DB_PASSWORD` environment variable is set.

### "User already exists" error
Use `make list-users` to see existing users, or choose a different username/email.

### "Database connection failed" error
Verify PostgreSQL is running and environment variables are correct.

### "Table does not exist" error
The script will create tables automatically, but ensure Alembic migrations are up to date.

## Examples

### First-time setup
```bash
# Start with empty database
make init-admin
# Follow prompts to create admin user

# Verify creation
make list-users
```

### Reset forgotten password
```bash
# Reset admin password
make reset-password username=admin password=newpassword123

# Or interactive mode
cd apps/api && bash scripts/init-admin.sh reset-password admin newpassword123
```

### Multiple admin accounts
```bash
# Create additional admin users
cd apps/api
python scripts/init_admin.py create \
  --username admin2 \
  --email admin2@example.com \
  --password password123 \
  --first-name "John" \
  --last-name "Doe"
```