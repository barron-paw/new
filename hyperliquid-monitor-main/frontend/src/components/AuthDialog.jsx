import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import './AuthDialog.css';

const modes = {
  login: {
    title: '登录账号',
    submitText: '登录',
    switchText: '没有账号？点此注册',
    target: 'register',
  },
  register: {
    title: '注册账号',
    submitText: '注册并开始 3 天试用',
    switchText: '已有账号？点此登录',
    target: 'login',
  },
};

export default function AuthDialog({ open, mode = 'login', onClose, onSwitch }) {
  const { login, register, error } = useAuth();
  const [form, setForm] = useState({ email: '', password: '' });
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState('');

  useEffect(() => {
    if (!open) {
      setForm({ email: '', password: '' });
      setLocalError('');
    }
  }, [open, mode]);

  if (!open) {
    return null;
  }

  const metadata = modes[mode] || modes.login;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLocalError('');
    try {
      setSubmitting(true);
      if (mode === 'login') {
        await login(form);
      } else {
        await register(form);
      }
      onClose();
    } catch (err) {
      setLocalError(err.message || '操作失败，请稍后再试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-dialog__backdrop" role="dialog" aria-modal="true">
      <div className="auth-dialog__panel">
        <div className="auth-dialog__header">
          <h2>{metadata.title}</h2>
          <button type="button" className="auth-dialog__close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        <form className="auth-dialog__form" onSubmit={handleSubmit}>
          <label className="auth-dialog__label">
            邮箱
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              placeholder="you@example.com"
              required
            />
          </label>
          <label className="auth-dialog__label">
            密码
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder="至少 6 位字符"
              required
              minLength={6}
            />
          </label>

          {(localError || error) ? (
            <div className="auth-dialog__error">{localError || error}</div>
          ) : null}

          <button type="submit" className="auth-dialog__submit" disabled={submitting}>
            {submitting ? '提交中…' : metadata.submitText}
          </button>
        </form>
        <div className="auth-dialog__switch">
          <button type="button" onClick={() => onSwitch(metadata.target)}>
            {metadata.switchText}
          </button>
        </div>
      </div>
    </div>
  );
}
