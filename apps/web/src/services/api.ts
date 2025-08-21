import axios, { AxiosInstance } from 'axios';
import { 
  Tenant, Site, Camera, Staff, Customer, Visit, VisitorReport, 
  AuthUser, LoginRequest, TokenResponse, CameraType,
  StaffFaceImage, StaffWithFaces, FaceRecognitionTestResult, WebcamInfo
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/v1`,
      timeout: 10000,
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.logout();
        }
        return Promise.reject(error);
      }
    );

    // Load token from localStorage
    const savedToken = localStorage.getItem('access_token');
    if (savedToken) {
      this.token = savedToken;
    }
  }

  // Auth methods
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>('/auth/token', {
      grant_type: 'password',
      ...credentials,
    });
    
    this.token = response.data.access_token;
    localStorage.setItem('access_token', this.token);
    
    return response.data;
  }

  logout(): void {
    this.token = null;
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  }

  async getCurrentUser(): Promise<AuthUser> {
    const response = await this.client.get<AuthUser>('/me');
    return response.data;
  }

  // Tenants (system admin only)
  async getTenants(): Promise<Tenant[]> {
    const response = await this.client.get<Tenant[]>('/tenants');
    return response.data;
  }

  async createTenant(tenant: Omit<Tenant, 'created_at'>): Promise<Tenant> {
    const response = await this.client.post<Tenant>('/tenants', tenant);
    return response.data;
  }

  // Sites
  async getSites(): Promise<Site[]> {
    const response = await this.client.get<Site[]>('/sites');
    return response.data;
  }

  async createSite(site: Omit<Site, 'tenant_id' | 'created_at'>): Promise<Site> {
    const response = await this.client.post<Site>('/sites', site);
    return response.data;
  }

  // Cameras
  async getCameras(siteId: string): Promise<Camera[]> {
    const response = await this.client.get<Camera[]>(`/sites/${siteId}/cameras`);
    return response.data;
  }

  async createCamera(
    siteId: string, 
    camera: Omit<Camera, 'tenant_id' | 'site_id' | 'camera_id' | 'created_at' | 'is_active'>
  ): Promise<Camera> {
    const response = await this.client.post<Camera>(`/sites/${siteId}/cameras`, camera);
    return response.data;
  }

  async getCamera(siteId: string, cameraId: number): Promise<Camera> {
    const response = await this.client.get<Camera>(`/sites/${siteId}/cameras/${cameraId}`);
    return response.data;
  }

  async updateCamera(
    siteId: string, 
    cameraId: number,
    camera: Omit<Camera, 'tenant_id' | 'site_id' | 'created_at' | 'is_active' | 'camera_id'>
  ): Promise<Camera> {
    const response = await this.client.put<Camera>(`/sites/${siteId}/cameras/${cameraId}`, camera);
    return response.data;
  }

  async deleteCamera(siteId: string, cameraId: number): Promise<void> {
    await this.client.delete(`/sites/${siteId}/cameras/${cameraId}`);
  }

  // Camera Streaming
  async startCameraStream(siteId: string, cameraId: number): Promise<{ message: string; camera_id: number; stream_active: boolean }> {
    const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/stream/start`);
    return response.data;
  }

  // Devices
  async getWebcams(): Promise<WebcamInfo[]> {
    const response = await this.client.get<WebcamInfo[]>('/devices/webcams');
    return response.data;
  }

  async stopCameraStream(siteId: string, cameraId: number): Promise<{ message: string; camera_id: number; stream_active: boolean }> {
    const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/stream/stop`);
    return response.data;
  }

  async getCameraStreamStatus(siteId: string, cameraId: number): Promise<{
    camera_id: number;
    stream_active: boolean;
    stream_info: {
      camera_id: number;
      is_active: boolean;
      camera_type: string;
      last_frame_time: number;
      error_count: number;
      queue_size: number;
    } | null;
  }> {
    const response = await this.client.get(`/sites/${siteId}/cameras/${cameraId}/stream/status`);
    return response.data;
  }

  getCameraStreamUrl(siteId: string, cameraId: number): string {
    const baseUrl = import.meta.env.VITE_API_URL || window.location.origin;
    const token = this.token || localStorage.getItem('access_token');
    const url = new URL(`${baseUrl}/v1/sites/${siteId}/cameras/${cameraId}/stream/feed`);
    if (token) {
      url.searchParams.set('access_token', token);
    }
    return url.toString();
  }

  // Staff
  async getStaff(): Promise<Staff[]> {
    const response = await this.client.get<Staff[]>('/staff');
    return response.data;
  }

  async createStaff(staff: Omit<Staff, 'tenant_id' | 'staff_id' | 'created_at' | 'is_active'>): Promise<Staff> {
    const response = await this.client.post<Staff>('/staff', staff);
    return response.data;
  }

  async getStaffMember(staffId: string): Promise<Staff> {
    const response = await this.client.get<Staff>(`/staff/${staffId}`);
    return response.data;
  }

  async updateStaff(
    staffId: string,
    staff: Omit<Staff, 'tenant_id' | 'created_at' | 'is_active' | 'staff_id'>
  ): Promise<Staff> {
    const response = await this.client.put<Staff>(`/staff/${staffId}`, staff);
    return response.data;
  }

  async deleteStaff(staffId: string): Promise<void> {
    await this.client.delete(`/staff/${staffId}`);
  }

  // Staff Face Images
  async getStaffFaceImages(staffId: string): Promise<StaffFaceImage[]> {
    const response = await this.client.get<StaffFaceImage[]>(`/staff/${staffId}/faces`);
    return response.data;
  }

  async getStaffWithFaces(staffId: string): Promise<StaffWithFaces> {
    const response = await this.client.get<StaffWithFaces>(`/staff/${staffId}/details`);
    return response.data;
  }

  async uploadStaffFaceImage(
    staffId: string, 
    imageData: string, 
    isPrimary: boolean = false
  ): Promise<StaffFaceImage> {
    const response = await this.client.post<StaffFaceImage>(`/staff/${staffId}/faces`, {
      image_data: imageData,
      is_primary: isPrimary
    });
    return response.data;
  }

  async deleteStaffFaceImage(staffId: string, imageId: string): Promise<void> {
    await this.client.delete(`/staff/${staffId}/faces/${imageId}`);
  }

  async recalculateFaceEmbedding(staffId: string, imageId: string): Promise<{
    message: string;
    processing_info: {
      face_count: number;
      confidence: number;
    };
  }> {
    const response = await this.client.put(`/staff/${staffId}/faces/${imageId}/recalculate`);
    return response.data;
  }

  async testFaceRecognition(staffId: string, testImage: string): Promise<FaceRecognitionTestResult> {
    const response = await this.client.post<FaceRecognitionTestResult>(
      `/staff/${staffId}/test-recognition`,
      { test_image: testImage }
    );
    return response.data;
  }

  // Customers
  async getCustomers(params?: { limit?: number; offset?: number }): Promise<Customer[]> {
    const response = await this.client.get<Customer[]>('/customers', { params });
    return response.data;
  }

  async createCustomer(customer: Omit<Customer, 'tenant_id' | 'customer_id' | 'first_seen' | 'last_seen' | 'visit_count'>): Promise<Customer> {
    const response = await this.client.post<Customer>('/customers', customer);
    return response.data;
  }

  async getCustomer(customerId: number): Promise<Customer> {
    const response = await this.client.get<Customer>(`/customers/${customerId}`);
    return response.data;
  }

  async updateCustomer(
    customerId: number,
    customer: Partial<Omit<Customer, 'tenant_id' | 'customer_id' | 'first_seen' | 'last_seen' | 'visit_count'>>
  ): Promise<Customer> {
    const response = await this.client.put<Customer>(`/customers/${customerId}`, customer);
    return response.data;
  }

  async deleteCustomer(customerId: number): Promise<void> {
    await this.client.delete(`/customers/${customerId}`);
  }

  // Visits
  async getVisits(params?: {
    site_id?: string;
    person_id?: string;
    start_time?: string;
    end_time?: string;
    limit?: number;
    offset?: number;
  }): Promise<Visit[]> {
    const response = await this.client.get<Visit[]>('/visits', { params });
    return response.data;
  }

  // Reports
  async getVisitorReport(params?: {
    site_id?: string;
    granularity?: 'hour' | 'day' | 'week' | 'month';
    start_date?: string;
    end_date?: string;
  }): Promise<VisitorReport[]> {
    const response = await this.client.get<VisitorReport[]>('/reports/visitors', { params });
    return response.data;
  }

  // Health check
  async getHealth(): Promise<{ status: string; env: string; timestamp: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Authenticated image loading
  async getImageUrl(imagePath: string): Promise<string> {
    try {
      // If imagePath already starts with /v1/files/, use it directly
      const url = imagePath.startsWith('/v1/files/') ? imagePath : `/v1/files/${imagePath}`;
      
      // Make authenticated request to get the image
      const response = await this.client.get(url, {
        responseType: 'blob',
      });
      
      // Create blob URL for the image
      const blob = response.data;
      return URL.createObjectURL(blob);
    } catch (error) {
      console.error('Failed to load authenticated image:', error);
      // Return a placeholder or fallback image URL
      return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+PC9zdmc+';
    }
  }
}

export const apiClient = new ApiClient();