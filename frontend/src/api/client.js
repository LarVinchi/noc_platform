import axios from 'axios';

// This points directly to your FastAPI server port
const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;