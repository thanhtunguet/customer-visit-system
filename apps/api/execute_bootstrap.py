#!/usr/bin/env python3
import sys

sys.path.insert(0, ".")

try:
    from app.core.config import settings
    from sqlalchemy import create_engine, text

    # Get database URL and convert to sync version
    db_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    print(f"Connecting to: {db_url}")

    # Create engine
    engine = create_engine(db_url)

    # Execute the SQL commands
    with engine.connect() as conn:
        # Insert tenant
        result = conn.execute(
            text(
                """
            INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
            VALUES ('t-dev', 'Development Tenant', 'Development tenant for workers', true, NOW(), NOW())
            ON CONFLICT (tenant_id) DO UPDATE SET
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at
        """
            )
        )
        print("Tenant created/updated")

        # Insert API key
        result = conn.execute(
            text(
                """
            INSERT INTO api_keys (tenant_id, hashed_key, name, role, is_active, created_at)
            VALUES ('t-dev', '298754db2dbab6ec62605ceb0379eb7ee376580359449efe0caa3aa06cd56736', 'worker-dev-key', 'worker', true, NOW())
            ON CONFLICT (tenant_id, hashed_key) DO NOTHING
        """
            )
        )
        print("API key created")

        # Verify
        result = conn.execute(
            text("SELECT tenant_id, name FROM tenants WHERE tenant_id = 't-dev'")
        )
        tenant_row = result.fetchone()
        print(f"Tenant verified: {tenant_row}")

        result = conn.execute(
            text(
                """
            SELECT name, role FROM api_keys 
            WHERE tenant_id = 't-dev' AND hashed_key = '298754db2dbab6ec62605ceb0379eb7ee376580359449efe0caa3aa06cd56736'
        """
            )
        )
        api_key_row = result.fetchone()
        print(f"API key verified: {api_key_row}")

        # Commit the transaction
        conn.commit()

    print("\n✅ Bootstrap completed successfully!")
    print("API Key: dev-secret")
    print("Tenant ID: t-dev")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
