import './MetricsGrid.css';
import { formatCurrency, formatNumber } from '../utils/format';
import { useLanguage } from '../context/LanguageContext.jsx';

export function MetricsGrid({ summary }) {
  const { language } = useLanguage();
  const isEnglish = language === 'en';
  if (!summary) {
    return null;
  }

  const cards = [
    {
      title: isEnglish ? 'Account Equity' : '账户权益',
      value: formatCurrency(summary.equity ?? summary.balance ?? 0),
      hint: isEnglish ? 'Account value reported by Hyperliquid' : '来自 Hyperliquid 的账户权益数值',
    },
    {
      title: isEnglish ? 'Withdrawable' : '可提金额',
      value: formatCurrency(summary.withdrawable ?? 0),
      hint: isEnglish ? 'Funds available for withdrawal' : '可随时提取的资金',
    },
    {
      title: isEnglish ? 'Open Position Value' : '持仓价值',
      value: formatCurrency(summary.totalPositionValue ?? 0),
      hint: isEnglish ? 'Sum of absolute position notionals' : '所有持仓名义价值的总和',
    },
    {
      title: isEnglish ? 'Positions Held' : '持仓数量',
      value: formatNumber(summary.positions?.length ?? 0, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }),
      hint: isEnglish ? 'Distinct markets with exposure' : '当前有敞口的交易对数量',
    },
  ];

  return (
    <section className="metrics-grid">
      {cards.map((card) => (
        <article key={card.title} className="metrics-grid__card">
          <h3>{card.title}</h3>
          <p className="metrics-grid__value">{card.value}</p>
          <p className="metrics-grid__hint">{card.hint}</p>
        </article>
      ))}
    </section>
  );
}

export default MetricsGrid;
