-- Complete database schema with RLS for multi-tenant face recognition system

-- Core tenant table
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id text PRIMARY KEY,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Sites within a tenant
CREATE TABLE IF NOT EXISTS sites (
  tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  site_id text NOT NULL,
  name text NOT NULL,
  location text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, site_id)
);

-- Cameras at each site
CREATE TABLE IF NOT EXISTS cameras (
  tenant_id text NOT NULL,
  site_id text NOT NULL,
  camera_id text NOT NULL,
  name text NOT NULL,
  rtsp_url text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, site_id, camera_id),
  FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, site_id) ON DELETE CASCADE
);

-- Staff members with their face embeddings
CREATE TABLE IF NOT EXISTS staff (
  tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  staff_id text NOT NULL,
  name text NOT NULL,
  site_id text,
  is_active boolean NOT NULL DEFAULT true,
  face_embedding vector(512),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, staff_id)
);

-- Customer profiles
CREATE TABLE IF NOT EXISTS customers (
  tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  customer_id text NOT NULL,
  name text,
  gender text CHECK (gender IN ('male', 'female', 'unknown')),
  estimated_age_range text,
  first_seen timestamptz NOT NULL DEFAULT now(),
  last_seen timestamptz,
  visit_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, customer_id)
);

-- Visit records when someone is detected
CREATE TABLE IF NOT EXISTS visits (
  tenant_id text NOT NULL,
  visit_id text NOT NULL,
  person_id text NOT NULL, -- references either staff_id or customer_id
  person_type text NOT NULL CHECK (person_type IN ('staff', 'customer')),
  site_id text NOT NULL,
  camera_id text NOT NULL,
  timestamp timestamptz NOT NULL DEFAULT now(),
  confidence_score float NOT NULL,
  face_embedding vector(512),
  image_path text,
  bbox_x float,
  bbox_y float,
  bbox_w float,
  bbox_h float,
  PRIMARY KEY (tenant_id, visit_id),
  FOREIGN KEY (tenant_id, site_id, camera_id) REFERENCES cameras(tenant_id, site_id, camera_id)
);

-- API keys for worker authentication
CREATE TABLE IF NOT EXISTS api_keys (
  key_id text PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  hashed_key text NOT NULL,
  name text NOT NULL,
  role text NOT NULL DEFAULT 'worker',
  is_active boolean NOT NULL DEFAULT true,
  last_used timestamptz,
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Enable Row Level Security on all tenant-scoped tables
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

-- RLS Policies for sites
DROP POLICY IF EXISTS p_sites_tenant ON sites;
CREATE POLICY p_sites_tenant ON sites
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- RLS Policies for cameras
DROP POLICY IF EXISTS p_cameras_tenant ON cameras;
CREATE POLICY p_cameras_tenant ON cameras
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- RLS Policies for staff
DROP POLICY IF EXISTS p_staff_tenant ON staff;
CREATE POLICY p_staff_tenant ON staff
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- RLS Policies for customers
DROP POLICY IF EXISTS p_customers_tenant ON customers;
CREATE POLICY p_customers_tenant ON customers
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- RLS Policies for visits
DROP POLICY IF EXISTS p_visits_tenant ON visits;
CREATE POLICY p_visits_tenant ON visits
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- RLS Policies for api_keys
DROP POLICY IF EXISTS p_api_keys_tenant ON api_keys;
CREATE POLICY p_api_keys_tenant ON api_keys
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_visits_timestamp ON visits(tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_visits_person ON visits(tenant_id, person_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_visits_site ON visits(tenant_id, site_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_customers_last_seen ON customers(tenant_id, last_seen DESC);

-- Materialized view for hourly visitor stats
CREATE MATERIALIZED VIEW IF NOT EXISTS visitor_stats_hourly AS
SELECT 
  tenant_id,
  site_id,
  date_trunc('hour', timestamp) as hour_bucket,
  COUNT(*) as total_visits,
  COUNT(DISTINCT person_id) as unique_visitors,
  COUNT(CASE WHEN person_type = 'staff' THEN 1 END) as staff_visits,
  COUNT(CASE WHEN person_type = 'customer' THEN 1 END) as customer_visits
FROM visits 
GROUP BY tenant_id, site_id, date_trunc('hour', timestamp);

CREATE UNIQUE INDEX IF NOT EXISTS idx_visitor_stats_hourly_unique 
ON visitor_stats_hourly(tenant_id, site_id, hour_bucket);

