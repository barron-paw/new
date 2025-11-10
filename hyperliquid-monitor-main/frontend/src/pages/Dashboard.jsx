import './Dashboard.css';
import Layout from '../components/Layout';
import WalletSelector from '../components/WalletSelector';
import MetricsGrid from '../components/MetricsGrid';
import PositionsTable from '../components/PositionsTable';
import FillsList from '../components/FillsList';
import StatusBanner from '../components/StatusBanner';
import LoadingIndicator from '../components/LoadingIndicator';
import useWalletData from '../hooks/useWalletData';
import AccountMenu from '../components/AccountMenu.jsx';
import SubscriptionPanel from '../components/SubscriptionPanel.jsx';
import MonitorConfigPanel from '../components/MonitorConfigPanel.jsx';

export function Dashboard() {
  const {
    selectedWallet,
    setSelectedWallet,
    summary,
    positions,
    fills,
    loading,
    error,
    refresh,
  } = useWalletData();

  const header = (
    <div className="dashboard__header">
      <div>
        <h1>Hyperliquid Monitor</h1>
        <p>Live positions, balances, and fills for your tracked wallets.</p>
      </div>
    </div>
  );

  const footer = (
    <div className="dashboard__footer">
      <p>
        Data polled directly from Hyperliquid public endpoints. Refresh interval 15s. Adjust via{' '}
        <code>useWalletData</code>.
      </p>
      <p>
        联系邮箱：<a href="mailto:baobangran@gamil.com">baobangran@gamil.com</a>
      </p>
    </div>
  );

  return (
    <Layout header={header} actions={<AccountMenu />} footer={footer}>
      <SubscriptionPanel />
      <MonitorConfigPanel />

      <WalletSelector
        value={selectedWallet}
        onChange={setSelectedWallet}
        onRefresh={refresh}
        isLoading={loading}
      />

      {error ? (
        <StatusBanner kind="error" title="Unable to fetch data" description={error} />
      ) : null}

      {loading ? <LoadingIndicator /> : null}

      <MetricsGrid summary={summary} />
      <PositionsTable positions={positions} />
      <FillsList fills={fills} />
    </Layout>
  );
}

export default Dashboard;
