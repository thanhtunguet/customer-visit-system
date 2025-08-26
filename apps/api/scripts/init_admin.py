#!/usr/bin/env python3
"""
Script to initialize or reset admin account for the face recognition system.
Usage:
    python scripts/init_admin.py --username admin --email admin@example.com --password newpassword
    python scripts/init_admin.py --reset-password admin newpassword
"""

import argparse
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import db
from app.models.database import User, UserRole, Base
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_tables():
    """Create all tables if they don't exist"""
    Base.metadata.create_all(bind=db.sync_engine)


def create_admin_user(username: str, email: str, password: str, first_name: str = "System", last_name: str = "Admin") -> bool:
    """Create a new system admin user"""
    session: Session = db.sync_session_maker()
    try:
        # Check if user already exists
        existing_user = session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            print(f"❌ User with username '{username}' or email '{email}' already exists!")
            print(f"   Existing user: {existing_user.username} ({existing_user.email})")
            return False
        
        # Create new admin user
        admin_user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.SYSTEM_ADMIN,
            tenant_id=None,  # System admin not tied to specific tenant
            is_active=True,
            is_email_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        admin_user.set_password(password)
        
        session.add(admin_user)
        session.commit()
        
        print(f"✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Role: {admin_user.role.value}")
        print(f"   User ID: {admin_user.user_id}")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error creating admin user: {e}")
        return False
    finally:
        session.close()


def reset_password(username: str, new_password: str) -> bool:
    """Reset password for existing user"""
    session: Session = db.sync_session_maker()
    try:
        # Find user
        user = session.query(User).filter(User.username == username).first()
        
        if not user:
            print(f"❌ User '{username}' not found!")
            return False
        
        # Reset password
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        
        session.commit()
        
        print(f"✅ Password reset successfully for user '{username}'!")
        print(f"   User ID: {user.user_id}")
        print(f"   Role: {user.role.value}")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error resetting password: {e}")
        return False
    finally:
        session.close()


def list_users():
    """List all existing users"""
    session: Session = db.sync_session_maker()
    try:
        users = session.query(User).all()
        
        if not users:
            print("📝 No users found in the system.")
            return
        
        print(f"📝 Found {len(users)} user(s):")
        print("-" * 80)
        for user in users:
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Name: {user.full_name}")
            print(f"Role: {user.role.value}")
            print(f"Active: {user.is_active}")
            print(f"Last Login: {user.last_login or 'Never'}")
            print(f"User ID: {user.user_id}")
            print("-" * 80)
            
    except Exception as e:
        print(f"❌ Error listing users: {e}")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Initialize or manage admin accounts')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create admin command
    create_parser = subparsers.add_parser('create', help='Create new admin user')
    create_parser.add_argument('--username', required=True, help='Admin username')
    create_parser.add_argument('--email', required=True, help='Admin email')
    create_parser.add_argument('--password', required=True, help='Admin password')
    create_parser.add_argument('--first-name', default='System', help='First name (default: System)')
    create_parser.add_argument('--last-name', default='Admin', help='Last name (default: Admin)')
    
    # Reset password command
    reset_parser = subparsers.add_parser('reset-password', help='Reset user password')
    reset_parser.add_argument('username', help='Username to reset password for')
    reset_parser.add_argument('password', help='New password')
    
    # List users command
    list_parser = subparsers.add_parser('list', help='List all users')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🔧 Initializing database connection...")
    
    try:
        # Ensure tables exist
        create_tables()
        print("✅ Database tables verified.")
        
        if args.command == 'create':
            success = create_admin_user(
                username=args.username,
                email=args.email,
                password=args.password,
                first_name=args.first_name,
                last_name=args.last_name
            )
            sys.exit(0 if success else 1)
            
        elif args.command == 'reset-password':
            success = reset_password(args.username, args.password)
            sys.exit(0 if success else 1)
            
        elif args.command == 'list':
            list_users()
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()