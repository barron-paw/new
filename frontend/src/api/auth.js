import apiClient, { setAuthToken, getAuthToken } from './client';

export async function loginUser(payload) {
  const response = await apiClient.post('/auth/login', payload);
  if (response?.token) {
    setAuthToken(response.token);
  }
  return response?.user || null;
}

export async function registerUser(payload) {
  const response = await apiClient.post('/auth/register', payload);
  if (response?.token) {
    setAuthToken(response.token);
  }
  return response?.user || null;
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

export function logoutUser() {
  setAuthToken(null);
}

export function requestVerificationCode(payload) {
  return apiClient.post('/auth/request_verification', payload);
}
