import React, { useState } from 'react';
import { PageHeader } from '../components/Layout';
import { Card, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Input';
import { LoadingState, ErrorState } from '../components/ui/LoadingSpinner';
import { useApi, useApiMutation, useFormState } from '../hooks/useApi';
import { instrumentsApi } from '../api/services';
import type { Instrument, InstrumentCreateRequest } from '../api/types';

export function Instruments() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const { data: instruments, loading, error, refetch } = useApi(() => instrumentsApi.list());

  if (loading) {
    return (
      <div>
        <PageHeader title="Instruments" subtitle="Manage tradable securities" />
        <LoadingState message="Loading instruments..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Instruments" subtitle="Manage tradable securities" />
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader 
        title="Instruments" 
        subtitle="Manage tradable securities"
        actions={
          <Button onClick={() => setShowCreateForm(true)}>
            Add Instrument
          </Button>
        }
      />

      {/* Create Instrument Form */}
      {showCreateForm && (
        <div className="mb-6">
          <CreateInstrumentForm 
            onSuccess={() => {
              setShowCreateForm(false);
              refetch();
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}

      {/* Instruments List */}
      <Card>
        <CardHeader>
          <CardTitle>Securities</CardTitle>
        </CardHeader>
        
        {instruments && instruments.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📈</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Instruments</h3>
            <p className="text-gray-600 mb-6">
              Add your first tradable security to start recording transactions.
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              Add Your First Instrument
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Symbol
                  </th>
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
                {instruments?.map((instrument) => (
                  <InstrumentRow key={instrument.id} instrument={instrument} onUpdate={refetch} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

interface CreateInstrumentFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

function CreateInstrumentForm({ onSuccess, onCancel }: CreateInstrumentFormProps) {
  const { mutate, loading } = useApiMutation<Instrument, InstrumentCreateRequest>();
  const { formData, updateField, errors, setFieldError, hasErrors } = useFormState<InstrumentCreateRequest>({
    symbol: '',
    name: '',
    type: 'EQUITY',
    currency: 'USD',
  });

  const instrumentTypes = [
    { value: 'EQUITY', label: 'Stock / Equity' },
    { value: 'ETF', label: 'ETF' },
    { value: 'MUTUAL_FUND', label: 'Mutual Fund' },
    { value: 'BOND', label: 'Bond' },
    { value: 'CRYPTO', label: 'Cryptocurrency' },
    { value: 'CASH', label: 'Cash Equivalent' },
    { value: 'OTHER', label: 'Other' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Basic validation
    if (!formData.symbol.trim()) {
      setFieldError('symbol', 'Symbol is required');
      return;
    }
    if (!formData.name.trim()) {
      setFieldError('name', 'Name is required');
      return;
    }

    const result = await mutate(instrumentsApi.create, {
      ...formData,
      symbol: formData.symbol.toUpperCase(),
    });
    if (result.success) {
      onSuccess();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add New Instrument</CardTitle>
      </CardHeader>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Symbol"
            value={formData.symbol}
            onChange={(e) => updateField('symbol', e.target.value.toUpperCase())}
            error={errors.symbol}
            placeholder="AAPL"
            required
          />
          
          <Select
            label="Type"
            value={formData.type}
            onChange={(e) => updateField('type', e.target.value as any)}
            options={instrumentTypes}
            error={errors.type}
          />
        </div>
        
        <Input
          label="Name"
          value={formData.name}
          onChange={(e) => updateField('name', e.target.value)}
          error={errors.name}
          placeholder="Apple Inc."
          required
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
            Add Instrument
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

interface InstrumentRowProps {
  instrument: Instrument;
  onUpdate: () => void;
}

function InstrumentRow({ instrument, onUpdate }: InstrumentRowProps) {
  const getInstrumentTypeDisplay = (type: string) => {
    const typeMap: Record<string, string> = {
      EQUITY: 'Stock',
      ETF: 'ETF',
      MUTUAL_FUND: 'Mutual Fund',
      BOND: 'Bond',
      CRYPTO: 'Crypto',
      CASH: 'Cash',
      OTHER: 'Other',
    };
    return typeMap[type] || type;
  };

  const getInstrumentTypeColor = (type: string) => {
    const colorMap: Record<string, string> = {
      EQUITY: 'bg-blue-100 text-blue-800',
      ETF: 'bg-green-100 text-green-800',
      MUTUAL_FUND: 'bg-purple-100 text-purple-800',
      BOND: 'bg-yellow-100 text-yellow-800',
      CRYPTO: 'bg-orange-100 text-orange-800',
      CASH: 'bg-gray-100 text-gray-800',
      OTHER: 'bg-gray-100 text-gray-800',
    };
    return colorMap[type] || 'bg-gray-100 text-gray-800';
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm font-bold text-gray-900">
          {instrument.symbol}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {instrument.name}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getInstrumentTypeColor(instrument.type)}`}>
          {getInstrumentTypeDisplay(instrument.type)}
        </span>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {instrument.currency}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-500">
          {instrument.created_at ? new Date(instrument.created_at).toLocaleDateString() : 'N/A'}
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
