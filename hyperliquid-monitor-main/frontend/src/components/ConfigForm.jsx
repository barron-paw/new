import { useState, useEffect } from 'react';
import './ConfigForm.css';
import { fetchConfig, updateConfig } from '../api/config';

export function ConfigForm({ onUpdate }) {
  const [formData, setFormData] = useState({
    telegramBotToken: '',
    telegramChatId: '',
    walletAddresses: '',
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    setError('');
    try {
      const config = await fetchConfig();
      setFormData({
        telegramBotToken: config.telegramBotToken ?? '',
        telegramChatId: config.telegramChatId ?? '',
        walletAddresses: Array.isArray(config.walletAddresses) && config.walletAddresses.length > 0
          ? config.walletAddresses.join('\n')
          : '',
      });
    } catch (err) {
      setError(err.message || 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      // Parse wallet addresses from textarea (one per line or comma-separated)
      const walletAddresses = formData.walletAddresses
        .split(/[,\n]/)
        .map((addr) => addr.trim())
        .filter((addr) => addr.length > 0);

      // Build config object, only include fields that have values
      const config = {};
      const token = formData.telegramBotToken.trim();
      const chatId = formData.telegramChatId.trim();
      
      if (token) {
        config.telegramBotToken = token;
      }
      if (chatId) {
        config.telegramChatId = chatId;
      }
      // Always include walletAddresses, even if empty array
      config.walletAddresses = walletAddresses;

      await updateConfig(config);
      setSuccess('Configuration updated successfully!');
      
      // Reload config to get the updated values
      await loadConfig();
      
      // Notify parent component
      if (onUpdate) {
        onUpdate();
      }
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.message || 'Failed to update configuration');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="config-form">
      <div className="config-form__header">
        <h2 className="config-form__title">监控配置</h2>
        <button
          type="button"
          className="config-form__toggle"
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={isExpanded ? 'config-form__toggle-icon--expanded' : ''}
          >
            <path
              d="M5 7.5L10 12.5L15 7.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {isExpanded && (
        <form className="config-form__form" onSubmit={handleSubmit}>
          {error && (
            <div className="config-form__message config-form__message--error">
              {error}
            </div>
          )}
          {success && (
            <div className="config-form__message config-form__message--success">
              {success}
            </div>
          )}

          <div className="config-form__field">
            <label htmlFor="telegram-bot-token" className="config-form__label">
              Telegram Bot Token
            </label>
            <input
              id="telegram-bot-token"
              type="text"
              className="config-form__input"
              value={formData.telegramBotToken}
              onChange={(e) => handleChange('telegramBotToken', e.target.value)}
              placeholder="Enter your Telegram bot token"
              disabled={loading || saving}
            />
            <p className="config-form__hint">
              Your Telegram bot token for sending notifications
            </p>
          </div>

          <div className="config-form__field">
            <label htmlFor="telegram-chat-id" className="config-form__label">
              Telegram Chat ID
            </label>
            <input
              id="telegram-chat-id"
              type="text"
              className="config-form__input"
              value={formData.telegramChatId}
              onChange={(e) => handleChange('telegramChatId', e.target.value)}
              placeholder="Enter your Telegram chat ID"
              disabled={loading || saving}
            />
            <p className="config-form__hint">
              Your Telegram chat ID where notifications will be sent
            </p>
          </div>

          <div className="config-form__field">
            <label htmlFor="wallet-addresses" className="config-form__label">
              Wallet Addresses
            </label>
            <textarea
              id="wallet-addresses"
              className="config-form__textarea"
              value={formData.walletAddresses}
              onChange={(e) => handleChange('walletAddresses', e.target.value)}
              placeholder="Enter wallet addresses (one per line or comma-separated)"
              rows="4"
              disabled={loading || saving}
            />
            <p className="config-form__hint">
              Wallet addresses to monitor (one per line or comma-separated)
            </p>
          </div>

          <div className="config-form__actions">
            <button
              type="button"
              className="config-form__button config-form__button--secondary"
              onClick={loadConfig}
              disabled={loading || saving}
            >
              {loading ? 'Loading...' : 'Reload'}
            </button>
            <button
              type="submit"
              className="config-form__button config-form__button--primary"
              disabled={loading || saving}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default ConfigForm;

