import apiClient from './client';

export function fetchBinanceFollowConfig() {
  return apiClient.get('/binance_follow');
}

export function saveBinanceFollowConfig(payload) {
  return apiClient.post('/binance_follow', payload);
}

