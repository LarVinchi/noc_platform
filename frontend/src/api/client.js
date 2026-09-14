import axios from 'axios';

// This points directly to your FastAPI server port
const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Create a dedicated API service for provisioning
export const provisioningApi = {
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
  getIncidents: (params) => apiClient.get('/incidents/', { params }),

  // Create a new incident (server auto-generates the tt_number)
  createIncident: (data) => apiClient.post('/incidents/', data),

  // Update status/resolution fields on an existing incident
  updateIncident: (incidentId, data) => apiClient.patch(`/incidents/${incidentId}`, data),
};

export default apiClient;