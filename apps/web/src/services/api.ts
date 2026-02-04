import axios, { AxiosInstance } from 'axios';
import { 
  Tenant, Site, Camera, Staff, Customer, Visit, VisitorReport, 
  AuthUser, LoginRequest, TokenResponse,
  StaffFaceImage, StaffWithFaces, FaceRecognitionTestResult, WebcamInfo,
  SiteCreate, CameraCreate, TenantCreate,
  User, UserCreate, UserUpdate, UserPasswordUpdate,
  ApiKey, ApiKeyCreate, ApiKeyCreateResponse, ApiKeyUpdate
} from '../types/api';
import { getTenantIdFromToken, isTokenExpired } from '../utils/jwt';

// Force use of window.location.origin in development to use Vite proxy
const API_BASE_URL = import.meta.env.DEV ? window.location.origin : (import.meta.env.VITE_API_URL || window.location.origin);

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;
  private currentTenantId: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/v1`,
      timeout: 30000, // Increased timeout for file uploads
    });

    // Request interceptor to add auth token and tenant context
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        if (this.currentTenantId) {
          config.headers['X-Tenant-ID'] = this.currentTenantId;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // Don't auto-logout on login endpoint 401s - let the login form handle it
        if (error.response?.status === 401 && !error.config?.url?.includes('/auth/token')) {
          this.logout();
        }
        return Promise.reject(error);
      }
    );

    // Load token and sync tenant context from token
    const savedToken = localStorage.getItem('access_token');
    if (savedToken && !isTokenExpired(savedToken)) {
      this.token = savedToken;
      this.syncTenantContextFromToken();
    } else if (savedToken) {
      // Token expired, clean up
      this.logout();
    }
  }

  get baseURL(): string {
    return this.client.defaults.baseURL || `${API_BASE_URL}/v1`;
  }

  // Auth methods
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>('/auth/token', {
      grant_type: 'password',
      ...credentials,
    });
    
    this.token = response.data.access_token;
    localStorage.setItem('access_token', this.token);
    
    // Sync tenant context from token (more reliable than credentials)
    this.syncTenantContextFromToken();
    
    return response.data;
  }

  async switchView(targetTenantId: string | null): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>('/auth/switch-view', {
      target_tenant_id: targetTenantId,
    });
    
    // Update token and sync tenant context from new token
    this.token = response.data.access_token;
    localStorage.setItem('access_token', this.token);
    this.syncTenantContextFromToken();
    
    return response.data;
  }

  logout(): void {
    this.token = null;
    this.currentTenantId = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('current_tenant_id');
    window.location.href = '/login';
  }

  // Tenant context management
  setCurrentTenant(tenantId: string | null): void {
    this.currentTenantId = tenantId;
    // Store in localStorage for persistence
    if (tenantId) {
      localStorage.setItem('current_tenant_id', tenantId);
    } else {
      localStorage.setItem('current_tenant_id', 'null'); // Store 'null' string for global view
    }
  }

  getCurrentTenant(): string | null {
    // If currentTenantId is not set, try to get it from localStorage
    if (this.currentTenantId === undefined || this.currentTenantId === null) {
      const stored = localStorage.getItem('current_tenant_id');
      if (stored === 'null') {
        this.currentTenantId = null; // Global view
      } else if (stored) {
        this.currentTenantId = stored; // Specific tenant
      } else {
        this.currentTenantId = null; // Default to global view
      }
    }
    return this.currentTenantId;
  }

  // Sync tenant context from JWT token
  private syncTenantContextFromToken(): void {
    if (!this.token) {
      this.currentTenantId = null;
      localStorage.removeItem('current_tenant_id');
      return;
    }
    
    const tenantId = getTenantIdFromToken(this.token);
    this.currentTenantId = tenantId;
    
    // Always store the tenant context (null for global view, tenantId for tenant view)
    if (tenantId) {
      localStorage.setItem('current_tenant_id', tenantId);
    } else {
      localStorage.setItem('current_tenant_id', 'null'); // Store 'null' string for global view
    }
  }

  async getCurrentUser(): Promise<AuthUser> {
    const response = await this.client.get<AuthUser>('/me');
    return response.data;
  }

  async changeMyPassword(passwordData: { current_password: string; new_password: string }): Promise<{ message: string }> {
    const response = await this.client.put<{ message: string }>('/me/password', passwordData);
    return response.data;
  }

  // Tenants (system admin only)
  async getTenants(): Promise<Tenant[]> {
    const response = await this.client.get<Tenant[]>('/tenants');
    return response.data;
  }

  async createTenant(tenant: TenantCreate): Promise<Tenant> {
    const response = await this.client.post<Tenant>('/tenants', tenant);
    return response.data;
  }

  async getTenant(tenantId: string): Promise<Tenant> {
    const response = await this.client.get<Tenant>(`/tenants/${tenantId}`);
    return response.data;
  }

  async updateTenant(tenantId: string, tenant: Partial<TenantCreate>): Promise<Tenant> {
    const response = await this.client.put<Tenant>(`/tenants/${tenantId}`, tenant);
    return response.data;
  }

  async deleteTenant(tenantId: string): Promise<void> {
    await this.client.delete(`/tenants/${tenantId}`);
  }

  async toggleTenantStatus(tenantId: string, isActive: boolean): Promise<Tenant> {
    const response = await this.client.patch<Tenant>(`/tenants/${tenantId}/status`, {
      is_active: isActive
    });
    return response.data;
  }

  // Sites
  async getSites(): Promise<Site[]> {
    const response = await this.client.get<Site[]>('/sites');
    return response.data;
  }

  async createSite(site: SiteCreate): Promise<Site> {
    const response = await this.client.post<Site>('/sites', site);
    return response.data;
  }

  async updateSite(siteId: number, site: Partial<SiteCreate>): Promise<Site> {
    const response = await this.client.put<Site>(`/sites/${siteId}`, site);
    return response.data;
  }

  async deleteSite(siteId: number): Promise<void> {
    await this.client.delete(`/sites/${siteId}`);
  }

  // Cameras
  async getCameras(siteId: number): Promise<Camera[]> {
    const response = await this.client.get<Camera[]>(`/sites/${siteId}/cameras`);
    return response.data;
  }

  async createCamera(
    siteId: number, 
    camera: CameraCreate
  ): Promise<Camera> {
    const response = await this.client.post<Camera>(`/sites/${siteId}/cameras`, camera);
    return response.data;
  }

  async getCamera(siteId: number, cameraId: number): Promise<Camera> {
    const response = await this.client.get<Camera>(`/sites/${siteId}/cameras/${cameraId}`);
    return response.data;
  }

  async updateCamera(
    siteId: number, 
    cameraId: number,
    camera: CameraCreate
  ): Promise<Camera> {
    const response = await this.client.put<Camera>(`/sites/${siteId}/cameras/${cameraId}`, camera);
    return response.data;
  }

  async deleteCamera(siteId: number, cameraId: number): Promise<void> {
    await this.client.delete(`/sites/${siteId}/cameras/${cameraId}`);
  }

  // Camera Streaming
  async startCameraStream(siteId: number, cameraId: number): Promise<{ message: string; camera_id: number; stream_active: boolean }> {
    const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/stream/start`);
    return response.data;
  }

  // Devices
  async getWebcams(siteId?: number): Promise<{
    devices: WebcamInfo[];
    source: 'workers' | 'none';
    worker_sources: string[];
    manual_input_required: boolean;
    message: string;
  }> {
    const params = siteId ? { site_id: siteId } : {};
    const response = await this.client.get('/devices/webcams', { params });
    return response.data;
  }

  async stopCameraStream(siteId: number | string, cameraId: number): Promise<{ message: string; camera_id: number; stream_active: boolean }> {
    const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/stream/stop`);
    return response.data;
  }

  async getCameraStreamStatus(siteId: number | string, cameraId: number): Promise<{
    camera_id: number;
    stream_active: boolean;
    processing_active?: boolean;
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

  getCameraStreamUrl(siteId: number | string, cameraId: number): string {
    const baseUrl = import.meta.env.DEV ? window.location.origin : (import.meta.env.VITE_API_URL || window.location.origin);
    const token = this.token || localStorage.getItem('access_token');
    const url = new URL(`${baseUrl}/v1/sites/${siteId}/cameras/${cameraId}/stream/feed`);
    if (token) {
      url.searchParams.set('access_token', token);
    }
    return url.toString();
  }

  getWorkerWebSocketUrl(tenantId: string): string {
    const baseUrl = import.meta.env.DEV ? window.location.origin : (import.meta.env.VITE_API_URL || window.location.origin);
    const token = this.token || localStorage.getItem('access_token');
    
    // Convert HTTP(S) URL to WebSocket URL
    const wsProtocol = baseUrl.startsWith('https:') ? 'wss:' : 'ws:';
    const wsBaseUrl = baseUrl.replace(/^https?:/, wsProtocol);
    
    const url = new URL(`${wsBaseUrl}/v1/workers/ws/${tenantId}`);
    if (token) {
      url.searchParams.set('token', token);
    }
    return url.toString();
  }

  // Camera Processing Control
  async startCameraProcessing(siteId: number, cameraId: number): Promise<{ message: string; camera_id: number; worker_id: string; command_id: string; processing_active: boolean }> {
    const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/processing/start`);
    return response.data;
  }

  async stopCameraProcessing(siteId: number, cameraId: number): Promise<{ message: string; camera_id: number; worker_id: string; command_id: string; processing_active: boolean }> {
    const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/processing/stop`);
    return response.data;
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
    staffId: number | string,
    staff: Omit<Staff, 'tenant_id' | 'created_at' | 'is_active' | 'staff_id'>
  ): Promise<Staff> {
    const response = await this.client.put<Staff>(`/staff/${staffId}`, staff);
    return response.data;
  }

  async deleteStaff(staffId: number | string): Promise<void> {
    await this.client.delete(`/staff/${staffId}`);
  }

  // Staff Face Images
  async getStaffFaceImages(staffId: number | string): Promise<StaffFaceImage[]> {
    const response = await this.client.get<StaffFaceImage[]>(`/staff/${staffId}/faces`);
    return response.data;
  }

  async getStaffWithFaces(staffId: number | string): Promise<StaffWithFaces> {
    const response = await this.client.get<StaffWithFaces>(`/staff/${staffId}/details`);
    return response.data;
  }

  async uploadStaffFaceImage(
    staffId: number | string, 
    imageData: string, 
    isPrimary: boolean = false
  ): Promise<StaffFaceImage> {
    const response = await this.client.post<StaffFaceImage>(`/staff/${staffId}/faces`, {
      image_data: imageData,
      is_primary: isPrimary
    }, {
      timeout: 45000, // 45 second timeout for individual uploads
    });
    return response.data;
  }

  async uploadMultipleStaffFaceImages(
    staffId: string, 
    imageDataArray: string[]
  ): Promise<StaffFaceImage[]> {
    const response = await this.client.post<StaffFaceImage[]>(`/staff/${staffId}/faces/bulk`, {
      images: imageDataArray.map((imageData, index) => ({
        image_data: imageData,
        is_primary: index === 0 // First image is primary if no existing images
      }))
    }, {
      timeout: Math.max(60000, imageDataArray.length * 20000), // Dynamic timeout based on number of images
    });
    return response.data;
  }

  async deleteStaffFaceImage(staffId: number | string, imageId: string): Promise<void> {
    await this.client.delete(`/staff/${staffId}/faces/${imageId}`);
  }

  async recalculateFaceEmbedding(staffId: number | string, imageId: string): Promise<{
    message: string;
    processing_info: {
      face_count: number;
      confidence: number;
    };
  }> {
    const response = await this.client.put(`/staff/${staffId}/faces/${imageId}/recalculate`);
    return response.data;
  }

  async testFaceRecognition(staffId: number | string, testImage: string): Promise<FaceRecognitionTestResult> {
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

  async bulkDeleteCustomers(customerIds: number[]): Promise<{
    message: string;
    deleted_customers: number;
    customer_ids: number[];
    deleted_visits: number;
    deleted_face_images: number;
    failed_embedding_cleanups: number[];
  }> {
    const response = await this.client.post('/customers/bulk-delete', {
      customer_ids: customerIds
    });
    return response.data;
  }

  async getCustomerFaceImages(customerId: number): Promise<{
    customer_id: number;
    total_images: number;
    images: Array<{
      image_id: number;  // Fixed: should be number, not string
      image_path: string;
      confidence_score: number;
      quality_score: number;
      created_at: string;
      visit_id?: string;
      face_bbox?: number[];
      detection_metadata?: Record<string, unknown>;
    }>;
  }> {
    const response = await this.client.get(`/customers/${customerId}/face-images`);
    return response.data;
  }

  async deleteCustomerFaceImagesBatch(customerId: number, imageIds: number[]): Promise<{
    message: string;
    deleted_count: number;
    requested_count: number;
  }> {
    const response = await this.client.post(`/customers/${customerId}/face-images/batch-delete`, {
      image_ids: imageIds
    });
    return response.data;
  }

  async backfillCustomerFaceImages(customerId: number): Promise<{
    message: string;
    customer_id: number;
    visits_processed: number;
    total_visits_found: number;
  }> {
    const response = await this.client.post(`/customers/${customerId}/face-images/backfill`);
    return response.data;
  }

  // Customer Data Cleanup
  async findSimilarCustomers(customerId: number, params?: {
    threshold?: number;
    limit?: number;
  }): Promise<{
    customer_id: number;
    customer_name?: string;
    similar_customers: Array<{
      customer_id: number;
      name?: string;
      visit_count: number;
      first_seen?: string;
      last_seen?: string;
      max_similarity: number;
      gender?: string;
      estimated_age_range?: string;
    }>;
    threshold_used: number;
    total_found: number;
  }> {
    const response = await this.client.get(`/customers/${customerId}/similar`, { params });
    return response.data;
  }

  async mergeCustomers(primaryCustomerId: number, secondaryCustomerId: number, notes?: string): Promise<{
    message: string;
    primary_customer_id: number;
    secondary_customer_id: number;
    merged_visits: number;
    merged_face_images: number;
    new_visit_count: number;
    merge_notes?: string;
  }> {
    const response = await this.client.post('/customers/merge', {
      primary_customer_id: primaryCustomerId,
      secondary_customer_id: secondaryCustomerId,
      notes
    });
    return response.data;
  }

  async bulkMergeCustomers(mergeOperations: Array<{
    primary_customer_id: number;
    secondary_customer_ids: number[];
  }>): Promise<{
    message: string;
    job_id: string;
    status: string;
    total_operations: number;
    total_customers: number;
    check_status_url: string;
  }> {
    const response = await this.client.post('/customers/bulk-merge', {
      merges: mergeOperations
    });
    return response.data;
  }

  async reassignVisit(visitId: string, newCustomerId: number, update_embeddings: boolean = true): Promise<{
    message: string;
    visit_id: string;
    old_customer_id: number;
    new_customer_id: number;
    old_customer_remaining_visits: number;
    new_customer_total_visits: number;
    embedding_action: string;
  }> {
    const response = await this.client.post('/customers/reassign-visit', {
      visit_id: visitId,
      new_customer_id: newCustomerId,
      update_embeddings,
    });
    return response.data;
  }

  async reassignFaceImage(imageId: number, newCustomerId: number): Promise<{
    message: string;
    image_id: number;
    new_customer_id: number;
  }> {
    const response = await this.client.post('/customers/reassign-face-image', {
      image_id: imageId,
      new_customer_id: newCustomerId,
    });
    return response.data;
  }

  async cleanupLowConfidenceFaces(customerId: number, params?: {
    min_confidence?: number;
    max_to_remove?: number;
  }): Promise<{
    message: string;
    customer_id: number;
    removed_count: number;
    min_confidence_threshold: number;
  }> {
    const response = await this.client.post(`/customers/${customerId}/cleanup-low-confidence-faces`, params || {});
    return response.data;
  }

  // Visits
  async getVisits(params?: {
    site_id?: string;
    person_id?: string;
    start_time?: string;
    end_time?: string;
    limit?: number;
    cursor?: string;
  }): Promise<{
    visits: Visit[];
    has_more: boolean;
    next_cursor?: string;
  }> {
    const response = await this.client.get<{
      visits: Visit[];
      has_more: boolean;
      next_cursor?: string;
    }>('/visits', { params });
    return response.data;
  }

  async deleteVisits(visitIds: string[]): Promise<{
    message: string;
    deleted_count: number;
    deleted_visit_ids: string[];
    images_cleaned?: number;
  }> {
    const response = await this.client.post<{
      message: string;
      deleted_count: number;
      deleted_visit_ids: string[];
      images_cleaned?: number;
    }>('/visits/delete', {
      visit_ids: visitIds
    });
    return response.data;
  }

  async mergeVisits(visitIds: string[], primaryVisitId?: string): Promise<{
    message: string;
    primary_visit_id: string;
    merged_visit_ids: string[];
    person_id: number;
    person_type: 'customer' | 'staff';
    site_id: number;
    camera_ids: number[];
    first_seen: string;
    last_seen: string;
    visit_duration_seconds: number;
    detection_count: number;
    highest_confidence: number;
  }> {
    const response = await this.client.post('/visits/merge', {
      visit_ids: visitIds,
      primary_visit_id: primaryVisitId,
    });
    return response.data;
  }

  async removeVisitFaceDetection(visitId: string): Promise<{
    message: string;
    visit_id: string;
    customer_id?: number;
    images_cleaned: number;
    embedding_cleaned: boolean;
  }> {
    const response = await this.client.delete(`/visits/${visitId}/face`);
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

  async getDemographicsReport(params?: {
    site_id?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<{
    visitor_type: Array<{ name: string; value: number; color: string }>;
    gender: Array<{ name: string; value: number; color: string }>;
    age_groups: Array<{ group: string; count: number; percentage: number }>;
    summary: {
      total_visits: number;
      unique_visitors: number;
      repeat_visitors: number;
      customer_visits: number;
      staff_visits: number;
    };
    note: string;
  }> {
    const response = await this.client.get('/reports/demographics', { params });
    return response.data;
  }

  // Health check
  async getHealth(): Promise<{ status: string; env: string; timestamp: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // User Management (System Admin only)
  async getUsers(skip: number = 0, limit: number = 100): Promise<User[]> {
    const response = await this.client.get<User[]>('/users', {
      params: { skip, limit }
    });
    return response.data;
  }

  async createUser(userData: UserCreate): Promise<User> {
    const response = await this.client.post<User>('/users', userData);
    return response.data;
  }

  async getUser(userId: string): Promise<User> {
    const response = await this.client.get<User>(`/users/${userId}`);
    return response.data;
  }

  async updateUser(userId: string, userData: UserUpdate): Promise<User> {
    const response = await this.client.put<User>(`/users/${userId}`, userData);
    return response.data;
  }

  async changeUserPassword(userId: string, passwordData: UserPasswordUpdate): Promise<{ message: string }> {
    const response = await this.client.put<{ message: string }>(`/users/${userId}/password`, passwordData);
    return response.data;
  }

  async deleteUser(userId: string): Promise<{ message: string }> {
    const response = await this.client.delete<{ message: string }>(`/users/${userId}`);
    return response.data;
  }

  async toggleUserStatus(userId: string): Promise<User> {
    const response = await this.client.put<User>(`/users/${userId}/toggle-status`);
    return response.data;
  }

  // API Key Management
  async getApiKeys(): Promise<ApiKey[]> {
    const response = await this.client.get<ApiKey[]>('/api-keys');
    return response.data;
  }

  async createApiKey(data: ApiKeyCreate): Promise<ApiKeyCreateResponse> {
    const response = await this.client.post<ApiKeyCreateResponse>('/api-keys', data);
    return response.data;
  }

  async getApiKey(keyId: string): Promise<ApiKey> {
    const response = await this.client.get<ApiKey>(`/api-keys/${keyId}`);
    return response.data;
  }

  async updateApiKey(keyId: string, data: ApiKeyUpdate): Promise<ApiKey> {
    const response = await this.client.put<ApiKey>(`/api-keys/${keyId}`, data);
    return response.data;
  }

  async deleteApiKey(keyId: string): Promise<void> {
    await this.client.delete(`/api-keys/${keyId}`);
  }

  // Workers Management
  async getWorkers(params?: {
    status?: string;
    site_id?: number;
    include_offline?: boolean;
  }): Promise<{
    workers: Array<{
      worker_id: string;
      tenant_id: string;
      hostname: string;
      ip_address?: string;
      worker_name: string;
      worker_version?: string;
      capabilities?: Record<string, unknown>;
      status: 'idle' | 'processing' | 'online' | 'offline' | 'error' | 'maintenance';
      site_id?: number;
      camera_id?: number;
      last_heartbeat?: string;
      last_error?: string;
      error_count: number;
      total_faces_processed: number;
      uptime_minutes?: number;
      registration_time: string;
      is_healthy: boolean;
    }>;
    total_count: number;
    online_count: number;
    offline_count: number;
    error_count: number;
  }> {
    const response = await this.client.get('/workers', { params });
    return response.data;
  }

  async getWorker(workerId: string): Promise<{
    worker_id: string;
    tenant_id: string;
    hostname: string;
    ip_address?: string;
    worker_name: string;
    worker_version?: string;
    capabilities?: Record<string, unknown>;
    status: 'idle' | 'processing' | 'online' | 'offline' | 'error' | 'maintenance';
    site_id?: number;
    camera_id?: number;
    last_heartbeat?: string;
    last_error?: string;
    error_count: number;
    total_faces_processed: number;
    uptime_minutes?: number;
    registration_time: string;
    is_healthy: boolean;
  }> {
    const response = await this.client.get(`/workers/${workerId}`);
    return response.data;
  }

  async deleteWorker(workerId: string): Promise<{ message: string }> {
    const response = await this.client.delete(`/workers/${workerId}`);
    return response.data;
  }

  async cleanupStaleWorkers(ttlSeconds: number = 300): Promise<{ 
    message: string; 
    ttl_seconds: number; 
    removed_count: number 
  }> {
    const response = await this.client.post('/workers/cleanup-stale', { ttl_seconds: ttlSeconds });
    return response.data;
  }

  // WebRTC Session Management
  async startWebRTCSession(data: {
    session_id: string;
    client_id: string;
    camera_id: number;
    site_id: number;
  }): Promise<{
    session_id: string;
    status: string;
    message: string;
    client_id: string;
    camera_id: number;
    site_id: number;
  }> {
    const response = await this.client.post('/webrtc/sessions/start', data);
    return response.data;
  }

  async stopWebRTCSession(sessionId: string): Promise<{
    session_id: string;
    status: string;
    message: string;
  }> {
    const response = await this.client.post(`/webrtc/sessions/${sessionId}/stop`);
    return response.data;
  }

  async getWebRTCSession(sessionId: string): Promise<{
    session: {
      session_id: string;
      client_id: string;
      worker_id: string;
      camera_id: number;
      site_id: number;
      status: string;
      created_at: string;
      offer_received: boolean;
      answer_received: boolean;
    };
    timestamp: string;
  }> {
    const response = await this.client.get(`/webrtc/sessions/${sessionId}`);
    return response.data;
  }

  async listWebRTCSessions(): Promise<{
    sessions: Array<{
      session_id: string;
      client_id: string;
      worker_id: string;
      camera_id: number;
      site_id: number;
      status: string;
      created_at: string;
      offer_received: boolean;
      answer_received: boolean;
    }>;
    total_count: number;
    tenant_id: string;
    timestamp: string;
  }> {
    const response = await this.client.get('/webrtc/sessions');
    return response.data;
  }

  // Enhanced Streaming Status APIs
  async getSiteStreamingStatus(siteId: number): Promise<{
    site_id: number;
    total_cameras: number;
    cameras: Array<{
      camera_id: number;
      camera_name: string;
      camera_type: string;
      is_active: boolean;
      stream_active: boolean;
      assigned_worker_id?: string;
      worker_status: string;
      worker_healthy: boolean;
      last_status_check?: string;
      source: string;
    }>;
    workers: Record<string, {
      worker_id: string;
      worker_name: string;
      hostname: string;
      status: string;
      is_healthy: boolean;
      last_heartbeat: string;
      assigned_cameras: number[];
      active_camera_streams: string[];
      total_active_streams: number;
    }>;
    streaming_summary: {
      total_active_streams: number;
      total_assigned_cameras: number;
      cameras_without_workers: number;
      workers_with_issues: number;
    };
  }> {
    const response = await this.client.get(`/sites/${siteId}/streaming/status`);
    return response.data;
  }

  async getStreamingOverview(): Promise<{
    tenant_id: string;
    total_workers: number;
    workers: Array<{
      worker_id: string;
      worker_name: string;
      hostname: string;
      status: string;
      is_healthy: boolean;
      last_heartbeat: string;
      site_id?: number;
      assigned_camera_id?: number;
      active_camera_streams: string[];
      total_active_streams: number;
    }>;
    camera_assignments: Record<string, {
      camera_id: number;
      worker_id: string;
      worker_name: string;
      worker_status: string;
      is_healthy: boolean;
      site_id: number;
      assigned_at: string;
    }>;
    summary: {
      healthy_workers: number;
      active_workers: number;
      total_assigned_cameras: number;
      total_active_streams: number;
      workers_with_active_streams: number;
    };
  }> {
    const response = await this.client.get('/streaming/status-overview');
    return response.data;
  }

  // Process uploaded images for face recognition
  async processUploadedImages(images: File[], siteId: number): Promise<{
    results: Array<{
      success: boolean;
      customer_id?: number;
      customer_name?: string;
      confidence?: number;
      is_new_customer?: boolean;
      error?: string;
    }>;
    total_processed: number;
    successful_count: number;
    failed_count: number;
    new_customers_count: number;
    recognized_count: number;
  }> {
    const formData = new FormData();
    
    // Add all images
    images.forEach((image) => {
      formData.append('images', image);
    });
    
    // Add site ID
    formData.append('site_id', siteId.toString());
    
    const response = await this.client.post('/events/process-images', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: Math.max(60000, images.length * 10000), // Dynamic timeout based on number of images
    });
    return response.data;
  }

  // Background Job Management
  async getJobStatus(jobId: string): Promise<{
    job_id: string;
    job_type: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    tenant_id: string;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    progress: number;
    message: string;
    result?: Record<string, unknown>;
    error?: string;
  }> {
    const response = await this.client.get(`/jobs/${jobId}`);
    return response.data;
  }

  async listJobs(params?: {
    status_filter?: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    job_type_filter?: string;
  }): Promise<{
    jobs: Array<{
      job_id: string;
      job_type: string;
      status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
      tenant_id: string;
      created_at: string;
      started_at?: string;
      completed_at?: string;
      progress: number;
      message: string;
      result?: Record<string, unknown>;
      error?: string;
    }>;
    total: number;
  }> {
    const response = await this.client.get('/jobs', { params });
    return response.data;
  }

  async cancelJob(jobId: string): Promise<{ message: string }> {
    const response = await this.client.post(`/jobs/${jobId}/cancel`);
    return response.data;
  }

  // Generic HTTP methods for flexibility
  async get<T = unknown>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get(url, { params });
    return response.data;
  }

  async post<T = unknown>(url: string, data?: Record<string, unknown>): Promise<T> {
    const response = await this.client.post(url, data);
    return response.data;
  }

  async put<T = unknown>(url: string, data?: Record<string, unknown>): Promise<T> {
    const response = await this.client.put(url, data);
    return response.data;
  }

  async delete<T = unknown>(url: string): Promise<T> {
    const response = await this.client.delete(url);
    return response.data;
  }

  // Authenticated image loading
  async getImageUrl(imagePath: string): Promise<string> {
    try {
      // Check if imagePath is already a complete presigned URL
      if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
        // It's a presigned URL, use it directly
        return imagePath;
      }
      
      // Normalize to avoid duplicating baseURL path (/v1)
      let filesPath: string;
      if (imagePath.startsWith('/v1/files/')) {
        filesPath = imagePath.replace(/^\/v1\//, '/'); // -> '/files/...'
      } else if (imagePath.startsWith('/files/')) {
        filesPath = imagePath;
      } else {
        filesPath = `/files/${imagePath.replace(/^\/+/, '')}`;
      }

      // Make authenticated request to get the image
      const response = await this.client.get(filesPath, {
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
