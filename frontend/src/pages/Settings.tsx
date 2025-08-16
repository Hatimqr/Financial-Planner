import { useState, useEffect } from 'react';
import { Edit, Trash2, Plus } from 'lucide-react';
import { accountsApi } from '../services/api';
import type { Account } from '../types';

const Settings = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);

  useEffect(() => {
    fetchAccounts();
  }, []);

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

  const handleDeleteAccount = async (account: Account) => {
    if (window.confirm(`Are you sure you want to delete "${account.name}"?`)) {
      try {
        await accountsApi.delete(account.id);
        await fetchAccounts();
      } catch (err) {
        setError('Failed to delete account');
      }
    }
  };

  const formatCurrency = (amount: number | undefined) => {
    if (amount === undefined) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  if (loading) {
    return <div className="loading">Loading settings...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      {error && <div className="error">{error}</div>}

      {/* Manage Accounts */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Manage Accounts</h2>
          <button 
            className="btn btn-primary"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus size={16} /> Add Account
          </button>
        </div>

        {accounts.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th>Account Name</th>
                <th>Type</th>
                <th>Currency</th>
                <th>Current Balance</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(account => (
                <tr key={account.id}>
                  <td style={{ fontWeight: 500 }}>{account.name}</td>
                  <td>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: '0.75rem',
                      backgroundColor: '#f8f9fa',
                      border: '1px solid #dee2e6'
                    }}>
                      {account.type}
                    </span>
                  </td>
                  <td>{account.currency}</td>
                  <td className={`amount ${(account.balance || 0) >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(account.balance)}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        className="btn"
                        onClick={() => setEditingAccount(account)}
                        style={{ padding: 6 }}
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={() => handleDeleteAccount(account)}
                        style={{ padding: 6 }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
            No accounts found. Create your first account to get started.
          </div>
        )}
      </div>

      {/* System Information */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">System Information</h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '12px 24px', alignItems: 'center' }}>
          <span style={{ fontWeight: 500 }}>API Base URL:</span>
          <span style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
            http://localhost:8000/api
          </span>
          
          <span style={{ fontWeight: 500 }}>Database:</span>
          <span style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
            SQLite (Local)
          </span>
          
          <span style={{ fontWeight: 500 }}>Total Accounts:</span>
          <span>{accounts.length}</span>
        </div>
      </div>

      {/* Account Modals */}
      {showCreateModal && (
        <AccountModal
          onClose={() => setShowCreateModal(false)}
          onSave={() => {
            setShowCreateModal(false);
            fetchAccounts();
          }}
        />
      )}

      {editingAccount && (
        <AccountModal
          account={editingAccount}
          onClose={() => setEditingAccount(null)}
          onSave={() => {
            setEditingAccount(null);
            fetchAccounts();
          }}
        />
      )}
    </div>
  );
};

interface AccountModalProps {
  account?: Account;
  onClose: () => void;
  onSave: () => void;
}

const AccountModal = ({ account, onClose, onSave }: AccountModalProps) => {
  const [name, setName] = useState(account?.name || '');
  const [type, setType] = useState<Account['type']>(account?.type || 'ASSET');
  const [currency, setCurrency] = useState(account?.currency || 'USD');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (account) {
        await accountsApi.update(account.id, { name, type, currency });
      } else {
        await accountsApi.create({ name, type, currency });
      }
      onSave();
    } catch (err) {
      setError('Failed to save account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal">
      <div className="modal-content">
        <div className="modal-header">
          <h2 className="modal-title">
            {account ? 'Edit Account' : 'Create Account'}
          </h2>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Account Name</label>
            <input
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Chase Checking"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Account Type</label>
            <select
              className="form-select"
              value={type}
              onChange={(e) => setType(e.target.value as Account['type'])}
              required
            >
              <option value="ASSET">Asset</option>
              <option value="LIABILITY">Liability</option>
              <option value="EQUITY">Equity</option>
              <option value="INCOME">Income</option>
              <option value="EXPENSE">Expense</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Currency</label>
            <select
              className="form-select"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              required
            >
              <option value="USD">USD - US Dollar</option>
              <option value="EUR">EUR - Euro</option>
              <option value="GBP">GBP - British Pound</option>
              <option value="CAD">CAD - Canadian Dollar</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : 'Save Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Settings;