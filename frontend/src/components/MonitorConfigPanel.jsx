import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { fetchMonitorConfig, updateMonitorConfig } from '../api/config.js';
import BotFatherGuide from './BotFatherGuide.jsx';
import { useLanguage } from '../context/LanguageContext.jsx';

function parseAddresses(value) {
  return value
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function MonitorConfigPanel() {
  const { user } = useAuth();
  const { language, setLanguage } = useLanguage();
  const isEnglish = language === 'en';
  const [form, setForm] = useState({
    telegramBotToken: '',
    telegramChatId: '',
    walletAddresses: '',
    language: 'zh',
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
          language: data.language || 'zh',
        });
        setLanguage(data.language || 'zh');
      } catch (err) {
        setStatus(isEnglish ? err.message || 'Failed to load monitor configuration' : err.message || '无法加载监控配置');
      } finally {
        setLoading(false);
      }
    };
    loadConfig();
  }, [canEdit, isEnglish, setLanguage]);

  const helperText = useMemo(() => {
    if (!user) {
      return isEnglish ? 'Please log in to configure monitoring.' : '请先登录后配置监控信息。';
    }
    if (!canEdit) {
      return isEnglish ? 'Trial expired or subscription inactive. Monitoring configuration locked.' : '试用已到期或订阅未激活，无法编辑监控配置。';
    }
    return '';
  }, [user, canEdit, isEnglish]);

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
        walletAddresses: parseAddresses(form.walletAddresses).slice(0, 2),
        language: form.language,
      };
      const response = await updateMonitorConfig(payload);
      setForm({
        telegramBotToken: response.telegramBotToken || '',
        telegramChatId: response.telegramChatId || '',
        walletAddresses: (response.walletAddresses || []).join('\n'),
        language: response.language || 'zh',
      });
      setLanguage(response.language || 'zh');
      setStatus(isEnglish ? 'Monitoring configuration saved.' : '监控配置已保存。');
    } catch (err) {
      setStatus(err.message || (isEnglish ? 'Save failed, please retry later.' : '保存失败，请稍后重试'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="dashboard__section monitor-config">
      <div className="monitor-config__header">
        <div>
          <h2>{isEnglish ? 'Monitoring Configuration' : '监控配置'}</h2>
          <p>
            {isEnglish
              ? 'Provide Telegram credentials and wallet addresses. The server will start monitoring and push trade alerts automatically.'
              : '填写 Telegram 凭证与钱包地址，保存后服务器会自动启动监控并推送交易提醒。'}
          </p>
        </div>
        {status ? <div className="monitor-config__status">{status}</div> : null}
      </div>

      {helperText ? <p className="monitor-config__helper">{helperText}</p> : null}

      <div className="monitor-config__layout">
        <div className="monitor-config__card monitor-config__card--form">
          <form className="monitor-config__form" onSubmit={handleSubmit}>
            <div className="monitor-config__fieldset">
              <span className="monitor-config__legend">{isEnglish ? 'Telegram Credentials' : 'Telegram 凭证'}</span>
              <div className="monitor-config__input-row">
                <label className="monitor-config__field">
                  <span>Bot Token</span>
                  <input
                    type="text"
                    value={form.telegramBotToken}
                    onChange={(event) => setForm((prev) => ({ ...prev, telegramBotToken: event.target.value }))}
                    placeholder={isEnglish ? 'e.g. 123456789:ABCDEF' : '例如：123456789:ABCDEF'}
                    disabled={!canEdit || loading}
                  />
                  <small>
                    {isEnglish
                      ? 'Token obtained from BotFather. Test it with your bot before saving.'
                      : '来自 BotFather 的 Token，建议先测试是否能成功发送消息。'}
                  </small>
                </label>
                <label className="monitor-config__field">
                  <span>Chat ID</span>
                  <input
                    type="text"
                    value={form.telegramChatId}
                    onChange={(event) => setForm((prev) => ({ ...prev, telegramChatId: event.target.value }))}
                    placeholder={isEnglish ? 'Group or chat ID' : '群组或私聊 ID'}
                    disabled={!canEdit || loading}
                  />
                  <small>
                    {isEnglish
                      ? 'Use @TelegramBotRaw or @userinfobot to retrieve the ID.'
                      : '可通过 @TelegramBotRaw 或 @userinfobot 查询。'}
                  </small>
                </label>
              </div>
            </div>

            <div className="monitor-config__fieldset">
              <span className="monitor-config__legend">{isEnglish ? 'Wallet Addresses' : '钱包列表'}</span>
              <label className="monitor-config__field">
                <span>{isEnglish ? 'Addresses to Monitor' : '监控地址'}</span>
                <textarea
                  rows={7}
                  value={form.walletAddresses}
                  onChange={(event) => setForm((prev) => ({ ...prev, walletAddresses: event.target.value }))}
                  placeholder={isEnglish ? '0x1234...\n0xabcd...' : '0x1234...\n0xabcd...'}
                  disabled={!canEdit || loading}
                />
                <small>
                  {isEnglish
                    ? 'One address per line (or separated by commas). Up to 2 wallets are monitored.'
                    : '每行一个地址，最多监控 2 个地址。'}
                </small>
              </label>
            </div>

            <div className="monitor-config__fieldset">
              <span className="monitor-config__legend">{isEnglish ? 'Language' : '语言'}</span>
              <label className="monitor-config__field">
                <span>{isEnglish ? 'Interface language' : '界面语言'}</span>
                <select
                  value={form.language}
                  onChange={(event) => setForm((prev) => ({ ...prev, language: event.target.value }))}
                  disabled={!canEdit || loading}
                >
                  <option value="zh">中文</option>
                  <option value="en">English</option>
                </select>
                <small>
                  {isEnglish
                    ? 'Selecting English will switch the UI and Telegram notifications to English.'
                    : '选择英语后，前端界面与推送信息将使用英文。'}
                </small>
              </label>
            </div>

            <div className="monitor-config__actions">
              <button type="submit" disabled={!canEdit || loading}>
                {loading ? (isEnglish ? 'Processing…' : '处理中…') : isEnglish ? 'Save' : '保存配置'}
              </button>
              <p className="monitor-config__hint">
                {isEnglish
                  ? 'After saving, check the console to confirm the monitoring service is running.'
                  : '保存后可在控制台查看监控线程是否启动。'}
              </p>
            </div>

            <div className="monitor-config__details">
              <p className="monitor-config__details-title">{isEnglish ? 'Monitoring Behaviour' : '监控提醒说明'}</p>
              <ul className="monitor-config__details-list">
                <li>{isEnglish ? 'Every time you save the configuration, a fresh position snapshot is pushed immediately.' : '每次保存配置后，立即发送当前持仓快照。'}</li>
                <li>{isEnglish ? 'After monitoring is enabled, every open or close event triggers a notification.' : '保存配置并启用监控后，每次开仓或平仓都会推送提醒。'}</li>
                <li>{isEnglish ? 'A consolidated position snapshot is delivered every 4 hours automatically.' : '系统会每 4 小时自动发送一次持仓快照。'}</li>
              </ul>
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
