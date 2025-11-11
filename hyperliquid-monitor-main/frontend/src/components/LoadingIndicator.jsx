import './LoadingIndicator.css';
import { useLanguage } from '../context/LanguageContext.jsx';

export function LoadingIndicator({ message }) {
  const { language } = useLanguage();
  const defaultMessage = language === 'en' ? 'Loading data…' : '数据加载中…';
  return (
    <div className="loading-indicator">
      <span className="loading-indicator__spinner" aria-hidden="true" />
      <span>{message || defaultMessage}</span>
    </div>
  );
}

export default LoadingIndicator;
