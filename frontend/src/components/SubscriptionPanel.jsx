import { useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { verifySubscription } from '../api/subscription.js';
import { useLanguage } from '../context/LanguageContext.jsx';

const PAYMENT_ADDRESS = '0xa0191ab9cad3dae4ce390d633c6c467da0ca975d';
const PAYMENT_AMOUNT = '7.9 USDT (BEP-20)';

function formatRemaining(user, language) {
  const isEnglish = language === 'en';
  if (!user) {
    return '';
  }
  const now = new Date();
  if (user.subscription_active && user.subscription_end) {
    const end = new Date(user.subscription_end);
    const days = Math.max(0, Math.ceil((end - now) / (1000 * 60 * 60 * 24)));
    return isEnglish ? `Subscription active, ~${days} days remaining` : `订阅有效，剩余约 ${days} 天`;
  }
  if (user.trial_active && user.trial_end) {
    const end = new Date(user.trial_end);
    const days = Math.max(0, Math.ceil((end - now) / (1000 * 60 * 60 * 24)));
    return isEnglish ? `Trial active, ~${days} days remaining` : `试用期剩余约 ${days} 天`;
  }
  return isEnglish ? 'Trial expired. Please subscribe to continue.' : '试用期已结束，请充值后继续使用监控配置';
}

export default function SubscriptionPanel() {
  const { user, refreshUser } = useAuth();
  const { language } = useLanguage();
  const isEnglish = language === 'en';
  const [txHash, setTxHash] = useState('');
  const [status, setStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const remaining = useMemo(() => formatRemaining(user, language), [user, language]);

  if (!user) {
    return (
      <section className="dashboard__section">
        <h2>{isEnglish ? 'Membership Subscription' : '会员订阅'}</h2>
        <p>
          {isEnglish
            ? 'Please log in or register first. A 3-day free trial will be granted automatically.'
            : '请先登录或注册账号，系统将自动赠送 3 天试用期。'}
        </p>
      </section>
    );
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!txHash.trim()) {
      setStatus(isEnglish ? 'Please enter a valid transaction hash.' : '请输入有效的交易哈希');
      return;
    }
    try {
      setSubmitting(true);
      setStatus(isEnglish ? 'Verifying transaction on-chain…' : '正在验证链上交易，请稍候…');
      await verifySubscription(txHash.trim());
      await refreshUser();
      setStatus(isEnglish ? 'Payment confirmed. Subscription activated!' : '支付已确认，订阅已激活！');
      setTxHash('');
    } catch (err) {
      setStatus(err.message || (isEnglish ? 'Verification failed. Please confirm the hash.' : '验证失败，请确认哈希是否正确。'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="dashboard__section subscription-panel">
      <div className="subscription-panel__content">
        <div>
          <h2>{isEnglish ? 'Membership Subscription' : '会员订阅'}</h2>
          <p className="subscription-panel__status">{remaining}</p>
          <ul className="subscription-panel__list">
            <li>{isEnglish ? `Price: ${PAYMENT_AMOUNT}` : `费用：${PAYMENT_AMOUNT}`}</li>
            <li>
              {isEnglish ? 'Recipient address (BSC):' : '收款地址（BSC）：'}
              <code>{PAYMENT_ADDRESS}</code>
            </li>
            <li>
              {isEnglish
                ? 'After completing the payment, submit the transaction hash to extend your subscription.'
                : '完成支付后提交交易哈希，系统会自动延长订阅有效期。'}
            </li>
          </ul>
          <p className="subscription-panel__notice">
            {isEnglish
              ? 'Note: the payment amount must be ≥ 7.9 USDT, otherwise the subscription may fail.'
              : '注意：支付金额必须 ≥ 7.9 USDT，否则可能会订阅失败。'}
          </p>
        </div>
        <form className="subscription-panel__form" onSubmit={handleSubmit}>
          <label>
            {isEnglish ? 'Transaction Hash (Tx Hash)' : '交易哈希 (Tx Hash)'}
            <input
              type="text"
              value={txHash}
              onChange={(event) => setTxHash(event.target.value)}
              placeholder={isEnglish ? '0x...' : '0x...'}
              required
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? (isEnglish ? 'Verifying…' : '验证中…') : isEnglish ? 'Submit' : '提交验证'}
          </button>
          {status ? <p className="subscription-panel__message">{status}</p> : null}
        </form>
      </div>
    </section>
  );
}
