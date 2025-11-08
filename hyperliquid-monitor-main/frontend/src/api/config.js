import apiClient from './client';

export function fetchConfig() {
  return apiClient.get('/config');
}

export function updateConfig(config) {
  return apiClient.post('/config', config);
}

