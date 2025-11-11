import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { loginUser, registerUser, fetchCurrentUser, logoutUser } from '../api/auth.js';

const AuthContext = createContext({
  user: null,
  loading: true,
  error: '',
  login: async () => {},
  register: async () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadUser = useCallback(async () => {
    setLoading(true);
    try {
      const current = await fetchCurrentUser();
      setUser(current);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(async (payload) => {
    setError('');
    try {
      const nextUser = await loginUser(payload);
      setUser(nextUser);
      return nextUser;
    } catch (err) {
      setError(err.message || '登录失败，请稍后重试');
      throw err;
    }
  }, []);

  const register = useCallback(async (payload) => {
    setError('');
    try {
      const nextUser = await registerUser(payload);
      setUser(nextUser);
      return nextUser;
    } catch (err) {
      setError(err.message || '注册失败，请稍后重试');
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    logoutUser();
    setUser(null);
  }, []);

  const value = {
    user,
    loading,
    error,
    login,
    register,
    logout,
    refreshUser: loadUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
