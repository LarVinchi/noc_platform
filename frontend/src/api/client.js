import axios from 'axios';

// This points directly to your FastAPI server port
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Create a dedicated API service for provisioning
export const provisioningApi = {
  assignmentOptions: () => apiClient.get('/inventory/assignment-options'),
  createNap: (data) => apiClient.post('/inventory/naps', data),
  allocateOrder: (id, data) => apiClient.patch(`/provisioning/${id}/allocate`, data),
  previewRequest: (data) => apiClient.post('/provisioning/intake/preview', data),
  importRequest: (data) => apiClient.post('/provisioning/intake', data),
  // Fetch all orders
  getOrders: () => apiClient.get('/provisioning/'),
  
  // Create a new order
  createOrder: (data) => apiClient.post('/provisioning/', data),
  
  // Complete Installation (Uses multipart/form-data for image uploads)
  completeInstallation: (orderId, formData) => {
    return apiClient.post(`/provisioning/${orderId}/complete`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  acceptInstallation: (orderId) => apiClient.patch(`/provisioning/${orderId}/accept`),

  // --- NEW: Drag and Drop Status Update ---
  updateStatus: (orderId, status) => apiClient.patch(`/provisioning/${orderId}/status`, { status })
};

// Create a dedicated API service for incidents
export const incidentsApi = {
  // List/filter incidents
  getIncidents: (params, options = {}) => apiClient.get('/incidents/', { ...options, params }),

  // Create a new incident (server auto-generates the tt_number)
  createIncident: (data) => apiClient.post('/incidents/', data),

  // Update status/resolution fields on an existing incident
  updateIncident: (incidentId, data) => apiClient.patch(`/incidents/${incidentId}`, data),
};

export const activitiesApi = {
  list: (options = {}) => apiClient.get('/activities/', options),
  create: (data) => apiClient.post('/activities/', data),
  update: (id, data) => apiClient.patch(`/activities/${id}`, data),
};

export default apiClient;
