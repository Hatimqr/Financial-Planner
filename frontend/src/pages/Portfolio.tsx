import React from 'react';
import { PageHeader } from '../components/Layout';
import { Card, CardHeader, CardTitle } from '../components/ui/Card';
import { LoadingState, ErrorState } from '../components/ui/LoadingSpinner';
import { useApi } from '../hooks/useApi';
import { portfolioApi } from '../api/services';
import type { Position } from '../api/types';

export function Portfolio() {
  const { data: portfolioData, loading, error, refetch } = useApi(() => 
    portfolioApi.getPositions({ include_pnl: false }) // Start without P&L to avoid errors
  );

  if (loading) {
    return (
      <div>
        <PageHeader title="Portfolio" subtitle="Your investment positions and performance" />
        <LoadingState message="Loading portfolio..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Portfolio" subtitle="Your investment positions and performance" />
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  const summary = portfolioData?.summary;
  const positions = portfolioData?.positions || [];

  return (
    <div>
      <PageHeader 
        title="Portfolio" 
        subtitle="Your investment positions and performance"
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600">Total Cost Basis</p>
            <p className="text-2xl font-bold text-gray-900">
              ${summary?.total_cost_basis?.toLocaleString() || '0.00'}
            </p>
          </div>
        </Card>
        
        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600">Market Value</p>
            <p className="text-2xl font-bold text-gray-900">
              ${summary?.total_market_value?.toLocaleString() || '0.00'}
            </p>
          </div>
        </Card>
        
        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600">Unrealized P&L</p>
            <p className={`text-2xl font-bold ${
              (summary?.total_unrealized_pnl || 0) >= 0 ? 'text-success-600' : 'text-danger-600'
            }`}>
              ${summary?.total_unrealized_pnl?.toLocaleString() || '0.00'}
            </p>
          </div>
        </Card>
        
        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600">Positions</p>
            <p className="text-2xl font-bold text-gray-900">
              {summary?.position_count || 0}
            </p>
          </div>
        </Card>
      </div>

      {/* Positions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Current Positions</CardTitle>
        </CardHeader>
        
        {positions.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📊</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Positions</h3>
            <p className="text-gray-600 mb-6">
              You don't have any investment positions yet. Start by adding some accounts and making your first trades.
            </p>
            <div className="space-x-3">
              <a href="/accounts" className="btn-primary">
                Add Account
              </a>
              <a href="/transactions" className="btn-secondary">
                Record Trade
              </a>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Security
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Account
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Quantity
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Avg Cost
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Cost
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Lots
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {positions.map((position) => (
                  <PositionRow key={`${position.instrument_id}-${position.account_id}`} position={position} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

interface PositionRowProps {
  position: Position;
}

function PositionRow({ position }: PositionRowProps) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <div>
          <div className="text-sm font-medium text-gray-900">
            {position.instrument_symbol}
          </div>
          <div className="text-sm text-gray-500">
            {position.instrument_name}
          </div>
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">
          {position.account_name}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right">
        <div className="text-sm text-gray-900">
          {position.total_quantity.toLocaleString()}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right">
        <div className="text-sm text-gray-900">
          ${position.avg_cost_per_share.toFixed(2)}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right">
        <div className="text-sm text-gray-900">
          ${position.total_cost.toLocaleString()}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-center">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          {position.lot_count} lot{position.lot_count !== 1 ? 's' : ''}
        </span>
      </td>
    </tr>
  );
}
