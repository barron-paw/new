const normalizeBaseUrl = (value) => (value ? value.replace(/\/$/, '') : value);

const envBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);
const API_BASE_URL = envBaseUrl || '/api';
const TOKEN_STORAGE_KEY = 'hm_auth_token';

let authToken = (typeof window !== 'undefined' && window.localStorage)
  ? window.localStorage.getItem(TOKEN_STORAGE_KEY)
  : null;

export function setAuthToken(token) {
  authToken = token || null;
  if (typeof window !== 'undefined' && window.localStorage) {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }
}

export function getAuthToken() {
  return authToken;
}

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  const config = {
    ...options,
    headers,
  };
  if (config.body && typeof config.body !== 'string') {
    config.body = JSON.stringify(config.body);
  }

  const response = await fetch(url, config);
  if (!response.ok) {
    let message = response.statusText || 'Request failed';
    try {
      const data = await response.json();
      message = data?.detail || data?.message || JSON.stringify(data);
    } catch (err) {
      const text = await response.text().catch(() => message);
      message = text || message;
    }
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export const apiClient = {
  get: (path, options) => request(path, { method: 'GET', ...options }),
  post: (path, body, options) => request(path, { method: 'POST', body, ...options }),
  put: (path, body, options) => request(path, { method: 'PUT', body, ...options }),
};

export default apiClient;
