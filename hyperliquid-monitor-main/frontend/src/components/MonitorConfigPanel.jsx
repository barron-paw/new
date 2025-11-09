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
      <div className="monitor-config__header">
        <div>
          <h2>监控配置</h2>
          <p>填写 Telegram 凭证与钱包地址，保存后服务器会自动启动监控并推送交易提醒。</p>
        </div>
        {status ? <div className="monitor-config__status">{status}</div> : null}
      </div>

      {helperText ? <p className="monitor-config__helper">{helperText}</p> : null}

      <div className="monitor-config__layout">
        <div className="monitor-config__card monitor-config__card--form">
          <form className="monitor-config__form" onSubmit={handleSubmit}>
            <div className="monitor-config__fieldset">
              <span className="monitor-config__legend">Telegram 凭证</span>
              <div className="monitor-config__input-row">
                <label className="monitor-config__field">
                  <span>Bot Token</span>
                  <input
                    type="text"
                    value={form.telegramBotToken}
                    onChange={(event) => setForm((prev) => ({ ...prev, telegramBotToken: event.target.value }))}
                    placeholder="例如：123456789:ABCDEF"
                    disabled={!canEdit || loading}
                  />
                  <small>来自 BotFather 的 Token，建议先测试是否能成功发送消息。</small>
                </label>
                <label className="monitor-config__field">
                  <span>Chat ID</span>
                  <input
                    type="text"
                    value={form.telegramChatId}
                    onChange={(event) => setForm((prev) => ({ ...prev, telegramChatId: event.target.value }))}
                    placeholder="群组或私聊 ID"
                    disabled={!canEdit || loading}
                  />
                  <small>可通过 @TelegramBotRaw 或 @userinfobot 查询。</small>
                </label>
              </div>
            </div>

            <div className="monitor-config__fieldset">
              <span className="monitor-config__legend">钱包列表</span>
              <label className="monitor-config__field">
                <span>监控地址</span>
                <textarea
                  rows={7}
                  value={form.walletAddresses}
                  onChange={(event) => setForm((prev) => ({ ...prev, walletAddresses: event.target.value }))}
                  placeholder="0x1234...\n0xabcd..."
                  disabled={!canEdit || loading}
                />
                <small>每行一个地址，或使用逗号分隔；保存后 30 秒内生效。</small>
              </label>
            </div>

            <div className="monitor-config__actions">
              <button type="submit" disabled={!canEdit || loading}>
                {loading ? '处理中…' : '保存配置'}
              </button>
              <p className="monitor-config__hint">保存后可在控制台查看监控线程是否启动。</p>
            </div>
          </form>
        </div>

        <div className="monitor-config__card monitor-config__card--guide">
          <BotFatherGuide />
        </div>
      </div>
    </section>
  );
}
