import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { dashboardApi, accountsApi } from '../services/api';
import type { DashboardSummary, TimeSeriesData, Account } from '../types';

const Dashboard = () => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dateRange, setDateRange] = useState('ytd');
  const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);

  useEffect(() => {
    fetchData();
  }, [dateRange, selectedAccounts]);

  const fetchData = async () => {
    setLoading(true);
    setError('');

    try {
      // Fetch accounts
      const accountsResponse = await accountsApi.getAll();
      setAccounts(accountsResponse.data);

      // Fetch dashboard summary
      const summaryParams = selectedAccounts.length > 0 ? { account_ids: selectedAccounts } : {};
      const summaryResponse = await dashboardApi.getSummary(summaryParams);
      setSummary(summaryResponse.data);

      // Calculate date range for time series
      const endDate = new Date().toISOString().split('T')[0];
      let startDate: string;
      
      switch (dateRange) {
        case '30d':
          startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
          break;
        case 'ytd':
          startDate = new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0];
          break;
        case '1y':
          startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
          break;
        default:
          startDate = new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0];
      }

      // Fetch time series data
      const timeSeriesParams = {
        start_date: startDate,
        end_date: endDate,
        ...(selectedAccounts.length > 0 && { account_ids: selectedAccounts }),
      };
      const timeSeriesResponse = await dashboardApi.getTimeSeries(timeSeriesParams);
      setTimeSeriesData(timeSeriesResponse.data);

    } catch (err) {
      setError('Failed to load dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const groupAccountsByType = () => {
    if (!summary) return {};

    const grouped: Record<string, typeof summary.account_balances> = {
      ASSET: [],
      LIABILITY: [],
      INCOME: [],
      EXPENSE: [],
      EQUITY: [],
    };

    summary.account_balances.forEach(account => {
      if (grouped[account.account_type]) {
        grouped[account.account_type].push(account);
      }
    });

    return grouped;
  };

  const prepareChartData = () => {
    if (!timeSeriesData) return [];

    return timeSeriesData.data_points.map(point => ({
      date: point.date,
      'Net Worth': point.net_worth,
      ...Object.entries(point.accounts).reduce((acc, [accountId, balance]) => {
        const accountInfo = timeSeriesData.account_info[accountId];
        if (accountInfo) {
          acc[accountInfo.name] = balance;
        }
        return acc;
      }, {} as Record<string, number>),
    }));
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  const groupedAccounts = groupAccountsByType();
  const chartData = prepareChartData();

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
      </div>

      {/* Filters */}
      <div className="card">
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label className="form-label">Date Range</label>
            <select
              className="form-select"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              style={{ width: 'auto' }}
            >
              <option value="30d">Last 30 Days</option>
              <option value="ytd">Year to Date</option>
              <option value="1y">Last Year</option>
            </select>
          </div>

          <div style={{ flex: 1 }}>
            <label className="form-label">Accounts</label>
            <select
              className="form-select"
              multiple
              value={selectedAccounts.map(String)}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, option => Number(option.value));
                setSelectedAccounts(selected);
              }}
              style={{ height: 80 }}
            >
              {accounts.map(account => (
                <option key={account.id} value={account.id}>
                  {account.name} ({account.type})
                </option>
              ))}
            </select>
            <small style={{ color: '#666' }}>Hold Ctrl/Cmd to select multiple accounts</small>
          </div>
        </div>
      </div>

      {/* Net Worth Card */}
      {summary && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Net Worth</h2>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div 
              style={{ 
                fontSize: '2.5rem', 
                fontWeight: 'bold',
                color: summary.net_worth >= 0 ? '#27ae60' : '#e74c3c'
              }}
            >
              {formatCurrency(summary.net_worth)}
            </div>
            <div style={{ color: '#666', marginTop: 8 }}>
              Assets: {formatCurrency(summary.total_assets)} | 
              Liabilities: {formatCurrency(summary.total_liabilities)}
            </div>
          </div>
        </div>
      )}

      {/* Time Series Chart */}
      {chartData.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Account Balances Over Time</h2>
          </div>
          <div style={{ height: 400 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="date" 
                  tick={{ fontSize: 12 }}
                  tickFormatter={(value) => new Date(value).toLocaleDateString()}
                />
                <YAxis 
                  tick={{ fontSize: 12 }}
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip 
                  formatter={(value: number) => formatCurrency(value)}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="Net Worth" 
                  stroke="#3498db" 
                  strokeWidth={3}
                  dot={false}
                />
                {Object.keys(timeSeriesData?.account_info || {}).map((accountId, index) => {
                  const accountInfo = timeSeriesData?.account_info[accountId];
                  const colors = ['#e74c3c', '#27ae60', '#f39c12', '#9b59b6', '#1abc9c'];
                  return accountInfo ? (
                    <Line
                      key={accountId}
                      type="monotone"
                      dataKey={accountInfo.name}
                      stroke={colors[index % colors.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ) : null;
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Account Summaries */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
          {Object.entries(groupedAccounts).map(([type, accountList]) => {
            if (accountList.length === 0) return null;

            const total = accountList.reduce((sum, account) => sum + account.balance, 0);

            return (
              <div key={type} className="card">
                <div className="card-header">
                  <h3 className="card-title">{type.charAt(0) + type.slice(1).toLowerCase()}s</h3>
                  <span className={`amount ${total >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(total)}
                  </span>
                </div>
                <div>
                  {accountList.map(account => (
                    <div 
                      key={account.account_id}
                      style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        padding: '8px 0',
                        borderBottom: '1px solid #eee'
                      }}
                    >
                      <span>{account.account_name}</span>
                      <span className={`amount ${account.balance >= 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(account.balance)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Dashboard;