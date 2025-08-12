import React, { useState } from 'react';
import { PageHeader } from '../components/Layout';
import { Card, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Input';
import { LoadingState, ErrorState } from '../components/ui/LoadingSpinner';
import { useApi, useApiMutation, useFormState } from '../hooks/useApi';
import { transactionsApi, accountsApi, instrumentsApi } from '../api/services';
import type { Transaction, TradeRequest, Account, Instrument } from '../api/types';

export function Transactions() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const { data: transactions, loading, error, refetch } = useApi(() => transactionsApi.list({ limit: 50 }));

  if (loading) {
    return (
      <div>
        <PageHeader title="Transactions" subtitle="Investment transaction history" />
        <LoadingState message="Loading transactions..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Transactions" subtitle="Investment transaction history" />
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader 
        title="Transactions" 
        subtitle="Investment transaction history"
        actions={
          <Button onClick={() => setShowCreateForm(true)}>
            Record Trade
          </Button>
        }
      />

      {/* Create Transaction Form */}
      {showCreateForm && (
        <div className="mb-6">
          <CreateTradeForm 
            onSuccess={() => {
              setShowCreateForm(false);
              refetch();
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}

      {/* Transactions List */}
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        
        {transactions && transactions.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">💳</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Transactions</h3>
            <p className="text-gray-600 mb-6">
              Record your first investment transaction to start tracking your portfolio.
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              Record Your First Trade
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Description
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Reference
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Lines
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {transactions?.map((transaction) => (
                  <TransactionRow key={transaction.id} transaction={transaction} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

interface CreateTradeFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

function CreateTradeForm({ onSuccess, onCancel }: CreateTradeFormProps) {
  const { mutate, loading } = useApiMutation<Transaction, TradeRequest>();
  const { data: accounts } = useApi(() => accountsApi.list());
  const { data: instruments } = useApi(() => instrumentsApi.list());
  
  const { formData, updateField, errors, setFieldError, hasErrors } = useFormState<TradeRequest>({
    instrument_id: 0,
    account_id: 0,
    side: 'BUY',
    quantity: 0,
    price: 0,
    fees: 0,
    date: new Date().toISOString().split('T')[0], // Today's date
    reference: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Basic validation
    if (!formData.instrument_id) {
      setFieldError('instrument_id', 'Please select an instrument');
      return;
    }
    if (!formData.account_id) {
      setFieldError('account_id', 'Please select an account');
      return;
    }
    if (formData.quantity <= 0) {
      setFieldError('quantity', 'Quantity must be greater than 0');
      return;
    }
    if (formData.price <= 0) {
      setFieldError('price', 'Price must be greater than 0');
      return;
    }

    const result = await mutate(transactionsApi.createTrade, formData);
    if (result.success) {
      onSuccess();
    }
  };

  const assetAccounts = accounts?.filter(account => account.type === 'ASSET') || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Record Trade</CardTitle>
      </CardHeader>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Select
            label="Instrument"
            value={formData.instrument_id.toString()}
            onChange={(e) => updateField('instrument_id', parseInt(e.target.value))}
            options={[
              { value: '0', label: 'Select an instrument...' },
              ...(instruments?.map(inst => ({
                value: inst.id.toString(),
                label: `${inst.symbol} - ${inst.name}`
              })) || [])
            ]}
            error={errors.instrument_id}
          />
          
          <Select
            label="Account"
            value={formData.account_id.toString()}
            onChange={(e) => updateField('account_id', parseInt(e.target.value))}
            options={[
              { value: '0', label: 'Select an account...' },
              ...assetAccounts.map(account => ({
                value: account.id.toString(),
                label: account.name
              }))
            ]}
            error={errors.account_id}
          />
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Select
            label="Side"
            value={formData.side}
            onChange={(e) => updateField('side', e.target.value as 'BUY' | 'SELL')}
            options={[
              { value: 'BUY', label: 'Buy' },
              { value: 'SELL', label: 'Sell' },
            ]}
            error={errors.side}
          />
          
          <Input
            label="Quantity"
            type="number"
            step="0.001"
            min="0"
            value={formData.quantity}
            onChange={(e) => updateField('quantity', parseFloat(e.target.value) || 0)}
            error={errors.quantity}
            placeholder="100"
            required
          />
          
          <Input
            label="Price per Share"
            type="number"
            step="0.01"
            min="0"
            value={formData.price}
            onChange={(e) => updateField('price', parseFloat(e.target.value) || 0)}
            error={errors.price}
            placeholder="150.00"
            required
          />
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Fees"
            type="number"
            step="0.01"
            min="0"
            value={formData.fees}
            onChange={(e) => updateField('fees', parseFloat(e.target.value) || 0)}
            error={errors.fees}
            placeholder="5.00"
          />
          
          <Input
            label="Trade Date"
            type="date"
            value={formData.date}
            onChange={(e) => updateField('date', e.target.value)}
            error={errors.date}
            required
          />
        </div>
        
        <Input
          label="Reference (Optional)"
          value={formData.reference}
          onChange={(e) => updateField('reference', e.target.value)}
          error={errors.reference}
          placeholder="Order #12345"
        />
        
        {/* Trade Summary */}
        {formData.quantity > 0 && formData.price > 0 && (
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Trade Summary</h4>
            <div className="text-sm text-gray-600">
              <p>Total Value: ${(formData.quantity * formData.price).toFixed(2)}</p>
              <p>Fees: ${formData.fees.toFixed(2)}</p>
              <p className="font-medium">
                Total Cost: ${(formData.quantity * formData.price + (formData.side === 'BUY' ? formData.fees : -formData.fees)).toFixed(2)}
              </p>
            </div>
          </div>
        )}
        
        <div className="flex space-x-3 pt-4">
          <Button type="submit" loading={loading} disabled={hasErrors}>
            Record Trade
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

interface TransactionRowProps {
  transaction: Transaction;
}

function TransactionRow({ transaction }: TransactionRowProps) {
  const getTransactionTypeColor = (type: string) => {
    const colorMap: Record<string, string> = {
      TRADE: 'bg-blue-100 text-blue-800',
      TRANSFER: 'bg-green-100 text-green-800',
      DIVIDEND: 'bg-purple-100 text-purple-800',
      FEE: 'bg-red-100 text-red-800',
      TAX: 'bg-yellow-100 text-yellow-800',
      FX: 'bg-orange-100 text-orange-800',
      ADJUST: 'bg-gray-100 text-gray-800',
    };
    return colorMap[type] || 'bg-gray-100 text-gray-800';
  };

  const getStatusColor = (status: string) => {
    return status === 'POSTED' 
      ? 'bg-green-100 text-green-800' 
      : 'bg-yellow-100 text-yellow-800';
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {new Date(transaction.date).toLocaleDateString()}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTransactionTypeColor(transaction.type)}`}>
          {transaction.type}
        </span>
      </td>
      <td className="px-6 py-4">
        <div className="text-sm text-gray-900 max-w-xs truncate">
          {transaction.memo}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-500">
          {transaction.reference || '-'}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(transaction.status)}`}>
          {transaction.status}
        </span>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-center">
        <div className="text-sm text-gray-900">
          {transaction.lines.length}
        </div>
      </td>
    </tr>
  );
}
