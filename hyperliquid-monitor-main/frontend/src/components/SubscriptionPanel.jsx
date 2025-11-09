import { useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { verifySubscription } from '../api/subscription.js';

const PAYMENT_ADDRESS = '0xa0191ab9cad3dae4ce390d633c6c467da0ca975d';
const PAYMENT_AMOUNT = '7.9 USDT (BEP-20)';

function formatRemaining(user) {
  if (!user) {
    return '';
  }
  const now = new Date();
  if (user.subscription_active && user.subscription_end) {
    const end = new Date(user.subscription_end);
    const days = Math.max(0, Math.ceil((end - now) / (1000 * 60 * 60 * 24)));
    return `订阅有效，剩余约 ${days} 天`; 
  }
  if (user.trial_active && user.trial_end) {
    const end = new Date(user.trial_end);
    const days = Math.max(0, Math.ceil((end - now) / (1000 * 60 * 60 * 24)));
    return `试用期剩余约 ${days} 天`; 
  }
  return '试用期已结束，请充值后继续使用监控配置';
}

export default function SubscriptionPanel() {
  const { user, refreshUser } = useAuth();
  const [txHash, setTxHash] = useState('');
  const [status, setStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const remaining = useMemo(() => formatRemaining(user), [user]);

  if (!user) {
    return (
      <section className="dashboard__section">
        <h2>会员订阅</h2>
        <p>请先登录或注册账号，系统将自动赠送 3 天试用期。</p>
      </section>
    );
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!txHash.trim()) {
      setStatus('请输入有效的交易哈希');
      return;
    }
    try {
      setSubmitting(true);
      setStatus('正在验证链上交易，请稍候…');
      await verifySubscription(txHash.trim());
      await refreshUser();
      setStatus('支付已确认，订阅已激活！');
      setTxHash('');
    } catch (err) {
      setStatus(err.message || '验证失败，请确认哈希是否正确。');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="dashboard__section subscription-panel">
      <div className="subscription-panel__content">
        <div>
          <h2>会员订阅</h2>
          <p className="subscription-panel__status">{remaining}</p>
          <ul className="subscription-panel__list">
            <li>费用：{PAYMENT_AMOUNT}</li>
            <li>收款地址（BSC）：<code>{PAYMENT_ADDRESS}</code></li>
            <li>完成支付后提交交易哈希，系统会自动延长订阅有效期。</li>
          </ul>
        </div>
        <form className="subscription-panel__form" onSubmit={handleSubmit}>
          <label>
            交易哈希 (Tx Hash)
            <input
              type="text"
              value={txHash}
              onChange={(event) => setTxHash(event.target.value)}
              placeholder="0x..."
              required
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? '验证中…' : '提交验证'}
          </button>
          {status ? <p className="subscription-panel__message">{status}</p> : null}
        </form>
      </div>
    </section>
  );
}
