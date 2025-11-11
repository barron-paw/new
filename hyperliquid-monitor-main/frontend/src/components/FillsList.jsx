import './FillsList.css';
import { formatNumber, formatPrice, formatTimestamp } from '../utils/format';
import { useLanguage } from '../context/LanguageContext.jsx';

export function FillsList({ fills }) {
  const { language } = useLanguage();
  const isEnglish = language === 'en';

  const translateSide = (side) => {
    if (isEnglish) {
      if (side === 'B' || side === 'buy') return 'Buy';
      if (side === 'A' || side === 'sell') return 'Sell';
      return side;
    }
    if (side === 'B' || side === 'buy') return '买入';
    if (side === 'A' || side === 'sell') return '卖出';
    return side;
  };

  return (
    <section className="fills-list">
      <div className="fills-list__header">
        <h3>{isEnglish ? 'Recent Fills' : '最新成交'}</h3>
        <span>
          {fills.length} {isEnglish ? 'events' : '笔'}
        </span>
      </div>
      {fills.length ? (
        <ul>
          {fills.map((fill) => (
            <li key={`${fill.txHash}-${fill.timeMs}`} className="fills-list__item">
              <div>
                <strong>{fill.coin}</strong>
                <span className={`fills-list__side fills-list__side--${fill.side}`}>
                  {translateSide(fill.side)}
                </span>
              </div>
              <div className="fills-list__details">
                <span>{formatPrice(fill.price)}</span>
                <span>{formatNumber(fill.size, { maximumFractionDigits: 6 })}</span>
                <span>{formatTimestamp(fill.timeMs)}</span>
              </div>
              <div className="fills-list__hash">{fill.txHash}</div>
            </li>
          ))}
        </ul>
      ) : (
        <p>{isEnglish ? 'No fills recorded for this wallet.' : '该钱包暂无成交记录。'}</p>
      )}
    </section>
  );
}

export default FillsList;
