import { useEffect, useMemo, useState } from 'react';
import { fetchBinanceFollowConfig, saveBinanceFollowConfig } from '../api/binance.js';
import { useLanguage } from '../context/LanguageContext.jsx';

const MODE_OPTIONS = [
  { value: 'fixed', labelZh: '固定份额', labelEn: 'Fixed size' },
  { value: 'percentage', labelZh: '按百分比', labelEn: 'Percentage' },
];

const STATUS_LABELS = {
  active: {
    zh: '运行中',
    en: 'Active',
  },
  disabled: {
    zh: '未启用',
    en: 'Disabled',
  },
  stopped_by_loss: {
    zh: '已因止损暂停',
    en: 'Stopped by stop-loss',
  },
};

const DEFAULT_FORM = {
  enabled: false,
  walletAddress: '',
  mode: 'fixed',
  amount: '',
  stopLossAmount: '',
  maxPosition: '',
  minOrderSize: '',
  apiKey: '',
  apiSecret: '',
};

export default function BinanceFollowPanel() {
  const { language } = useLanguage();
  const isEnglish = language === 'en';

  const [form, setForm] = useState(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [hasApiKey, setHasApiKey] = useState(false);
  const [hasApiSecret, setHasApiSecret] = useState(false);
  const [followStatus, setFollowStatus] = useState('disabled');
  const [stopReason, setStopReason] = useState('');
  const [baselineBalance, setBaselineBalance] = useState(null);
  const [resetCredentials, setResetCredentials] = useState(false);

  useEffect(() => {
    let ignore = false;
    const load = async () => {
      setLoading(true);
      setStatusMessage('');
      try {
        const data = await fetchBinanceFollowConfig();
        if (ignore) {
          return;
        }
        setForm({
          enabled: Boolean(data.enabled),
          walletAddress: data.walletAddress || '',
          mode: data.mode || 'fixed',
          amount: data.amount != null ? String(data.amount) : '',
          stopLossAmount: data.stopLossAmount != null ? String(data.stopLossAmount) : '',
          maxPosition: data.maxPosition != null ? String(data.maxPosition) : '',
          minOrderSize: data.minOrderSize != null ? String(data.minOrderSize) : '',
          apiKey: '',
          apiSecret: '',
        });
        setHasApiKey(Boolean(data.hasApiKey));
        setHasApiSecret(Boolean(data.hasApiSecret));
        setFollowStatus(data.status || (data.enabled ? 'active' : 'disabled'));
        setStopReason(data.stopReason || '');
        setBaselineBalance(
          typeof data.baselineBalance === 'number' ? data.baselineBalance : null,
        );
      } catch (err) {
        if (!ignore) {
          setStatusMessage(err.message || (isEnglish ? 'Failed to load Binance settings.' : '无法加载 Binance 设置。'));
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      ignore = true;
    };
  }, [isEnglish]);

  const statusLabel = useMemo(() => {
    const pack = STATUS_LABELS[followStatus] || STATUS_LABELS.disabled;
    return isEnglish ? pack.en : pack.zh;
  }, [followStatus, isEnglish]);

  const handleChange = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
    if (field === 'apiKey' || field === 'apiSecret') {
      setResetCredentials(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatusMessage('');
    setLoading(true);
    try {
      const payload = {
        enabled: Boolean(form.enabled),
        walletAddress: form.walletAddress.trim() || null,
        mode: form.mode || 'fixed',
        amount: Number(form.amount) || 0,
        stopLossAmount: Number(form.stopLossAmount) || 0,
        maxPosition: Number(form.maxPosition) || 0,
        minOrderSize: Number(form.minOrderSize) || 0,
        apiKey: form.apiKey.trim() || null,
        apiSecret: form.apiSecret.trim() || null,
        resetCredentials,
      };
      const record = await saveBinanceFollowConfig(payload);
      setHasApiKey(Boolean(record.hasApiKey));
      setHasApiSecret(Boolean(record.hasApiSecret));
      setFollowStatus(record.status || (record.enabled ? 'active' : 'disabled'));
      setStopReason(record.stopReason || '');
      setBaselineBalance(
        typeof record.baselineBalance === 'number' ? record.baselineBalance : null,
      );
      setForm((prev) => ({
        ...prev,
        enabled: Boolean(record.enabled),
        walletAddress: record.walletAddress || '',
        mode: record.mode || 'fixed',
        amount: record.amount != null ? String(record.amount) : '',
        stopLossAmount: record.stopLossAmount != null ? String(record.stopLossAmount) : '',
        maxPosition: record.maxPosition != null ? String(record.maxPosition) : '',
        minOrderSize: record.minOrderSize != null ? String(record.minOrderSize) : '',
        apiKey: '',
        apiSecret: '',
      }));
      setResetCredentials(false);
      setStatusMessage(isEnglish ? 'Binance settings saved.' : 'Binance 设置已保存。');
    } catch (err) {
      setStatusMessage(err.message || (isEnglish ? 'Save failed, please retry later.' : '保存失败，请稍后重试。'));
    } finally {
      setLoading(false);
    }
  };

  const handleResetCredentials = () => {
    setForm((prev) => ({
      ...prev,
      apiKey: '',
      apiSecret: '',
    }));
    setResetCredentials(true);
    setHasApiKey(false);
    setHasApiSecret(false);
    setStatusMessage(
      isEnglish
        ? 'Credentials will be cleared after saving.'
        : '保存后将清除已保存的 API 凭证。',
    );
  };

  return (
    <section className="dashboard__section binance-follow">
      <div className="monitor-config__header">
        <div>
          <h2>{isEnglish ? 'Binance Auto Follow' : 'Binance 自动跟单'}</h2>
          <p>
            {isEnglish
              ? 'Follow your Hyperliquid wallet trades on Binance USDT-M futures with matched leverage.'
              : '使用与 Hyperliquid 相同的杠杆，在 Binance U 本位合约自动复制交易。'}
          </p>
        </div>
        {statusMessage ? <div className="monitor-config__status">{statusMessage}</div> : null}
      </div>

      <div className="binance-follow__status">
        <span className={`binance-follow__badge binance-follow__badge--${followStatus}`}>
          {statusLabel}
        </span>
        {stopReason ? (
          <span className="binance-follow__status-text">
            {isEnglish ? 'Reason:' : '原因：'}
            {stopReason}
          </span>
        ) : null}
        {baselineBalance != null ? (
          <span className="binance-follow__status-text">
            {isEnglish ? 'Baseline balance:' : '基准余额：'}
            {baselineBalance.toFixed(2)}
            {' '}
            USDT
          </span>
        ) : null}
      </div>

      <form className="monitor-config__form" onSubmit={handleSubmit}>
        <div className="monitor-config__fieldset">
          <span className="monitor-config__legend">{isEnglish ? 'Binance Account' : 'Binance 账户'}</span>
          <label className="monitor-config__field monitor-config__field--inline">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={handleChange('enabled')}
              disabled={loading}
            />
            <span>{isEnglish ? 'Enable auto follow' : '启用自动跟单'}</span>
          </label>

          <label className="monitor-config__field">
            <span>{isEnglish ? 'Hyperliquid wallet to follow' : '跟随的 Hyperliquid 钱包地址'}</span>
            <input
              type="text"
              value={form.walletAddress}
              onChange={handleChange('walletAddress')}
              placeholder="0x..."
              disabled={loading}
            />
            <small>
              {isEnglish
                ? 'Trades from this wallet will be mirrored on Binance using the selected size mode.'
                : '来自该地址的交易将按所选模式复制到 Binance。'}
            </small>
          </label>

          <div className="monitor-config__input-row">
            <label className="monitor-config__field">
              <span>{isEnglish ? 'API Key' : 'API Key'}</span>
              <input
                type="text"
                value={form.apiKey}
                onChange={handleChange('apiKey')}
                placeholder={isEnglish ? (hasApiKey ? 'Already stored' : 'Paste Binance API Key') : hasApiKey ? '已保存' : '粘贴 Binance API Key'}
                disabled={loading}
                autoComplete="off"
              />
              {hasApiKey ? (
                <small>{isEnglish ? 'A key is stored on the server.' : '服务器已保存一份 API Key。'}</small>
              ) : null}
            </label>

            <label className="monitor-config__field">
              <span>{isEnglish ? 'API Secret' : 'API Secret'}</span>
              <input
                type="password"
                value={form.apiSecret}
                onChange={handleChange('apiSecret')}
                placeholder={isEnglish ? (hasApiSecret ? 'Already stored' : 'Paste Binance API Secret') : hasApiSecret ? '已保存' : '粘贴 Binance API Secret'}
                disabled={loading}
                autoComplete="off"
              />
              {hasApiSecret ? (
                <small>
                  {isEnglish ? 'A secret is stored on the server.' : '服务器已保存一份 API Secret。'}
                </small>
              ) : null}
            </label>
          </div>

          {(hasApiKey || hasApiSecret) ? (
            <button
              type="button"
              className="binance-follow__reset"
              onClick={handleResetCredentials}
              disabled={loading}
            >
              {isEnglish ? 'Reset saved credentials' : '重置已保存的凭证'}
            </button>
          ) : null}
        </div>

        <div className="monitor-config__fieldset">
          <span className="monitor-config__legend">{isEnglish ? 'Order size & risk' : '下单与风控'}</span>

          <div className="monitor-config__input-row">
            <label className="monitor-config__field">
              <span>{isEnglish ? 'Size mode' : '份额模式'}</span>
              <select value={form.mode} onChange={handleChange('mode')} disabled={loading}>
                {MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {isEnglish ? option.labelEn : option.labelZh}
                  </option>
                ))}
              </select>
            </label>

            <label className="monitor-config__field">
              <span>
                {form.mode === 'percentage'
                  ? (isEnglish ? 'Percentage (%)' : '百分比 (%)')
                  : (isEnglish ? 'Fixed size (contracts)' : '固定份额（合约张数）')}
              </span>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={form.amount}
                onChange={handleChange('amount')}
                disabled={loading}
              />
            </label>
          </div>

          <div className="monitor-config__input-row">
            <label className="monitor-config__field">
              <span>{isEnglish ? 'Stop-loss threshold (USDT)' : '止损金额阈值 (USDT)'}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.stopLossAmount}
                onChange={handleChange('stopLossAmount')}
                disabled={loading}
              />
              <small>
                {isEnglish
                  ? 'When cumulative loss exceeds this amount the bot will stop automatically.'
                  : '当累计亏损超过此金额时自动停止跟单。'}
              </small>
            </label>

            <label className="monitor-config__field">
              <span>{isEnglish ? 'Maximum position (contracts)' : '最大持仓（合约张数）'}</span>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={form.maxPosition}
                onChange={handleChange('maxPosition')}
                disabled={loading}
              />
            </label>
          </div>

          <label className="monitor-config__field">
            <span>{isEnglish ? 'Minimum order size (contracts)' : '最小下单量（合约张数）'}</span>
            <input
              type="number"
              step="0.0001"
              min="0"
              value={form.minOrderSize}
              onChange={handleChange('minOrderSize')}
              disabled={loading}
            />
            <small>
              {isEnglish
                ? 'Orders smaller than this value will be skipped to avoid Binance minimum lot errors.'
                : '订单数量低于该值时将被跳过，以避免 Binance 最小下单量限制。'}
            </small>
          </label>
        </div>

        <div className="monitor-config__actions">
          <button type="submit" disabled={loading}>
            {loading ? (isEnglish ? 'Processing…' : '处理中…') : isEnglish ? 'Save' : '保存配置'}
          </button>
          <p className="monitor-config__hint">
            {isEnglish
              ? 'Use trade-only API keys. Withdraw permission must remain disabled.'
              : '请使用仅开放交易权限的 API Key，禁止开启提现权限。'}
          </p>
        </div>
      </form>
    </section>
  );
}

