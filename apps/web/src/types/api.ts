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
  tenant_id: string;
  staff_id: string;
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

export interface StaffFaceImage {
  tenant_id: string;
  image_id: string;
  staff_id: string;
  image_path: string;
  face_landmarks?: number[][];  // 5-point landmarks
  is_primary: boolean;
  created_at: string;
}

export interface StaffWithFaces extends Staff {
  face_images: StaffFaceImage[];
}

export interface FaceRecognitionMatch {
  staff_id: string;
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