import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { accountsApi, dashboardApi } from '../services/api';
import type { Account, AccountLedger } from '../types';

const Accounts = () => {
  const { id } = useParams<{ id: string }>();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [ledger, setLedger] = useState<AccountLedger | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAccounts();
  }, []);

  useEffect(() => {
    if (id) {
      const accountId = parseInt(id);
      const account = accounts.find(acc => acc.id === accountId);
      if (account) {
        setSelectedAccount(account);
        fetchLedger(accountId);
      }
    } else if (accounts.length > 0) {
      setSelectedAccount(accounts[0]);
      fetchLedger(accounts[0].id);
    }
  }, [id, accounts]);

  const fetchAccounts = async () => {
    try {
      const response = await accountsApi.getAll();
      setAccounts(response.data);
    } catch (err) {
      setError('Failed to load accounts');
    } finally {
      setLoading(false);
    }
  };

  const fetchLedger = async (accountId: number) => {
    try {
      const response = await dashboardApi.getAccountLedger(accountId);
      setLedger(response.data);
    } catch (err) {
      setError('Failed to load account ledger');
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getDebitEntries = () => {
    return ledger?.ledger_entries.filter(entry => entry.side === 'DR') || [];
  };

  const getCreditEntries = () => {
    return ledger?.ledger_entries.filter(entry => entry.side === 'CR') || [];
  };

  if (loading) {
    return <div className="loading">Loading accounts...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Accounts</h1>
      </div>

      {/* Account Selector */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Select Account</h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
          {accounts.map(account => (
            <button
              key={account.id}
              className={`btn ${selectedAccount?.id === account.id ? 'btn-primary' : ''}`}
              onClick={() => {
                setSelectedAccount(account);
                fetchLedger(account.id);
              }}
              style={{ 
                textAlign: 'left',
                padding: 12,
                height: 'auto'
              }}
            >
              <div style={{ fontWeight: 600 }}>{account.name}</div>
              <div style={{ fontSize: '0.875rem', opacity: 0.7 }}>{account.type}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Account Details and T-Account */}
      {selectedAccount && ledger && (
        <>
          {/* Account Header */}
          <div className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">{selectedAccount.name}</h2>
                <p style={{ color: '#666', margin: 0 }}>
                  {selectedAccount.type} • {selectedAccount.currency}
                </p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                  {formatCurrency(ledger.account.current_balance)}
                </div>
                <div style={{ color: '#666', fontSize: '0.875rem' }}>Current Balance</div>
              </div>
            </div>
          </div>

          {/* T-Account Ledger */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">T-Account Ledger</h3>
              <span style={{ color: '#666' }}>
                {ledger.total_entries} entries
              </span>
            </div>

            {ledger.ledger_entries.length > 0 ? (
              <div className="ledger-table">
                {/* Debits Side */}
                <div className="ledger-side">
                  <div className="ledger-header">
                    Debits
                  </div>
                  {getDebitEntries().map(entry => (
                    <div key={entry.transaction_line_id} className="ledger-entry">
                      <div className="ledger-date">{formatDate(entry.date)}</div>
                      <div className="ledger-memo">
                        <div>{entry.memo}</div>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>{entry.transaction_type}</div>
                      </div>
                      <div className="ledger-amount">{formatCurrency(entry.amount)}</div>
                    </div>
                  ))}
                  {getDebitEntries().length === 0 && (
                    <div style={{ padding: 20, textAlign: 'center', color: '#666' }}>
                      No debit entries
                    </div>
                  )}
                </div>

                {/* Credits Side */}
                <div className="ledger-side">
                  <div className="ledger-header">
                    Credits
                  </div>
                  {getCreditEntries().map(entry => (
                    <div key={entry.transaction_line_id} className="ledger-entry">
                      <div className="ledger-date">{formatDate(entry.date)}</div>
                      <div className="ledger-memo">
                        <div>{entry.memo}</div>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>{entry.transaction_type}</div>
                      </div>
                      <div className="ledger-amount">{formatCurrency(entry.amount)}</div>
                    </div>
                  ))}
                  {getCreditEntries().length === 0 && (
                    <div style={{ padding: 20, textAlign: 'center', color: '#666' }}>
                      No credit entries
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
                No transactions found for this account
              </div>
            )}
          </div>

          {/* Transaction History Table */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Transaction History</h3>
            </div>
            {ledger.ledger_entries.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Type</th>
                    <th>Side</th>
                    <th>Amount</th>
                    <th>Running Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.ledger_entries.map(entry => (
                    <tr key={entry.transaction_line_id}>
                      <td>{formatDate(entry.date)}</td>
                      <td>{entry.memo}</td>
                      <td>{entry.transaction_type}</td>
                      <td>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: 4,
                          fontSize: '0.75rem',
                          backgroundColor: entry.side === 'DR' ? '#e8f5e8' : '#fff3cd',
                          color: entry.side === 'DR' ? '#155724' : '#856404'
                        }}>
                          {entry.side}
                        </span>
                      </td>
                      <td className="amount">{formatCurrency(entry.amount)}</td>
                      <td className={`amount ${entry.running_balance >= 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(entry.running_balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
                No transactions found for this account
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default Accounts;