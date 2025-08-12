import React, { useState } from 'react';
import { PageHeader } from '../components/Layout';
import { Card, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Input';
import { LoadingState, ErrorState } from '../components/ui/LoadingSpinner';
import { useApi, useApiMutation, useFormState } from '../hooks/useApi';
import { accountsApi } from '../api/services';
import type { Account, AccountCreateRequest } from '../api/types';

export function Accounts() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const { data: accounts, loading, error, refetch } = useApi(() => accountsApi.list());

  if (loading) {
    return (
      <div>
        <PageHeader title="Accounts" subtitle="Manage your investment accounts" />
        <LoadingState message="Loading accounts..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Accounts" subtitle="Manage your investment accounts" />
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader 
        title="Accounts" 
        subtitle="Manage your investment accounts"
        actions={
          <Button onClick={() => setShowCreateForm(true)}>
            Add Account
          </Button>
        }
      />

      {/* Create Account Form */}
      {showCreateForm && (
        <div className="mb-6">
          <CreateAccountForm 
            onSuccess={() => {
              setShowCreateForm(false);
              refetch();
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}

      {/* Accounts List */}
      <Card>
        <CardHeader>
          <CardTitle>Your Accounts</CardTitle>
        </CardHeader>
        
        {accounts && accounts.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🏦</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Accounts</h3>
            <p className="text-gray-600 mb-6">
              Create your first account to start tracking your investments.
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              Add Your First Account
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Currency
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {accounts?.map((account) => (
                  <AccountRow key={account.id} account={account} onUpdate={refetch} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

interface CreateAccountFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

function CreateAccountForm({ onSuccess, onCancel }: CreateAccountFormProps) {
  const { mutate, loading } = useApiMutation<Account, AccountCreateRequest>();
  const { formData, updateField, errors, setFieldError, hasErrors } = useFormState<AccountCreateRequest>({
    name: '',
    type: 'ASSET',
    currency: 'USD',
  });

  const accountTypes = [
    { value: 'ASSET', label: 'Asset (Brokerage, Cash, Retirement)' },
    { value: 'LIABILITY', label: 'Liability (Loans, Credit Cards)' },
    { value: 'EQUITY', label: 'Equity (Opening Balances)' },
    { value: 'INCOME', label: 'Income (Dividends, Interest)' },
    { value: 'EXPENSE', label: 'Expense (Fees, Taxes)' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Basic validation
    if (!formData.name.trim()) {
      setFieldError('name', 'Account name is required');
      return;
    }

    const result = await mutate(accountsApi.create, formData);
    if (result.success) {
      onSuccess();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create New Account</CardTitle>
      </CardHeader>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Account Name"
          value={formData.name}
          onChange={(e) => updateField('name', e.target.value)}
          error={errors.name}
          placeholder="e.g., Assets:Schwab Brokerage"
          required
        />
        
        <Select
          label="Account Type"
          value={formData.type}
          onChange={(e) => updateField('type', e.target.value as any)}
          options={accountTypes}
          error={errors.type}
        />
        
        <Input
          label="Currency"
          value={formData.currency}
          onChange={(e) => updateField('currency', e.target.value.toUpperCase())}
          error={errors.currency}
          placeholder="USD"
          maxLength={3}
          required
        />
        
        <div className="flex space-x-3 pt-4">
          <Button type="submit" loading={loading} disabled={hasErrors}>
            Create Account
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

interface AccountRowProps {
  account: Account;
  onUpdate: () => void;
}

function AccountRow({ account, onUpdate }: AccountRowProps) {
  const getAccountTypeDisplay = (type: string) => {
    const typeMap: Record<string, string> = {
      ASSET: 'Asset',
      LIABILITY: 'Liability', 
      EQUITY: 'Equity',
      INCOME: 'Income',
      EXPENSE: 'Expense',
    };
    return typeMap[type] || type;
  };

  const getAccountTypeColor = (type: string) => {
    const colorMap: Record<string, string> = {
      ASSET: 'bg-green-100 text-green-800',
      LIABILITY: 'bg-red-100 text-red-800',
      EQUITY: 'bg-blue-100 text-blue-800',
      INCOME: 'bg-purple-100 text-purple-800',
      EXPENSE: 'bg-yellow-100 text-yellow-800',
    };
    return colorMap[type] || 'bg-gray-100 text-gray-800';
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm font-medium text-gray-900">
          {account.name}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getAccountTypeColor(account.type)}`}>
          {getAccountTypeDisplay(account.type)}
        </span>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {account.currency}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-500">
          {account.created_at ? new Date(account.created_at).toLocaleDateString() : 'N/A'}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
        <Button variant="ghost" size="sm">
          Edit
        </Button>
      </td>
    </tr>
  );
}
