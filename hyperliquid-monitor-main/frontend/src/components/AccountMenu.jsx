import { useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import AuthDialog from './AuthDialog.jsx';
import './AccountMenu.css';
import { useLanguage } from '../context/LanguageContext.jsx';
import { fetchMonitorConfig, updateMonitorConfig } from '../api/config.js';

function formatStatus(user, language) {
  const isEnglish = language === 'en';
  if (!user) {
    return null;
  }
  const trialEnd = user.trial_end ? new Date(user.trial_end) : null;
  const subscriptionEnd = user.subscription_end ? new Date(user.subscription_end) : null;
  const now = new Date();

  if (user.subscription_active && subscriptionEnd) {
    return isEnglish
      ? `Subscription active, until ${subscriptionEnd.toLocaleString()}`
      : `订阅有效，截止 ${subscriptionEnd.toLocaleString()}`;
  }
  if (user.trial_active && trialEnd) {
    const days = Math.max(0, Math.ceil((trialEnd - now) / (1000 * 60 * 60 * 24)));
    return isEnglish ? `Trial remaining ${days} days` : `试用剩余 ${days} 天`;
  }
  return isEnglish ? 'Expired. Please renew to continue monitoring.' : '已过期，请续费后继续使用监控功能';
}

export default function AccountMenu() {
  const { user, loading, logout } = useAuth();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState('login');
  const { language, setLanguage } = useLanguage();
  const isEnglish = language === 'en';
  const statusLabel = useMemo(() => formatStatus(user, language), [user, language]);
  const [savingLanguage, setSavingLanguage] = useState(false);

  const openDialog = (mode) => {
    setDialogMode(mode);
    setDialogOpen(true);
  };

  const handleLanguageChange = async (event) => {
    const nextLanguage = event.target.value;
    setLanguage(nextLanguage);
    if (!user) {
      return;
    }
    try {
      setSavingLanguage(true);
      const config = await fetchMonitorConfig().catch(() => null);
      if (!config) {
        return;
      }
      await updateMonitorConfig({
        telegramBotToken: (config.telegramBotToken || '').trim() || null,
        telegramChatId: (config.telegramChatId || '').trim() || null,
        walletAddresses: Array.isArray(config.walletAddresses) ? config.walletAddresses : [],
        language: nextLanguage,
      });
      setLanguage(nextLanguage);
    } catch (error) {
      console.error('Failed to update language preference', error);
    } finally {
      setSavingLanguage(false);
    }
  };

  if (loading) {
    return <div className="account-menu">{isEnglish ? 'Loading account…' : '正在加载账号信息…'}</div>;
  }

  return (
    <div className="account-menu">
      {user ? (
        <>
          <div className="account-menu__details">
            <div className="account-menu__email">{user.email}</div>
            <div className="account-menu__status" data-active={user.can_access_monitor}>{statusLabel}</div>
          </div>
          <button type="button" className="account-menu__button" onClick={logout}>
            {isEnglish ? 'Sign out' : '退出'}
          </button>
        </>
      ) : (
        <div className="account-menu__actions">
          <button type="button" className="account-menu__button" onClick={() => openDialog('login')}>
            {isEnglish ? 'Sign in' : '登录'}
          </button>
          <button type="button" className="account-menu__button account-menu__button--secondary" onClick={() => openDialog('register')}>
            {isEnglish ? 'Register' : '注册'}
          </button>
        </div>
      )}

      <div className="account-menu__language">
        <span aria-hidden="true">🌐</span>
        <label className="visually-hidden" htmlFor="language-select">
          {isEnglish ? 'Language' : '界面语言'}
        </label>
        <select
          id="language-select"
          value={language}
          onChange={handleLanguageChange}
          disabled={savingLanguage}
        >
          <option value="zh">中文</option>
          <option value="en">English</option>
        </select>
      </div>

      <AuthDialog
        open={dialogOpen}
        mode={dialogMode}
        onClose={() => setDialogOpen(false)}
        onSwitch={(mode) => setDialogMode(mode)}
      />
    </div>
  );
}
