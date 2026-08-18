import axios from 'axios';

export const TOKEN_STORAGE_KEY = 'access_token';

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url: string = error.config?.url ?? '';
      const isLoginRequest = url.includes('/auth/login');
      if (!isLoginRequest) {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        if (!window.location.pathname.startsWith('/login')) {
          window.location.assign('/login');
        }
      }
    }
    return Promise.reject(error);
  },
);