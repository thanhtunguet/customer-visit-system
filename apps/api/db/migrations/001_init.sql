-- Minimal schema bootstrap; full Alembic setup to follow
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id text PRIMARY KEY,
  name text NOT NULL
);

-- Example tenant-scoped table
CREATE TABLE IF NOT EXISTS customers (
  tenant_id text NOT NULL,
  customer_id text NOT NULL,
  name text,
  gender text,
  first_seen timestamptz NOT NULL DEFAULT now(),
  last_seen timestamptz,
  PRIMARY KEY (tenant_id, customer_id)
);

-- RLS example (requires app.tenant_id setting)
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_customers_tenant ON customers;
CREATE POLICY p_customers_tenant ON customers
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

