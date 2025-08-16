import axios from 'axios';
import type { 
  Account, 
  Transaction, 
  DashboardSummary, 
  TimeSeriesData, 
  AccountLedger 
} from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const accountsApi = {
  getAll: (params?: { type?: string; currency?: string }) => 
    api.get<Account[]>('/accounts/', { params }),
  
  getById: (id: number) => 
    api.get<Account>(`/accounts/${id}`),
  
  create: (account: Omit<Account, 'id'>) => 
    api.post<Account>('/accounts/', account),
  
  update: (id: number, account: Partial<Account>) => 
    api.put<Account>(`/accounts/${id}`, account),
  
  delete: (id: number) => 
    api.delete(`/accounts/${id}`),
};

export const transactionsApi = {
  getAll: (params?: {
    account_id?: number;
    type?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => api.get<Transaction[]>('/transactions/', { params }),
  
  getById: (id: number) => 
    api.get<Transaction>(`/transactions/${id}`),
  
  create: (transaction: Omit<Transaction, 'id'>) => 
    api.post<Transaction>('/transactions/', transaction),
  
  delete: (id: number) => 
    api.delete(`/transactions/${id}`),
  
  post: (id: number) => 
    api.post(`/transactions/${id}/post`),
  
  postAll: (ids: number[]) => 
    Promise.all(ids.map(id => api.post(`/transactions/${id}/post`))),
};

export const dashboardApi = {
  getSummary: (params?: {
    account_ids?: number[];
    as_of_date?: string;
  }) => api.get<DashboardSummary>('/dashboard/summary', { params }),
  
  getTimeSeries: (params: {
    account_ids?: number[];
    start_date: string;
    end_date: string;
    frequency?: 'daily' | 'weekly' | 'monthly';
  }) => api.get<TimeSeriesData>('/dashboard/timeseries', { params }),
  
  getAccountLedger: (accountId: number, params?: {
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => api.get<AccountLedger>(`/dashboard/accounts/${accountId}/ledger`, { params }),
};

export default api;