export interface Tenant {
  tenant_id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
}

export interface TenantCreate {
  tenant_id: string;
  name: string;
  description?: string;
}

export interface Site {
  site_id: number;
  tenant_id: string;
  name: string;
  location?: string;
  created_at: string;
}

export enum CameraType {
  RTSP = 'rtsp',
  WEBCAM = 'webcam'
}

export interface Camera {
  camera_id: number;
  tenant_id: string;
  site_id: number;
  name: string;
  camera_type: CameraType;
  rtsp_url?: string;
  device_index?: number;
  is_active: boolean;
  created_at: string;
}

export interface WebcamInfo {
  device_index: number;
  width?: number;
  height?: number;
  fps?: number;
  backend?: string;
  is_working: boolean;
  frame_captured: boolean;
  in_use: boolean;
  in_use_by?: string;
}

export interface Staff {
  staff_id: number;
  tenant_id: string;
  name: string;
  site_id?: number;
  is_active: boolean;
  created_at: string;
}

export interface Customer {
  customer_id: number;
  tenant_id: string;
  name?: string;
  gender?: string;
  estimated_age_range?: string;
  phone?: string;
  email?: string;
  first_seen: string;
  last_seen?: string;
  visit_count: number;
}

export interface Visit {
  tenant_id: string;
  visit_id: string;
  person_id: number;
  person_type: 'staff' | 'customer';
  site_id: number;
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

export interface StaffFaceImage {
  tenant_id: string;
  image_id: string;
  staff_id: number;
  image_path: string;
  face_landmarks?: number[][];  // 5-point landmarks
  is_primary: boolean;
  created_at: string;
}

export interface StaffWithFaces extends Staff {
  face_images: StaffFaceImage[];
}

export interface FaceRecognitionMatch {
  staff_id: number;
  staff_name: string;
  similarity: number;
  image_id?: string;
}

export interface FaceRecognitionTestResult {
  matches: FaceRecognitionMatch[];
  best_match?: FaceRecognitionMatch;
  processing_info: {
    test_face_detected: boolean;
    test_confidence: number;
    total_staff_compared: number;
  };
}

// Create interfaces without auto-generated IDs
export interface SiteCreate {
  name: string;
  location?: string;
}

export interface StaffCreate {
  name: string;
  site_id?: number;
  face_embedding?: number[];
}

export interface CustomerCreate {
  name?: string;
  gender?: string;
  estimated_age_range?: string;
  phone?: string;
  email?: string;
}

export interface CameraCreate {
  name: string;
  camera_type: CameraType;
  rtsp_url?: string;
  device_index?: number;
}

// ===============================
// User Management Types
// ===============================

export enum UserRole {
  SYSTEM_ADMIN = 'SYSTEM_ADMIN',
  TENANT_ADMIN = 'TENANT_ADMIN',
  SITE_MANAGER = 'SITE_MANAGER',
  WORKER = 'WORKER'
}

export interface User {
  user_id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  tenant_id?: string;
  is_active: boolean;
  is_email_verified: boolean;
  last_login?: string;
  password_changed_at: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  role: UserRole;
  tenant_id?: string;
  is_active?: boolean;
}

export interface UserUpdate {
  username?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  role?: UserRole;
  tenant_id?: string;
  is_active?: boolean;
}

export interface UserPasswordUpdate {
  current_password?: string;
  new_password: string;
}