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

export default apiClient;