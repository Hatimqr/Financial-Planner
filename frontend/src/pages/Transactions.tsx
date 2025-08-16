import { useState, useEffect } from 'react';
import { Trash2, Plus, Filter, X, Send, CheckCircle } from 'lucide-react';
import { transactionsApi, dashboardApi } from '../services/api';
import TransactionModal from '../components/TransactionModal';
import type { Transaction } from '../types';

const Transactions = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [filteredTransactions, setFilteredTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [posting, setPosting] = useState<number | null>(null);
  const [postingAll, setPostingAll] = useState(false);
  
  // Filter states
  const [filters, setFilters] = useState({
    type: '',
    status: '',
    dateFrom: '',
    dateTo: '',
    memo: ''
  });
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchTransactions();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [transactions, filters]);

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      const response = await transactionsApi.getAll();
      setTransactions(response.data);
    } catch (err) {
      setError('Failed to load transactions');
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = transactions;

    if (filters.type) {
      filtered = filtered.filter(tx => tx.type.toLowerCase().includes(filters.type.toLowerCase()));
    }
    if (filters.status) {
      filtered = filtered.filter(tx => (tx.status || 'draft').toLowerCase().includes(filters.status.toLowerCase()));
    }
    if (filters.memo) {
      filtered = filtered.filter(tx => tx.memo.toLowerCase().includes(filters.memo.toLowerCase()));
    }
    if (filters.dateFrom) {
      filtered = filtered.filter(tx => tx.date >= filters.dateFrom);
    }
    if (filters.dateTo) {
      filtered = filtered.filter(tx => tx.date <= filters.dateTo);
    }

    setFilteredTransactions(filtered);
  };

  const clearFilters = () => {
    setFilters({
      type: '',
      status: '',
      dateFrom: '',
      dateTo: '',
      memo: ''
    });
  };

  const handleDelete = async (transactionId: number) => {
    if (!confirm('Are you sure you want to delete this transaction? This action cannot be undone.')) {
      return;
    }

    try {
      setDeleting(transactionId);
      await transactionsApi.delete(transactionId);
      
      // Refresh the transactions list
      await fetchTransactions();
    } catch (err: any) {
      alert('Failed to delete transaction');
      console.error(err);
    } finally {
      setDeleting(null);
    }
  };

  const handlePost = async (transactionId: number) => {
    try {
      setPosting(transactionId);
      await transactionsApi.post(transactionId);
      
      // Refresh the transactions list
      await fetchTransactions();
    } catch (err: any) {
      alert('Failed to post transaction');
      console.error(err);
    } finally {
      setPosting(null);
    }
  };

  const handlePostAll = async () => {
    const draftTransactions = filteredTransactions.filter(tx => 
      tx.status === 'draft' || !tx.status
    );
    
    if (draftTransactions.length === 0) {
      alert('No draft transactions to post');
      return;
    }

    if (!confirm(`Are you sure you want to post all ${draftTransactions.length} draft transactions? This will affect account balances.`)) {
      return;
    }

    try {
      setPostingAll(true);
      await transactionsApi.postAll(draftTransactions.map(tx => tx.id));
      
      // Refresh the transactions list
      await fetchTransactions();
    } catch (err: any) {
      alert('Failed to post some transactions');
      console.error(err);
    } finally {
      setPostingAll(false);
    }
  };

  const handleTransactionSaved = () => {
    setShowModal(false);
    fetchTransactions();
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

  const getTransactionDebits = (transaction: Transaction) => {
    return transaction.lines
      .filter(line => line.dr_cr === 'DR')
      .reduce((sum, line) => sum + line.amount, 0);
  };

  const getTransactionCredits = (transaction: Transaction) => {
    return transaction.lines
      .filter(line => line.dr_cr === 'CR')
      .reduce((sum, line) => sum + line.amount, 0);
  };

  const getDebitAccountNames = (transaction: Transaction) => {
    return transaction.lines
      .filter(line => line.dr_cr === 'DR')
      .map(line => line.account_name || `Account ${line.account_id}`)
      .join(', ');
  };

  const getCreditAccountNames = (transaction: Transaction) => {
    return transaction.lines
      .filter(line => line.dr_cr === 'CR')
      .map(line => line.account_name || `Account ${line.account_id}`)
      .join(', ');
  };

  const getTransactionAmount = (transaction: Transaction) => {
    // For double-entry, debits should equal credits, so we can use either
    return getTransactionDebits(transaction);
  };

  if (loading) {
    return <div className="loading">Loading transactions...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Transactions</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <button 
            className="btn"
            onClick={() => setShowFilters(!showFilters)}
            style={{ backgroundColor: showFilters ? '#e3f2fd' : 'transparent' }}
          >
            <Filter size={16} />
            Filters
          </button>
          <button 
            className="btn"
            onClick={handlePostAll}
            disabled={postingAll}
            style={{ backgroundColor: '#e8f5e8', color: '#155724' }}
          >
            {postingAll ? <span>Posting...</span> : <><Send size={16} /> Post All Drafts</>}
          </button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={16} />
            New Transaction
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Filters</h3>
            <button className="btn" onClick={clearFilters}>
              <X size={16} />
              Clear All
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div>
              <label className="form-label">Type</label>
              <input
                type="text"
                className="form-input"
                value={filters.type}
                onChange={(e) => setFilters({...filters, type: e.target.value})}
                placeholder="Filter by type..."
              />
            </div>
            <div>
              <label className="form-label">Status</label>
              <select
                className="form-select"
                value={filters.status}
                onChange={(e) => setFilters({...filters, status: e.target.value})}
              >
                <option value="">All Statuses</option>
                <option value="draft">Draft</option>
                <option value="posted">Posted</option>
              </select>
            </div>
            <div>
              <label className="form-label">Description</label>
              <input
                type="text"
                className="form-input"
                value={filters.memo}
                onChange={(e) => setFilters({...filters, memo: e.target.value})}
                placeholder="Filter by description..."
              />
            </div>
            <div>
              <label className="form-label">Date From</label>
              <input
                type="date"
                className="form-input"
                value={filters.dateFrom}
                onChange={(e) => setFilters({...filters, dateFrom: e.target.value})}
              />
            </div>
            <div>
              <label className="form-label">Date To</label>
              <input
                type="date"
                className="form-input"
                value={filters.dateTo}
                onChange={(e) => setFilters({...filters, dateTo: e.target.value})}
              />
            </div>
          </div>
        </div>
      )}

      {transactions.length > 0 ? (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">All Transactions</h2>
            <span style={{ color: '#666' }}>
              Showing {filteredTransactions.length} of {transactions.length} transactions
            </span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Type</th>
                <th>Status</th>
                <th>Debit Accounts</th>
                <th>Credit Accounts</th>
                <th>Amount</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredTransactions.map(transaction => (
                <tr key={transaction.id}>
                  <td>{formatDate(transaction.date)}</td>
                  <td>{transaction.memo}</td>
                  <td>{transaction.type}</td>
                  <td>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: '0.75rem',
                      backgroundColor: transaction.status === 'posted' ? '#d4edda' : '#fff3cd',
                      color: transaction.status === 'posted' ? '#155724' : '#856404'
                    }}>
                      {transaction.status?.toUpperCase() || 'DRAFT'}
                    </span>
                  </td>
                  <td>{getDebitAccountNames(transaction)}</td>
                  <td>{getCreditAccountNames(transaction)}</td>
                  <td className="amount">{formatCurrency(getTransactionAmount(transaction))}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {(transaction.status === 'draft' || !transaction.status) && (
                        <button
                          className="btn"
                          onClick={() => handlePost(transaction.id)}
                          disabled={posting === transaction.id}
                          style={{ padding: '4px 8px', backgroundColor: '#e8f5e8', color: '#155724' }}
                          title="Post transaction"
                        >
                          {posting === transaction.id ? '...' : <CheckCircle size={14} />}
                        </button>
                      )}
                      <button
                        className="btn btn-danger"
                        onClick={() => handleDelete(transaction.id)}
                        disabled={deleting === transaction.id}
                        style={{ padding: '4px 8px' }}
                        title="Delete transaction"
                      >
                        {deleting === transaction.id ? '...' : <Trash2 size={14} />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card">
          <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
            <p>No transactions found</p>
            <button className="btn btn-primary" onClick={() => setShowModal(true)}>
              Create your first transaction
            </button>
          </div>
        </div>
      )}

      {showModal && (
        <TransactionModal
          onClose={() => setShowModal(false)}
          onSave={handleTransactionSaved}
        />
      )}
    </div>
  );
};

export default Transactions;