import { useCallback } from 'react';
import './WalletSelector.css';

export function WalletSelector({ value, onChange, onRefresh, isLoading }) {
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
        <label className="wallet-selector__label" htmlFor="wallet-input">Wallet</label>
        <input
          id="wallet-input"
          type="text"
          className="wallet-selector__input"
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="请输入钱包地址"
          spellCheck="false"
        />
      </div>

      <button
        type="button"
        className="wallet-selector__refresh"
        onClick={onRefresh}
        disabled={!value.trim() || isLoading}
      >
        {isLoading ? '加载中…' : '刷新'}
      </button>
    </div>
  );
}

export default WalletSelector;
