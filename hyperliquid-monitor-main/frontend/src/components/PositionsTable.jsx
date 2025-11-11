import './PositionsTable.css';
import { formatNumber, formatPercentage, formatPrice } from '../utils/format';
import { useLanguage } from '../context/LanguageContext.jsx';

export function PositionsTable({ positions }) {
  const { language } = useLanguage();
  const isEnglish = language === 'en';

  const translateSide = (side) => {
    if (isEnglish) {
      if (side === '多' || side === 'long') return 'Long';
      if (side === '空' || side === 'short') return 'Short';
      return side === 'flat' ? 'Flat' : side;
    }
    if (side === 'long') return '多';
    if (side === 'short') return '空';
    if (side === 'flat') return '空仓';
    return side;
  };

  if (!positions?.length) {
    return (
      <section className="positions-table positions-table--empty">
        <h3>{isEnglish ? 'Open Positions' : '当前持仓'}</h3>
        <p>{isEnglish ? 'No active positions for this wallet.' : '当前钱包暂无持仓。'}</p>
      </section>
    );
  }

  return (
    <section className="positions-table">
      <h3>{isEnglish ? 'Open Positions' : '当前持仓'}</h3>
      <div className="positions-table__container">
        <table>
          <thead>
            <tr>
              <th>{isEnglish ? 'Market' : '交易对'}</th>
              <th>{isEnglish ? 'Side' : '方向'}</th>
              <th>{isEnglish ? 'Size' : '数量'}</th>
              <th>{isEnglish ? 'Entry' : '开仓价'}</th>
              <th>{isEnglish ? 'Mark' : '标记价'}</th>
              <th>{isEnglish ? 'Value' : '价值'}</th>
              <th>{isEnglish ? 'Unrealized PnL' : '未实现盈亏'}</th>
              <th>{isEnglish ? 'Margin Used' : '已用保证金'}</th>
              <th>{isEnglish ? 'Leverage' : '杠杆'}</th>
              <th>{isEnglish ? 'Liq. Price' : '强平价'}</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr key={position.coin}>
                <td>{position.coin}/USDC</td>
                <td className={`positions-table__side positions-table__side--${position.side}`}>
                  {translateSide(position.side)}
                </td>
                <td>{formatNumber(position.size, { maximumFractionDigits: 6 })}</td>
                <td>{formatPrice(position.entryPrice)}</td>
                <td>{formatPrice(position.markPrice)}</td>
                <td>{formatNumber(position.positionValue)}</td>
                <td>
                  {formatNumber(position.unrealizedPnl)}
                  <span className="positions-table__pnl-percent">
                    {formatPercentage(position.pnlPercent)}
                  </span>
                </td>
                <td>{formatNumber(position.marginUsed)}</td>
                <td>{position.leverage ? `${formatNumber(position.leverage, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}x` : 'N/A'}</td>
                <td>{formatPrice(position.liquidationPrice)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default PositionsTable;
