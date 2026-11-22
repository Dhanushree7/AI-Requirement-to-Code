import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 90000,
});

// Request interceptor: attach Authorization Bearer token from localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401 Unauthorized session expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const url = error.config?.url || '';
      // Don't auto-redirect on failed login/signup attempts
      const isAuthAttempt = url.includes('/auth/login') || url.includes('/auth/signin') || url.includes('/auth/register');
      if (!isAuthAttempt) {
        localStorage.removeItem('token');
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        sessionStorage.removeItem('token');
        sessionStorage.removeItem('access_token');
        sessionStorage.removeItem('user');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export const projectApi = {
  // Projects
  list: () => api.get('/projects').then(res => res.data),
  get: (id) => api.get(`/projects/${id}`).then(res => res.data),
  create: (data) => api.post('/projects', data).then(res => res.data),
  update: (id, data) => api.put(`/projects/${id}`, data).then(res => res.data),
  delete: (id) => api.delete(`/projects/${id}`).then(res => res.data),
  getDashboard: (id) => api.get(`/projects/${id}/dashboard`).then(res => res.data),
  getJobStatus: (jobId) => api.get(`/projects/jobs/${jobId}`).then(res => res.data),
  getActiveJob: (projectId) => api.get(`/projects/${projectId}/jobs/active`).then(res => res.data),

  // File Upload
  upload: (projectId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/projects/${projectId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(res => res.data);
  },
  getFiles: (projectId) => api.get(`/projects/${projectId}/files`).then(res => res.data),

  // Requirements
  analyzeRequirements: (projectId) => api.post(`/projects/${projectId}/requirements/analyze`).then(res => res.data),
  getDomainModel: (projectId) => api.get(`/projects/${projectId}/domain-model`).then(res => res.data),
  updateDomainModel: (projectId, data) => api.put(`/projects/${projectId}/domain-model`, data).then(res => res.data),
  getRequirements: (projectId, category) => {
    const params = category ? { category } : {};
    return api.get(`/projects/${projectId}/requirements`, { params }).then(res => res.data);
  },
  getRequirementsSummary: (projectId) => api.get(`/projects/${projectId}/requirements/summary`).then(res => res.data),
  createRequirement: (projectId, data) => api.post(`/projects/${projectId}/requirements`, data).then(res => res.data),
  updateRequirement: (reqId, data) => api.put(`/requirements/${reqId}`, data).then(res => res.data),
  deleteRequirement: (reqId) => api.delete(`/requirements/${reqId}`).then(res => res.data),

  // Artifacts
  generateAllArtifacts: (projectId) => api.post(`/projects/${projectId}/artifacts/generate-all`).then(res => res.data),
  getArtifact: (projectId, artifactType) => api.get(`/projects/${projectId}/artifacts/${artifactType}`).then(res => res.data),
  updateArtifact: (projectId, artifactType, data) => api.put(`/projects/${projectId}/artifacts/${artifactType}`, data).then(res => res.data),
  regenerateArtifact: (projectId, artifactType, data) => api.post(`/projects/${projectId}/artifacts/${artifactType}/regenerate`, data).then(res => res.data),
  restoreVersion: (projectId, artifactType, versionNumber) => api.post(`/projects/${projectId}/artifacts/${artifactType}/restore/${versionNumber}`).then(res => res.data),

  // Codegen
  getBackendSkeleton: (projectId) => api.get(`/projects/${projectId}/codegen/skeleton`).then(res => res.data),
  downloadBackendZip: async (projectId) => {
    const response = await api.get(`/projects/${projectId}/codegen/download`, {
      responseType: 'blob',
    });
    let filename = `fastapi_starter_${projectId ? projectId.slice(0, 8) : 'export'}.zip`;
    const disposition = response.headers?.['content-disposition'];
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename=["']?([^"';]+)["']?/);
      if (match && match[1]) {
        filename = match[1].trim();
      }
    }
    const blob = new Blob([response.data], { type: 'application/zip' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    return { success: true, filename };
  },
  downloadZipUrl: (projectId) => `/api/projects/${projectId}/codegen/download`,

  // Knowledge Graph
  getGraph: (projectId) => api.get(`/projects/${projectId}/graph`).then(res => res.data),
  getTraceability: (projectId) => api.get(`/projects/${projectId}/graph/traceability`).then(res => res.data),
  getImpactAnalysis: (projectId, nodeId) => api.get(`/projects/${projectId}/graph/impact/${nodeId}`).then(res => res.data),

  // RAG & Query Assistant
  queryRag: (projectId, question) => api.post(`/projects/${projectId}/rag/query`, { question }).then(res => res.data),
  getSuggestedQuestions: (projectId) => api.get(`/projects/${projectId}/rag/suggested-questions`).then(res => res.data),

  // LLM Health & Provider Settings
  getLlmHealth: () => api.get('/llm/health').then(res => res.data),
  getProviderStatus: () => api.get('/settings/provider/status').then(res => res.data),
  testAndSaveProvider: (data) => api.post('/settings/provider/test-and-save', data).then(res => res.data),
  deleteProviderKey: () => api.delete('/settings/provider').then(res => res.data),
};

export const authApi = {
  forgotPassword: (email) => api.post('/auth/forgot-password', { email }).then(res => res.data),
  verifyResetToken: (token) => api.get('/auth/verify-reset-token', { params: { token } }).then(res => res.data),
  resetPassword: (token, newPassword) => api.post('/auth/reset-password', { token, new_password: newPassword }).then(res => res.data),
  login: (email, password) => api.post('/auth/login', { email, password }).then(res => res.data),
  signin: (email, password) => api.post('/auth/login', { email, password }).then(res => res.data),
  register: (fullName, email, password) => api.post('/auth/register', { full_name: fullName, email, password }).then(res => res.data),
  signup: (fullName, email, password) => api.post('/auth/register', { full_name: fullName, email, password }).then(res => res.data),
  getMe: () => api.get('/auth/me').then(res => res.data),
};

export default api;
