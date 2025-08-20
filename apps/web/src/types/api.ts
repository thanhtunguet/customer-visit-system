export interface Tenant {
  tenant_id: string;
  name: string;
  created_at: string;
}

export interface Site {
  tenant_id: string;
  site_id: string;
  name: string;
  location?: string;
  created_at: string;
}

export enum CameraType {
  RTSP = 'rtsp',
  WEBCAM = 'webcam'
}

export interface Camera {
  tenant_id: string;
  site_id: string;
  camera_id: number;
  name: string;
  camera_type: CameraType;
  rtsp_url?: string;
  device_index?: number;
  is_active: boolean;
  created_at: string;
}

export interface Staff {
  tenant_id: string;
  staff_id: number;
  name: string;
  site_id?: string;
  is_active: boolean;
  created_at: string;
}

export interface Customer {
  tenant_id: string;
  customer_id: number;
  name?: string;
  gender?: string;
  first_seen: string;
  last_seen?: string;
  visit_count: number;
}

export interface Visit {
  tenant_id: string;
  visit_id: string;
  person_id: number;
  person_type: 'staff' | 'customer';
  site_id: string;
  camera_id: number;
  timestamp: string;
  confidence_score: number;
  image_path?: string;
}

export interface VisitorReport {
  period: string;
  total_visits: number;
  unique_visitors: number;
  staff_visits: number;
  customer_visits: number;
}

export interface AuthUser {
  sub: string;
  role: string;
  tenant_id: string;
}

export interface LoginRequest {
  username: string;
  password: string;
  tenant_id: string;
  role?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}