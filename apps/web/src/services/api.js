import axios from 'axios';
import { getTenantIdFromToken, isTokenExpired } from '../utils/jwt';
// Force use of window.location.origin in development to use Vite proxy
const API_BASE_URL = import.meta.env.DEV
    ? window.location.origin
    : import.meta.env.VITE_API_URL || window.location.origin;
class ApiClient {
    constructor() {
        this.token = null;
        this.currentTenantId = null;
        this.client = axios.create({
            baseURL: `${API_BASE_URL}/v1`,
            timeout: 30000, // Increased timeout for file uploads
        });
        // Request interceptor to add auth token and tenant context
        this.client.interceptors.request.use((config) => {
            if (this.token) {
                config.headers.Authorization = `Bearer ${this.token}`;
            }
            if (this.currentTenantId) {
                config.headers['X-Tenant-ID'] = this.currentTenantId;
            }
            return config;
        }, (error) => Promise.reject(error));
        // Response interceptor for error handling
        this.client.interceptors.response.use((response) => response, (error) => {
            // Don't auto-logout on login endpoint 401s - let the login form handle it
            if (error.response?.status === 401 &&
                !error.config?.url?.includes('/auth/token')) {
                this.logout();
            }
            return Promise.reject(error);
        });
        // Load token and sync tenant context from token
        const savedToken = localStorage.getItem('access_token');
        if (savedToken && !isTokenExpired(savedToken)) {
            this.token = savedToken;
            this.syncTenantContextFromToken();
        }
        else if (savedToken) {
            // Token expired, clean up
            this.logout();
        }
    }
    get baseURL() {
        return this.client.defaults.baseURL || `${API_BASE_URL}/v1`;
    }
    // Auth methods
    async login(credentials) {
        const response = await this.client.post('/auth/token', {
            grant_type: 'password',
            ...credentials,
        });
        this.token = response.data.access_token;
        localStorage.setItem('access_token', this.token);
        // Sync tenant context from token (more reliable than credentials)
        this.syncTenantContextFromToken();
        return response.data;
    }
    async switchView(targetTenantId) {
        const response = await this.client.post('/auth/switch-view', {
            target_tenant_id: targetTenantId,
        });
        // Update token and sync tenant context from new token
        this.token = response.data.access_token;
        localStorage.setItem('access_token', this.token);
        this.syncTenantContextFromToken();
        return response.data;
    }
    logout() {
        this.token = null;
        this.currentTenantId = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('current_tenant_id');
        window.location.href = '/login';
    }
    // Tenant context management
    setCurrentTenant(tenantId) {
        this.currentTenantId = tenantId;
        // Store in localStorage for persistence
        if (tenantId) {
            localStorage.setItem('current_tenant_id', tenantId);
        }
        else {
            localStorage.setItem('current_tenant_id', 'null'); // Store 'null' string for global view
        }
    }
    getCurrentTenant() {
        // If currentTenantId is not set, try to get it from localStorage
        if (this.currentTenantId === undefined || this.currentTenantId === null) {
            const stored = localStorage.getItem('current_tenant_id');
            if (stored === 'null') {
                this.currentTenantId = null; // Global view
            }
            else if (stored) {
                this.currentTenantId = stored; // Specific tenant
            }
            else {
                this.currentTenantId = null; // Default to global view
            }
        }
        return this.currentTenantId;
    }
    // Sync tenant context from JWT token
    syncTenantContextFromToken() {
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
        }
        else {
            localStorage.setItem('current_tenant_id', 'null'); // Store 'null' string for global view
        }
    }
    async getCurrentUser() {
        const response = await this.client.get('/me');
        return response.data;
    }
    async changeMyPassword(passwordData) {
        const response = await this.client.put('/me/password', passwordData);
        return response.data;
    }
    // Tenants (system admin only)
    async getTenants() {
        const response = await this.client.get('/tenants');
        return response.data;
    }
    async createTenant(tenant) {
        const response = await this.client.post('/tenants', tenant);
        return response.data;
    }
    async getTenant(tenantId) {
        const response = await this.client.get(`/tenants/${tenantId}`);
        return response.data;
    }
    async updateTenant(tenantId, tenant) {
        const response = await this.client.put(`/tenants/${tenantId}`, tenant);
        return response.data;
    }
    async deleteTenant(tenantId) {
        await this.client.delete(`/tenants/${tenantId}`);
    }
    async toggleTenantStatus(tenantId, isActive) {
        const response = await this.client.patch(`/tenants/${tenantId}/status`, {
            is_active: isActive,
        });
        return response.data;
    }
    // Sites
    async getSites() {
        const response = await this.client.get('/sites');
        return response.data;
    }
    async createSite(site) {
        const response = await this.client.post('/sites', site);
        return response.data;
    }
    async updateSite(siteId, site) {
        const response = await this.client.put(`/sites/${siteId}`, site);
        return response.data;
    }
    async deleteSite(siteId) {
        await this.client.delete(`/sites/${siteId}`);
    }
    // Cameras
    async getCameras(siteId) {
        const response = await this.client.get(`/sites/${siteId}/cameras`);
        return response.data;
    }
    async createCamera(siteId, camera) {
        const response = await this.client.post(`/sites/${siteId}/cameras`, camera);
        return response.data;
    }
    async getCamera(siteId, cameraId) {
        const response = await this.client.get(`/sites/${siteId}/cameras/${cameraId}`);
        return response.data;
    }
    async updateCamera(siteId, cameraId, camera) {
        const response = await this.client.put(`/sites/${siteId}/cameras/${cameraId}`, camera);
        return response.data;
    }
    async deleteCamera(siteId, cameraId) {
        await this.client.delete(`/sites/${siteId}/cameras/${cameraId}`);
    }
    // Camera Streaming
    async startCameraStream(siteId, cameraId) {
        const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/stream/start`);
        return response.data;
    }
    // Devices
    async getWebcams(siteId) {
        const params = siteId ? { site_id: siteId } : {};
        const response = await this.client.get('/devices/webcams', { params });
        return response.data;
    }
    async stopCameraStream(siteId, cameraId) {
        const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/stream/stop`);
        return response.data;
    }
    async getCameraStreamStatus(siteId, cameraId) {
        const response = await this.client.get(`/sites/${siteId}/cameras/${cameraId}/stream/status`);
        return response.data;
    }
    getCameraStreamUrl(siteId, cameraId) {
        const baseUrl = import.meta.env.DEV
            ? window.location.origin
            : import.meta.env.VITE_API_URL || window.location.origin;
        const token = this.token || localStorage.getItem('access_token');
        const url = new URL(`${baseUrl}/v1/sites/${siteId}/cameras/${cameraId}/stream/feed`);
        if (token) {
            url.searchParams.set('access_token', token);
        }
        return url.toString();
    }
    getWorkerWebSocketUrl(tenantId) {
        const baseUrl = import.meta.env.DEV
            ? window.location.origin
            : import.meta.env.VITE_API_URL || window.location.origin;
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
    async startCameraProcessing(siteId, cameraId) {
        const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/processing/start`);
        return response.data;
    }
    async stopCameraProcessing(siteId, cameraId) {
        const response = await this.client.post(`/sites/${siteId}/cameras/${cameraId}/processing/stop`);
        return response.data;
    }
    // Staff
    async getStaff() {
        const response = await this.client.get('/staff');
        return response.data;
    }
    async createStaff(staff) {
        const response = await this.client.post('/staff', staff);
        return response.data;
    }
    async getStaffMember(staffId) {
        const response = await this.client.get(`/staff/${staffId}`);
        return response.data;
    }
    async updateStaff(staffId, staff) {
        const response = await this.client.put(`/staff/${staffId}`, staff);
        return response.data;
    }
    async deleteStaff(staffId) {
        await this.client.delete(`/staff/${staffId}`);
    }
    // Staff Face Images
    async getStaffFaceImages(staffId) {
        const response = await this.client.get(`/staff/${staffId}/faces`);
        return response.data;
    }
    async getStaffWithFaces(staffId) {
        const response = await this.client.get(`/staff/${staffId}/details`);
        return response.data;
    }
    async uploadStaffFaceImage(staffId, imageData, isPrimary = false) {
        const response = await this.client.post(`/staff/${staffId}/faces`, {
            image_data: imageData,
            is_primary: isPrimary,
        }, {
            timeout: 45000, // 45 second timeout for individual uploads
        });
        return response.data;
    }
    async uploadMultipleStaffFaceImages(staffId, imageDataArray) {
        const response = await this.client.post(`/staff/${staffId}/faces/bulk`, {
            images: imageDataArray.map((imageData, index) => ({
                image_data: imageData,
                is_primary: index === 0, // First image is primary if no existing images
            })),
        }, {
            timeout: Math.max(60000, imageDataArray.length * 20000), // Dynamic timeout based on number of images
        });
        return response.data;
    }
    async deleteStaffFaceImage(staffId, imageId) {
        await this.client.delete(`/staff/${staffId}/faces/${imageId}`);
    }
    async recalculateFaceEmbedding(staffId, imageId) {
        const response = await this.client.put(`/staff/${staffId}/faces/${imageId}/recalculate`);
        return response.data;
    }
    async testFaceRecognition(staffId, testImage) {
        const response = await this.client.post(`/staff/${staffId}/test-recognition`, { test_image: testImage });
        return response.data;
    }
    // Customers
    async getCustomers(params) {
        const response = await this.client.get('/customers', {
            params,
        });
        return response.data;
    }
    async createCustomer(customer) {
        const response = await this.client.post('/customers', customer);
        return response.data;
    }
    async getCustomer(customerId) {
        const response = await this.client.get(`/customers/${customerId}`);
        return response.data;
    }
    async updateCustomer(customerId, customer) {
        const response = await this.client.put(`/customers/${customerId}`, customer);
        return response.data;
    }
    async deleteCustomer(customerId) {
        await this.client.delete(`/customers/${customerId}`);
    }
    async bulkDeleteCustomers(customerIds) {
        const response = await this.client.post('/customers/bulk-delete', {
            customer_ids: customerIds,
        });
        return response.data;
    }
    async getCustomerFaceImages(customerId) {
        const response = await this.client.get(`/customers/${customerId}/face-images`);
        return response.data;
    }
    async deleteCustomerFaceImagesBatch(customerId, imageIds) {
        const response = await this.client.post(`/customers/${customerId}/face-images/batch-delete`, {
            image_ids: imageIds,
        });
        return response.data;
    }
    async backfillCustomerFaceImages(customerId) {
        const response = await this.client.post(`/customers/${customerId}/face-images/backfill`);
        return response.data;
    }
    // Customer Data Cleanup
    async findSimilarCustomers(customerId, params) {
        const response = await this.client.get(`/customers/${customerId}/similar`, {
            params,
        });
        return response.data;
    }
    async mergeCustomers(primaryCustomerId, secondaryCustomerId, notes) {
        const response = await this.client.post('/customers/merge', {
            primary_customer_id: primaryCustomerId,
            secondary_customer_id: secondaryCustomerId,
            notes,
        });
        return response.data;
    }
    async bulkMergeCustomers(mergeOperations) {
        const response = await this.client.post('/customers/bulk-merge', {
            merges: mergeOperations,
        });
        return response.data;
    }
    async reassignVisit(visitId, newCustomerId, update_embeddings = true) {
        const response = await this.client.post('/customers/reassign-visit', {
            visit_id: visitId,
            new_customer_id: newCustomerId,
            update_embeddings,
        });
        return response.data;
    }
    async reassignFaceImage(imageId, newCustomerId) {
        const response = await this.client.post('/customers/reassign-face-image', {
            image_id: imageId,
            new_customer_id: newCustomerId,
        });
        return response.data;
    }
    async cleanupLowConfidenceFaces(customerId, params) {
        const response = await this.client.post(`/customers/${customerId}/cleanup-low-confidence-faces`, params || {});
        return response.data;
    }
    // Visits
    async getVisits(params) {
        const response = await this.client.get('/visits', { params });
        return response.data;
    }
    async deleteVisits(visitIds) {
        const response = await this.client.post('/visits/delete', {
            visit_ids: visitIds,
        });
        return response.data;
    }
    async mergeVisits(visitIds, primaryVisitId) {
        const response = await this.client.post('/visits/merge', {
            visit_ids: visitIds,
            primary_visit_id: primaryVisitId,
        });
        return response.data;
    }
    async removeVisitFaceDetection(visitId) {
        const response = await this.client.delete(`/visits/${visitId}/face`);
        return response.data;
    }
    // Reports
    async getVisitorReport(params) {
        const response = await this.client.get('/reports/visitors', { params });
        return response.data;
    }
    async getDemographicsReport(params) {
        const response = await this.client.get('/reports/demographics', { params });
        return response.data;
    }
    // Health check
    async getHealth() {
        const response = await this.client.get('/health');
        return response.data;
    }
    // User Management (System Admin only)
    async getUsers(skip = 0, limit = 100) {
        const response = await this.client.get('/users', {
            params: { skip, limit },
        });
        return response.data;
    }
    async createUser(userData) {
        const response = await this.client.post('/users', userData);
        return response.data;
    }
    async getUser(userId) {
        const response = await this.client.get(`/users/${userId}`);
        return response.data;
    }
    async updateUser(userId, userData) {
        const response = await this.client.put(`/users/${userId}`, userData);
        return response.data;
    }
    async changeUserPassword(userId, passwordData) {
        const response = await this.client.put(`/users/${userId}/password`, passwordData);
        return response.data;
    }
    async deleteUser(userId) {
        const response = await this.client.delete(`/users/${userId}`);
        return response.data;
    }
    async toggleUserStatus(userId) {
        const response = await this.client.put(`/users/${userId}/toggle-status`);
        return response.data;
    }
    // API Key Management
    async getApiKeys() {
        const response = await this.client.get('/api-keys');
        return response.data;
    }
    async createApiKey(data) {
        const response = await this.client.post('/api-keys', data);
        return response.data;
    }
    async getApiKey(keyId) {
        const response = await this.client.get(`/api-keys/${keyId}`);
        return response.data;
    }
    async updateApiKey(keyId, data) {
        const response = await this.client.put(`/api-keys/${keyId}`, data);
        return response.data;
    }
    async deleteApiKey(keyId) {
        await this.client.delete(`/api-keys/${keyId}`);
    }
    // Workers Management
    async getWorkers(params) {
        const response = await this.client.get('/workers', { params });
        return response.data;
    }
    async getWorker(workerId) {
        const response = await this.client.get(`/workers/${workerId}`);
        return response.data;
    }
    async deleteWorker(workerId) {
        const response = await this.client.delete(`/workers/${workerId}`);
        return response.data;
    }
    async cleanupStaleWorkers(ttlSeconds = 300) {
        const response = await this.client.post('/workers/cleanup-stale', {
            ttl_seconds: ttlSeconds,
        });
        return response.data;
    }
    // WebRTC Session Management
    async startWebRTCSession(data) {
        const response = await this.client.post('/webrtc/sessions/start', data);
        return response.data;
    }
    async stopWebRTCSession(sessionId) {
        const response = await this.client.post(`/webrtc/sessions/${sessionId}/stop`);
        return response.data;
    }
    async getWebRTCSession(sessionId) {
        const response = await this.client.get(`/webrtc/sessions/${sessionId}`);
        return response.data;
    }
    async listWebRTCSessions() {
        const response = await this.client.get('/webrtc/sessions');
        return response.data;
    }
    // Enhanced Streaming Status APIs
    async getSiteStreamingStatus(siteId) {
        const response = await this.client.get(`/sites/${siteId}/streaming/status`);
        return response.data;
    }
    async getStreamingOverview() {
        const response = await this.client.get('/streaming/status-overview');
        return response.data;
    }
    // Process uploaded images for face recognition
    async processUploadedImages(images, siteId) {
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
    async getJobStatus(jobId) {
        const response = await this.client.get(`/jobs/${jobId}`);
        return response.data;
    }
    async listJobs(params) {
        const response = await this.client.get('/jobs', { params });
        return response.data;
    }
    async cancelJob(jobId) {
        const response = await this.client.post(`/jobs/${jobId}/cancel`);
        return response.data;
    }
    // Generic HTTP methods for flexibility
    async get(url, params) {
        const response = await this.client.get(url, { params });
        return response.data;
    }
    async post(url, data) {
        const response = await this.client.post(url, data);
        return response.data;
    }
    async put(url, data) {
        const response = await this.client.put(url, data);
        return response.data;
    }
    async delete(url) {
        const response = await this.client.delete(url);
        return response.data;
    }
    // Authenticated image loading
    async getImageUrl(imagePath) {
        try {
            // Check if imagePath is already a complete presigned URL
            if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
                // It's a presigned URL, use it directly
                return imagePath;
            }
            // Normalize to avoid duplicating baseURL path (/v1)
            let filesPath;
            if (imagePath.startsWith('/v1/files/')) {
                filesPath = imagePath.replace(/^\/v1\//, '/'); // -> '/files/...'
            }
            else if (imagePath.startsWith('/files/')) {
                filesPath = imagePath;
            }
            else {
                filesPath = `/files/${imagePath.replace(/^\/+/, '')}`;
            }
            // Make authenticated request to get the image
            const response = await this.client.get(filesPath, {
                responseType: 'blob',
            });
            // Create blob URL for the image
            const blob = response.data;
            return URL.createObjectURL(blob);
        }
        catch (error) {
            console.error('Failed to load authenticated image:', error);
            // Return a placeholder or fallback image URL
            return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+PC9zdmc+';
        }
    }
}
export const apiClient = new ApiClient();
