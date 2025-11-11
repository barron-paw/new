import { useCallback } from 'react';
import './WalletSelector.css';
import { useLanguage } from '../context/LanguageContext.jsx';

export function WalletSelector({ value, onChange, onRefresh, isLoading }) {
  const { language } = useLanguage();
  const isEnglish = language === 'en';
  const handleInputChange = useCallback(
    (event) => {
      onChange?.(event.target.value);
    },
    [onChange],
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        onRefresh?.();
      }
    },
    [onRefresh],
  );

  return (
    <div className="wallet-selector">
      <div className="wallet-selector__input-wrapper">
        <label className="wallet-selector__label" htmlFor="wallet-input">
          {isEnglish ? 'Wallet' : '钱包'}
        </label>
        <input
          id="wallet-input"
          type="text"
          className="wallet-selector__input"
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={isEnglish ? 'Enter wallet address' : '请输入钱包地址'}
          spellCheck="false"
        />
      </div>

      <button
        type="button"
        className="wallet-selector__refresh"
        onClick={onRefresh}
        disabled={!value.trim() || isLoading}
      >
        {isLoading ? (isEnglish ? 'Loading…' : '加载中…') : isEnglish ? 'Refresh' : '刷新'}
      </button>
    </div>
  );
}

export default WalletSelector;
