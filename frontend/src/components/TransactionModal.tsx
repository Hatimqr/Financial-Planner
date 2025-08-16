import { useState, useEffect } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';
import { accountsApi, transactionsApi } from '../services/api';
import type { Account, TransactionLine } from '../types';

interface TransactionModalProps {
  onClose: () => void;
  onSave: () => void;
}

const TransactionModal = ({ onClose, onSave }: TransactionModalProps) => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [memo, setMemo] = useState('');
  const [lines, setLines] = useState<Omit<TransactionLine, 'id'>[]>([
    { account_id: 0, dr_cr: 'DR', amount: 0 },
    { account_id: 0, dr_cr: 'CR', amount: 0 },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [postImmediately, setPostImmediately] = useState(true);

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    try {
      const response = await accountsApi.getAll();
      setAccounts(response.data);
    } catch (err) {
      setError('Failed to load accounts');
    }
  };

  const addLine = () => {
    setLines([...lines, { account_id: 0, dr_cr: 'DR', amount: 0 }]);
  };

  const removeLine = (index: number) => {
    if (lines.length > 2) {
      setLines(lines.filter((_, i) => i !== index));
    }
  };

  const updateLine = (index: number, field: keyof Omit<TransactionLine, 'id'>, value: any) => {
    const newLines = [...lines];
    newLines[index] = { ...newLines[index], [field]: value };
    setLines(newLines);
  };

  const getTotalDebits = () => {
    return lines
      .filter(line => line.dr_cr === 'DR')
      .reduce((sum, line) => sum + Number(line.amount), 0);
  };

  const getTotalCredits = () => {
    return lines
      .filter(line => line.dr_cr === 'CR')
      .reduce((sum, line) => sum + Number(line.amount), 0);
  };

  const isBalanced = () => {
    const debits = getTotalDebits();
    const credits = getTotalCredits();
    return Math.abs(debits - credits) < 0.01;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isBalanced()) {
      setError('Transaction must be balanced (Total Debits = Total Credits)');
      return;
    }

    if (lines.some(line => line.account_id === 0)) {
      setError('Please select an account for all lines');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await transactionsApi.create({
        type: 'TRANSFER',
        date,
        memo,
        auto_post: postImmediately,
        lines: lines.map(line => ({
          ...line,
          id: 0, // Will be assigned by backend
        })),
      });
      onSave();
    } catch (err) {
      setError('Failed to create transaction');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal">
      <div className="modal-content">
        <div className="modal-header">
          <h2 className="modal-title">New Transaction</h2>
          <button className="close-btn" onClick={onClose}>
            <X />
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Date</label>
            <input
              type="date"
              className="form-input"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <input
              type="text"
              className="form-input"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="Transaction description"
              required
            />
          </div>

          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <label className="form-label" style={{ margin: 0 }}>Transaction Lines</label>
              <button type="button" className="btn" onClick={addLine}>
                <Plus size={16} /> Add Line
              </button>
            </div>

            {lines.map((line, index) => (
              <div key={index} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                <select
                  className="form-select"
                  value={line.account_id}
                  onChange={(e) => updateLine(index, 'account_id', Number(e.target.value))}
                  style={{ flex: 2 }}
                  required
                >
                  <option value={0}>Select Account</option>
                  {accounts.map(account => (
                    <option key={account.id} value={account.id}>
                      {account.name} ({account.type})
                    </option>
                  ))}
                </select>

                <select
                  className="form-select"
                  value={line.dr_cr}
                  onChange={(e) => updateLine(index, 'dr_cr', e.target.value as 'DR' | 'CR')}
                  style={{ flex: 1 }}
                >
                  <option value="DR">Debit</option>
                  <option value="CR">Credit</option>
                </select>

                <input
                  type="number"
                  step="0.01"
                  className="form-input"
                  value={line.amount}
                  onChange={(e) => updateLine(index, 'amount', Number(e.target.value))}
                  style={{ flex: 1 }}
                  required
                />

                {lines.length > 2 && (
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => removeLine(index)}
                    style={{ padding: 8 }}
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            ))}

            <div style={{ marginTop: 12, padding: 12, backgroundColor: isBalanced() ? '#d4edda' : '#f8d7da', borderRadius: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Total Debits: ${getTotalDebits().toFixed(2)}</span>
                <span>Total Credits: ${getTotalCredits().toFixed(2)}</span>
              </div>
              <div style={{ textAlign: 'center', marginTop: 4, fontWeight: 500 }}>
                {isBalanced() ? '✓ Balanced' : '⚠ Not Balanced'}
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <input
                type="checkbox"
                checked={postImmediately}
                onChange={(e) => setPostImmediately(e.target.checked)}
                style={{ marginRight: 8 }}
              />
              Post transaction immediately (affects account balances)
            </label>
            <small style={{ color: '#666', display: 'block', marginTop: 4 }}>
              Uncheck to create a draft transaction that can be posted later
            </small>
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={loading || !isBalanced()}
            >
              {loading ? 'Creating...' : 'Create Transaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TransactionModal;