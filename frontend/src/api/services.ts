// API service functions for different endpoint groups

import apiClient from './client';
import type {
  Account,
  AccountCreateRequest,
  Instrument,
  InstrumentCreateRequest,
  Transaction,
  TradeRequest,
  CorporateAction,
  CorporateActionCreateRequest,
  PortfolioPositions,
  PortfolioSummary,
  ProcessingResult,
} from './types';

// Accounts API
export const accountsApi = {
  list: () => apiClient.get<Account[]>('/api/accounts/'),
  
  get: (id: number) => apiClient.get<Account>(`/api/accounts/${id}`),
  
  create: (data: AccountCreateRequest) => 
    apiClient.post<Account>('/api/accounts/', data),
  
  update: (id: number, data: Partial<AccountCreateRequest>) =>
    apiClient.put<Account>(`/api/accounts/${id}`, data),
  
  delete: (id: number) =>
    apiClient.delete(`/api/accounts/${id}`),
};

// Instruments API
export const instrumentsApi = {
  list: (params?: {
    symbol?: string;
    type?: string;
    currency?: string;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }
    const queryString = searchParams.toString();
    return apiClient.get<Instrument[]>(
      `/api/instruments/${queryString ? `?${queryString}` : ''}`
    );
  },
  
  get: (id: number) => apiClient.get<Instrument>(`/api/instruments/${id}`),
  
  create: (data: InstrumentCreateRequest) =>
    apiClient.post<Instrument>('/api/instruments/', data),
  
  update: (id: number, data: Partial<InstrumentCreateRequest>) =>
    apiClient.put<Instrument>(`/api/instruments/${id}`, data),
  
  delete: (id: number) =>
    apiClient.delete(`/api/instruments/${id}`),
};

// Transactions API
export const transactionsApi = {
  list: (params?: {
    account_id?: number;
    instrument_id?: number;
    type?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }
    const queryString = searchParams.toString();
    return apiClient.get<Transaction[]>(
      `/api/transactions/${queryString ? `?${queryString}` : ''}`
    );
  },
  
  get: (id: number) => apiClient.get<Transaction>(`/api/transactions/${id}`),
  
  createTrade: (data: TradeRequest) =>
    apiClient.post<Transaction>('/api/transactions/trade', data),
  
  post: (id: number) =>
    apiClient.post(`/api/transactions/${id}/post`),
  
  unpost: (id: number) =>
    apiClient.post(`/api/transactions/${id}/unpost`),
};

// Corporate Actions API
export const corporateActionsApi = {
  list: (params?: {
    instrument_id?: number;
    type?: string;
    processed_only?: boolean;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }
    const queryString = searchParams.toString();
    return apiClient.get<CorporateAction[]>(
      `/api/corporate-actions/${queryString ? `?${queryString}` : ''}`
    );
  },
  
  get: (id: number) => apiClient.get<CorporateAction>(`/api/corporate-actions/${id}`),
  
  create: (data: CorporateActionCreateRequest) =>
    apiClient.post<CorporateAction>('/api/corporate-actions/', data),
  
  update: (id: number, data: Partial<CorporateActionCreateRequest>) =>
    apiClient.put<CorporateAction>(`/api/corporate-actions/${id}`, data),
  
  delete: (id: number) =>
    apiClient.delete(`/api/corporate-actions/${id}`),
  
  process: (id: number) =>
    apiClient.post<ProcessingResult>(`/api/corporate-actions/${id}/process`),
  
  processPending: (instrument_id?: number) => {
    const params = instrument_id ? `?instrument_id=${instrument_id}` : '';
    return apiClient.post<ProcessingResult[]>(`/api/corporate-actions/process-pending${params}`);
  },
  
  getSummaryReport: (params?: {
    instrument_id?: number;
    start_date?: string;
    end_date?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }
    const queryString = searchParams.toString();
    return apiClient.get<any>(
      `/api/corporate-actions/summary/report${queryString ? `?${queryString}` : ''}`
    );
  },
};

// Portfolio API
export const portfolioApi = {
  getPositions: (params?: {
    account_id?: number;
    instrument_id?: number;
    include_pnl?: boolean;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
    }
    const queryString = searchParams.toString();
    return apiClient.get<PortfolioPositions>(
      `/api/portfolio/positions${queryString ? `?${queryString}` : ''}`
    );
  },
  
  getSummary: (account_id?: number) => {
    const params = account_id ? `?account_id=${account_id}` : '';
    return apiClient.get<PortfolioSummary>(`/api/portfolio/summary${params}`);
  },
};

// System API
export const systemApi = {
  getHealth: () => apiClient.getHealth(),
  getStatus: () => apiClient.getApiStatus(),
};
