import { useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import AuthDialog from './AuthDialog.jsx';
import './AccountMenu.css';

function formatStatus(user) {
  if (!user) {
    return null;
  }
  const trialEnd = user.trial_end ? new Date(user.trial_end) : null;
  const subscriptionEnd = user.subscription_end ? new Date(user.subscription_end) : null;
  const now = new Date();

  if (user.subscription_active && subscriptionEnd) {
    return `订阅有效，截止 ${subscriptionEnd.toLocaleString()}`;
  }
  if (user.trial_active && trialEnd) {
    const days = Math.max(0, Math.ceil((trialEnd - now) / (1000 * 60 * 60 * 24)));
    return `试用剩余 ${days} 天`;
  }
  return '已过期，请续费后继续使用监控功能';
}

export default function AccountMenu() {
  const { user, loading, logout } = useAuth();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState('login');
  const statusLabel = useMemo(() => formatStatus(user), [user]);

  const openDialog = (mode) => {
    setDialogMode(mode);
    setDialogOpen(true);
  };

  if (loading) {
    return <div className="account-menu">正在加载账号信息…</div>;
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
            退出
          </button>
        </>
      ) : (
        <div className="account-menu__actions">
          <button type="button" className="account-menu__button" onClick={() => openDialog('login')}>
            登录
          </button>
          <button type="button" className="account-menu__button account-menu__button--secondary" onClick={() => openDialog('register')}>
            注册
          </button>
        </div>
      )}

      <AuthDialog
        open={dialogOpen}
        mode={dialogMode}
        onClose={() => setDialogOpen(false)}
        onSwitch={(mode) => setDialogMode(mode)}
      />
    </div>
  );
}
