export interface Account {
  id: number;
  name: string;
  type: 'ASSET' | 'LIABILITY' | 'EQUITY' | 'INCOME' | 'EXPENSE';
  currency: string;
  balance?: number;
}

export interface Transaction {
  id: number;
  type: string;
  date: string;
  memo: string;
  status?: string;
  auto_post?: boolean;
  lines: TransactionLine[];
}

export interface TransactionLine {
  id: number;
  account_id: number;
  account_name?: string;
  dr_cr: 'DR' | 'CR';
  amount: number;
}

export interface DashboardSummary {
  net_worth: number;
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  total_income: number;
  total_expenses: number;
  account_balances: AccountBalance[];
}

export interface AccountBalance {
  account_id: number;
  account_name: string;
  account_type: string;
  currency: string;
  balance: number;
}

export interface TimeSeriesData {
  data_points: TimeSeriesPoint[];
  account_info: Record<string, AccountInfo>;
}

export interface TimeSeriesPoint {
  date: string;
  accounts: Record<string, number>;
  net_worth: number;
}

export interface AccountInfo {
  name: string;
  type: string;
}

export interface LedgerEntry {
  transaction_id: number;
  transaction_line_id: number;
  date: string;
  memo: string;
  transaction_type: string;
  side: 'DR' | 'CR';
  amount: number;
  running_balance: number;
}

export interface AccountLedger {
  account: Account & { current_balance: number };
  ledger_entries: LedgerEntry[];
  total_entries: number;
  has_more: boolean;
}