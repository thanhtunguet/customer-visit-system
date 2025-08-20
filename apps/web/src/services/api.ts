import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { 
  Tenant, Site, Camera, Staff, Customer, Visit, VisitorReport, 
  AuthUser, LoginRequest, TokenResponse, CameraType,
  StaffFaceImage, StaffWithFaces, FaceRecognitionTestResult
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

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
}

export const apiClient = new ApiClient();