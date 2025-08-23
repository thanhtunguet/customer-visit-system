#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '.')

from passlib.context import CryptContext
import uuid

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Generate hash for admin123
password = "admin123"
password_hash = pwd_context.hash(password)

print(f"Password: {password}")
print(f"Generated hash: {password_hash}")

# Test the hash
verification = pwd_context.verify(password, password_hash)
print(f"Verification test: {verification}")

# Generate user ID
user_id = f"admin-{str(uuid.uuid4())[:8]}"

# Print SQL to insert the user
sql = f"""
INSERT INTO users (
    user_id, username, email, first_name, last_name, 
    password_hash, role, is_active, is_email_verified, 
    password_changed_at, created_at, updated_at
) VALUES (
    '{user_id}',
    'admin',
    'admin@system.local',
    'System',
    'Administrator',
    '{password_hash}',
    'SYSTEM_ADMIN',
    true,
    true,
    NOW(),
    NOW(),
    NOW()
);
"""

print("\nSQL to insert admin user:")
print(sql)