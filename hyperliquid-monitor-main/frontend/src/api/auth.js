import apiClient, { setAuthToken, getAuthToken } from './client';

export async function registerUser(payload) {
  const response = await apiClient.post('/auth/register', payload);
  setAuthToken(response.token);
  return response.user;
}

export function login(payload) {
  return apiClient.post('/auth/login', payload);
}

export function register(payload) {
  return apiClient.post('/auth/register', payload);
}

export async function fetchCurrentUser() {
  try {
    const token = getAuthToken();
    if (!token) {
      return null;
    }
    const user = await apiClient.get('/auth/me');
    return user;
  } catch (error) {
    setAuthToken(null);
    return null;
  }
}

export function requestVerificationCode(payload) {
  return apiClient.post('/auth/request_verification', payload);
}

export function logoutUser() {
  setAuthToken(null);
}
