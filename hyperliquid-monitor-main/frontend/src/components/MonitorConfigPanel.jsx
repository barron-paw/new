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
    telegramChatId: '',
    walletAddresses: '',
    language: 'zh',
  });
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [usesDefaultBot, setUsesDefaultBot] = useState(false);
  const [defaultBotUsername, setDefaultBotUsername] = useState('');

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
          telegramChatId: data.telegramChatId || '',
          walletAddresses: (data.walletAddresses || []).join('\n'),
          language: data.language || 'zh',
        });
        setLanguage(data.language || 'zh');
        setUsesDefaultBot(Boolean(data.usesDefaultBot));
        setDefaultBotUsername(data.defaultBotUsername || '');
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
        telegramChatId: form.telegramChatId.trim() || null,
        walletAddresses: parseAddresses(form.walletAddresses).slice(0, 2),
        language: form.language,
      };
      const response = await updateMonitorConfig(payload);
      setForm({
        telegramChatId: response.telegramChatId || '',
        walletAddresses: (response.walletAddresses || []).join('\n'),
        language: response.language || 'zh',
      });
      setLanguage(response.language || 'zh');
      setUsesDefaultBot(Boolean(response.usesDefaultBot));
      setDefaultBotUsername(response.defaultBotUsername || '');
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
              ? 'Save your Telegram chat ID and wallet addresses. The system already uses the official bot token for you.'
              : '填写 Telegram chat_id 与钱包地址即可，系统已为您配置官方机器人 Token。'}
          </p>
        </div>
        {status ? <div className="monitor-config__status">{status}</div> : null}
      </div>

      {helperText ? <p className="monitor-config__helper">{helperText}</p> : null}

      <div className="monitor-config__layout">
        <div className="monitor-config__card monitor-config__card--form">
          <form className="monitor-config__form" onSubmit={handleSubmit}>
            <div className="monitor-config__fieldset">
              <span className="monitor-config__legend">{isEnglish ? 'Telegram' : 'Telegram 设置'}</span>
              <label className="monitor-config__field">
                <span>{isEnglish ? 'Chat ID' : 'Chat ID'}</span>
                <input
                  type="text"
                  value={form.telegramChatId}
                  onChange={(event) => setForm((prev) => ({ ...prev, telegramChatId: event.target.value }))}
                  placeholder={isEnglish ? 'Group or chat ID' : '群组或私聊 ID'}
                  disabled={!canEdit || loading}
                />
                <small>
                  {isEnglish ? (
                    <>
                      {usesDefaultBot
                        ? 'Our default bot token is preconfigured. Talk to '
                        : 'Provide the chat ID used by your Telegram bot. Talk to '}
                      <strong>@TelegramBotRaw</strong> to obtain the ID.
                    </>
                  ) : (
                    <>
                      {usesDefaultBot ? '系统已内置官方机器人 Token。' : '如使用自建机器人请填写对应 chat_id。'}
                      通过 <strong>@TelegramBotRaw</strong> 发送消息即可返回 chat_id。
                    </>
                  )}
                </small>
                {usesDefaultBot ? (
                  <small className="monitor-config__field-note">
                    {isEnglish
                      ? defaultBotUsername
                        ? `Default bot: ${defaultBotUsername}. Open Telegram, search for it, press Start once.`
                        : 'Default bot token is active. Open Telegram and press Start on the official bot.'
                      : defaultBotUsername
                        ? `默认机器人：${defaultBotUsername}，在 Telegram 搜索并点击 Start 即可。`
                        : '已启用默认机器人，请在 Telegram 中打开官方机器人并点击 Start。'}
                  </small>
                ) : null}
              </label>
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
          <BotFatherGuide usesDefaultBot={usesDefaultBot} defaultBotUsername={defaultBotUsername} />
        </div>
      </div>
    </section>
  );
}
