import React from 'react';
import { PageHeader } from '../components/Layout';
import { Card, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { LoadingState, ErrorState } from '../components/ui/LoadingSpinner';
import { useApi } from '../hooks/useApi';
import { corporateActionsApi } from '../api/services';
import type { CorporateAction } from '../api/types';

export function CorporateActions() {
  const { data: actions, loading, error, refetch } = useApi(() => corporateActionsApi.list());

  if (loading) {
    return (
      <div>
        <PageHeader title="Corporate Actions" subtitle="Stock splits, dividends, and symbol changes" />
        <LoadingState message="Loading corporate actions..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Corporate Actions" subtitle="Stock splits, dividends, and symbol changes" />
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader 
        title="Corporate Actions" 
        subtitle="Stock splits, dividends, and symbol changes"
        actions={
          <Button disabled>
            Add Action
          </Button>
        }
      />

      {/* Corporate Actions List */}
      <Card>
        <CardHeader>
          <CardTitle>Action History</CardTitle>
        </CardHeader>
        
        {actions && actions.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🏢</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Corporate Actions</h3>
            <p className="text-gray-600 mb-6">
              When companies announce stock splits, dividends, or other corporate actions, they'll appear here.
            </p>
            <div className="text-sm text-gray-500">
              <p>Corporate actions are typically processed automatically when announced.</p>
            </div>
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
                    Instrument
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Details
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Notes
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {actions?.map((action) => (
                  <CorporateActionRow key={action.id} action={action} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

interface CorporateActionRowProps {
  action: CorporateAction;
}

function CorporateActionRow({ action }: CorporateActionRowProps) {
  const getActionTypeColor = (type: string) => {
    const colorMap: Record<string, string> = {
      SPLIT: 'bg-blue-100 text-blue-800',
      CASH_DIVIDEND: 'bg-green-100 text-green-800',
      STOCK_DIVIDEND: 'bg-purple-100 text-purple-800',
      SYMBOL_CHANGE: 'bg-orange-100 text-orange-800',
      MERGER: 'bg-red-100 text-red-800',
      SPINOFF: 'bg-yellow-100 text-yellow-800',
    };
    return colorMap[type] || 'bg-gray-100 text-gray-800';
  };

  const getActionDetails = (action: CorporateAction) => {
    switch (action.type) {
      case 'SPLIT':
        return `${action.ratio}:1 split`;
      case 'CASH_DIVIDEND':
        return `$${action.cash_per_share?.toFixed(2)}/share`;
      case 'STOCK_DIVIDEND':
        return `${(action.ratio! * 100).toFixed(1)}% stock dividend`;
      case 'SYMBOL_CHANGE':
        return 'Symbol change';
      case 'MERGER':
        return 'Merger';
      case 'SPINOFF':
        return 'Spinoff';
      default:
        return '-';
    }
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {new Date(action.date).toLocaleDateString()}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div>
          <div className="text-sm font-medium text-gray-900">
            {action.instrument_symbol}
          </div>
          <div className="text-sm text-gray-500 max-w-xs truncate">
            {action.instrument_name}
          </div>
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getActionTypeColor(action.type)}`}>
          {action.type.replace('_', ' ')}
        </span>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {getActionDetails(action)}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
          action.processed 
            ? 'bg-green-100 text-green-800' 
            : 'bg-yellow-100 text-yellow-800'
        }`}>
          {action.processed ? 'Processed' : 'Pending'}
        </span>
      </td>
      <td className="px-6 py-4">
        <div className="text-sm text-gray-500 max-w-xs truncate">
          {action.notes || '-'}
        </div>
      </td>
    </tr>
  );
}
