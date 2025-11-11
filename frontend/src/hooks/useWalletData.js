import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchWalletSummary, fetchWalletFills } from '../api/wallet';
import { useLanguage } from '../context/LanguageContext.jsx';

const REFRESH_INTERVAL = 15_000;

export function useWalletData() {
  const { language } = useLanguage();
  const isEnglish = language === 'en';
  const [selectedWallet, setSelectedWallet] = useState('');
  const [activeWallet, setActiveWallet] = useState('');
  const [summary, setSummary] = useState(null);
  const [fills, setFills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadData = useCallback(async (address) => {
    if (!address) {
      setSummary(null);
      setFills([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [summaryResponse, fillsResponse] = await Promise.all([
        fetchWalletSummary(address),
        fetchWalletFills(address, 50),
      ]);
      setSummary(summaryResponse);
      setFills(fillsResponse.items || []);
    } catch (err) {
      setError(err.message || (isEnglish ? 'Failed to load wallet data' : '加载钱包数据失败'));
    } finally {
      setLoading(false);
    }
  }, [isEnglish]);

  useEffect(() => {
    if (!activeWallet) {
      return;
    }
    loadData(activeWallet);
    const timer = setInterval(() => loadData(activeWallet), REFRESH_INTERVAL);
    return () => clearInterval(timer);
  }, [activeWallet, loadData]);

  const positions = useMemo(() => summary?.positions || [], [summary]);

  const refresh = useCallback(() => {
    const trimmed = selectedWallet.trim();
    if (!trimmed) {
      setActiveWallet('');
      setSummary(null);
      setFills([]);
      setError('');
      return;
    }
    setError('');
    setActiveWallet((current) => {
      if (current === trimmed) {
        loadData(trimmed);
        return current;
      }
      return trimmed;
    });
  }, [loadData, selectedWallet]);

  return {
    selectedWallet,
    setSelectedWallet,
    summary,
    positions,
    fills,
    loading,
    error,
    refresh,
  };
}

export default useWalletData;
