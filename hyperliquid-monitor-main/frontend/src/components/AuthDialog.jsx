import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import './AuthDialog.css';
import { useLanguage } from '../context/LanguageContext.jsx';
import { login, register, requestVerificationCode } from '../api/auth.js';

export default function AuthDialog({ open, mode = 'login', onClose, onSwitch }) {
  const { login, register, error } = useAuth();
  const { language } = useLanguage();
  const isEnglish = language === 'en';

  const modes = {
    login: {
      title: isEnglish ? 'Sign in' : '登录账号',
      submitText: isEnglish ? 'Sign in' : '登录',
      switchText: isEnglish ? 'No account? Register' : '没有账号？点此注册',
      target: 'register',
    },
    register: {
      title: isEnglish ? 'Create account' : '注册账号',
      submitText: isEnglish ? 'Register & start 3-day trial' : '注册并开始 3 天试用',
      switchText: isEnglish ? 'Already have an account? Sign in' : '已有账号？点此登录',
      target: 'login',
    },
  };

  const [form, setForm] = useState({ email: '', password: '', verificationCode: '' });
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

  const handleRequestVerification = async () => {
    const email = form.email.trim();
    if (!email) {
      setLocalError(isEnglish ? 'Please enter your email first.' : '请先填写邮箱。');
      return;
    }
    setLocalError('');
    try {
      await requestVerificationCode({ email });
      setLocalError(isEnglish ? 'Verification code sent. Please check your inbox.' : '验证码已发送，请查收邮箱。');
    } catch (err) {
      setLocalError(err.message || (isEnglish ? 'Failed to send verification code.' : '验证码发送失败。'));
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLocalError('');
    if (!form.email || !form.password) {
      setLocalError(isEnglish ? 'Email and password are required.' : '邮箱和密码不能为空。');
      return;
    }
    try {
      setSubmitting(true);
      if (mode === 'login') {
        await login(form);
      } else {
        if (!form.verificationCode.trim()) {
          setLocalError(isEnglish ? 'Verification code is required.' : '请输入邮箱验证码。');
          setSubmitting(false);
          return;
        }
        await register({ email: form.email, password: form.password, verification_code: form.verificationCode.trim() });
      }
      onClose();
    } catch (err) {
      setLocalError(err.message || (isEnglish ? 'Action failed, please retry later.' : '操作失败，请稍后再试'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-dialog__backdrop" role="dialog" aria-modal="true">
      <div className="auth-dialog__panel">
        <div className="auth-dialog__header">
          <h2>{metadata.title}</h2>
          <button
            type="button"
            className="auth-dialog__close"
            onClick={onClose}
            aria-label={isEnglish ? 'Close' : '关闭'}
          >
            ×
          </button>
        </div>
        <form className="auth-dialog__form" onSubmit={handleSubmit}>
          <label className="auth-dialog__label">
            {isEnglish ? 'Email' : '邮箱'}
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              placeholder="you@example.com"
              required
            />
          </label>
          <label className="auth-dialog__label">
            {isEnglish ? 'Password' : '密码'}
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder={isEnglish ? 'At least 6 characters' : '至少 6 位字符'}
              required
              minLength={6}
            />
          </label>
          {mode === 'register' ? (
            <label>
              <span>{isEnglish ? 'Verification Code' : '验证码'}</span>
              <div className="auth-dialog__code-row">
                <input
                  type="text"
                  value={form.verificationCode}
                  onChange={(event) => setForm((prev) => ({ ...prev, verificationCode: event.target.value }))}
                />
                <button type="button" onClick={handleRequestVerification} disabled={submitting}>
                  {isEnglish ? 'Send Code' : '获取验证码'}
                </button>
              </div>
            </label>
          ) : null}

          {(localError || error) ? (
            <div className="auth-dialog__error">{localError || error}</div>
          ) : null}

          <button type="submit" className="auth-dialog__submit" disabled={submitting}>
            {submitting ? (isEnglish ? 'Submitting…' : '提交中…') : metadata.submitText}
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
