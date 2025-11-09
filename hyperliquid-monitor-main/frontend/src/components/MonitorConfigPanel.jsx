import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { fetchMonitorConfig, updateMonitorConfig } from '../api/config.js';
import BotFatherGuide from './BotFatherGuide.jsx';

function parseAddresses(value) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function MonitorConfigPanel() {
  const { user } = useAuth();
  const [form, setForm] = useState({
    telegramBotToken: '',
    telegramChatId: '',
    walletAddresses: '',
  });
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const canEdit = user?.can_access_monitor;

  useEffect(() => {
    const loadConfig = async () => {
      if (!canEdit) {
        return;
      }
      setLoading(true);
      try {
        const data = await fetchMonitorConfig();
        setForm({
          telegramBotToken: data.telegramBotToken || '',
          telegramChatId: data.telegramChatId || '',
          walletAddresses: (data.walletAddresses || []).join('\n'),
        });
      } catch (err) {
        setStatus(err.message || '无法加载监控配置');
      } finally {
        setLoading(false);
      }
    };
    loadConfig();
  }, [canEdit]);

  const helperText = useMemo(() => {
    if (!user) {
      return '请先登录后配置监控信息。';
    }
    if (!canEdit) {
      return '试用已到期或订阅未激活，无法编辑监控配置。';
    }
    return '';
  }, [user, canEdit]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canEdit) {
      return;
    }
    setStatus('');
    try {
      setLoading(true);
      const payload = {
        telegramBotToken: form.telegramBotToken.trim() || null,
        telegramChatId: form.telegramChatId.trim() || null,
        walletAddresses: parseAddresses(form.walletAddresses),
      };
      const response = await updateMonitorConfig(payload);
      setForm({
        telegramBotToken: response.telegramBotToken || '',
        telegramChatId: response.telegramChatId || '',
        walletAddresses: (response.walletAddresses || []).join('\n'),
      });
      setStatus('监控配置已保存。');
    } catch (err) {
      setStatus(err.message || '保存失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="dashboard__section monitor-config">
      <div className="monitor-config__grid">
        <div className="monitor-config__form-wrapper">
          <h2>监控配置</h2>
          {helperText ? <p className="monitor-config__helper">{helperText}</p> : null}
          <form className="monitor-config__form" onSubmit={handleSubmit}>
            <label>
              Telegram Bot Token
              <input
                type="text"
                value={form.telegramBotToken}
                onChange={(event) => setForm((prev) => ({ ...prev, telegramBotToken: event.target.value }))}
                placeholder="例如：123456:ABCDEF"
                disabled={!canEdit || loading}
              />
            </label>
            <label>
              Telegram Chat ID
              <input
                type="text"
                value={form.telegramChatId}
                onChange={(event) => setForm((prev) => ({ ...prev, telegramChatId: event.target.value }))}
                placeholder="群组或私聊 ID"
                disabled={!canEdit || loading}
              />
            </label>
            <label>
              钱包地址（每行一个或使用逗号分隔）
              <textarea
                rows={6}
                value={form.walletAddresses}
                onChange={(event) => setForm((prev) => ({ ...prev, walletAddresses: event.target.value }))}
                placeholder="0x1234...\n0xabcd..."
                disabled={!canEdit || loading}
              />
            </label>
            <button type="submit" disabled={!canEdit || loading}>
              {loading ? '处理中…' : '保存配置'}
            </button>
            {status ? <p className="monitor-config__message">{status}</p> : null}
          </form>
        </div>
        <BotFatherGuide />
      </div>
    </section>
  );
}
