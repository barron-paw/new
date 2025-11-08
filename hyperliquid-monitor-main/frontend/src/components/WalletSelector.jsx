import { useState, useEffect, useRef } from 'react';
import './WalletSelector.css';

export function WalletSelector({ wallets, value, onChange, onRefresh }) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const containerRef = useRef(null);

  const handleInputChange = (event) => {
    onChange?.(event.target.value);
  };

  const handleWalletSelect = (wallet) => {
    onChange?.(wallet);
    setIsDropdownOpen(false);
  };

  const toggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen]);

  return (
    <div className="wallet-selector">
      <div className="wallet-selector__input-wrapper">
        <label className="wallet-selector__label" htmlFor="wallet-input">Wallet</label>
        <div className="wallet-selector__input-container" ref={containerRef}>
          <input
            id="wallet-input"
            type="text"
            className="wallet-selector__input"
            value={value}
            onChange={handleInputChange}
            placeholder="Enter wallet address"
          />
          {wallets.length > 0 && (
            <button
              type="button"
              className={`wallet-selector__dropdown-button ${isDropdownOpen ? 'wallet-selector__dropdown-button--open' : ''}`}
              onClick={toggleDropdown}
              aria-label="Select wallet"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4 6L8 10L12 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
          {isDropdownOpen && wallets.length > 0 && (
            <div className="wallet-selector__dropdown">
              {wallets.map((wallet) => (
                <button
                  key={wallet}
                  type="button"
                  className="wallet-selector__dropdown-item"
                  onClick={() => handleWalletSelect(wallet)}
                >
                  {wallet}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <button
        type="button"
        className="wallet-selector__refresh"
        onClick={onRefresh}
        disabled={!value}
      >
        Refresh
      </button>
    </div>
  );
}

export default WalletSelector;
