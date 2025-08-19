export type FaceDetectedEvent = {
  tenant_id: string;
  site_id: string;
  camera_id: string;
  timestamp: string; // ISO
  embedding: number[]; // 512
  bbox: number[]; // [x,y,w,h]
  snapshot_url?: string | null;
  is_staff_local?: boolean;
};

export type VisitRecord = {
  tenant_id: string;
  site_id: string;
  person_id: string;
  timestamp: string;
  confidence: number;
  image_path?: string | null;
};

export type CustomerProfile = {
  tenant_id: string;
  customer_id: string;
  name?: string | null;
  gender?: "male" | "female" | "other" | null;
  first_seen: string;
  last_seen?: string | null;
};

