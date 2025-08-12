// Type definitions for API data structures

export interface Account {
  id: number;
  name: string;
  type: 'ASSET' | 'LIABILITY' | 'EQUITY' | 'INCOME' | 'EXPENSE';
  currency: string;
  created_at?: string;
}

export interface AccountCreateRequest {
  name: string;
  type: 'ASSET' | 'LIABILITY' | 'EQUITY' | 'INCOME' | 'EXPENSE';
  currency: string;
}

export interface Instrument {
  id: number;
  symbol: string;
  name: string;
  type: 'EQUITY' | 'ETF' | 'MUTUAL_FUND' | 'BOND' | 'CRYPTO' | 'CASH' | 'OTHER';
  currency: string;
  created_at?: string;
}

export interface InstrumentCreateRequest {
  symbol: string;
  name: string;
  type: 'EQUITY' | 'ETF' | 'MUTUAL_FUND' | 'BOND' | 'CRYPTO' | 'CASH' | 'OTHER';
  currency: string;
}

export interface TransactionLine {
  id: number;
  account_id: number;
  account_name: string;
  instrument_id?: number;
  instrument_symbol?: string;
  dr_cr: 'DR' | 'CR';
  amount: number;
  quantity?: number;
}

export interface Transaction {
  id: number;
  type: 'TRADE' | 'TRANSFER' | 'DIVIDEND' | 'FEE' | 'TAX' | 'FX' | 'ADJUST';
  date: string;
  memo: string;
  reference?: string;
  status: string;
  created_at?: string;
  lines: TransactionLine[];
}

export interface TradeRequest {
  instrument_id: number;
  account_id: number;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  fees: number;
  date: string;
  reference?: string;
}

export interface CorporateAction {
  id: number;
  instrument_id: number;
  instrument_symbol: string;
  instrument_name: string;
  type: 'SPLIT' | 'CASH_DIVIDEND' | 'STOCK_DIVIDEND' | 'SYMBOL_CHANGE' | 'MERGER' | 'SPINOFF';
  date: string;
  ratio?: number;
  cash_per_share?: number;
  notes?: string;
  processed: boolean;
  created_at?: string;
}

export interface CorporateActionCreateRequest {
  instrument_id: number;
  type: 'SPLIT' | 'CASH_DIVIDEND' | 'STOCK_DIVIDEND' | 'SYMBOL_CHANGE' | 'MERGER' | 'SPINOFF';
  date: string;
  ratio?: number;
  cash_per_share?: number;
  notes?: string;
  auto_process: boolean;
}

export interface Position {
  instrument_id: number;
  instrument_symbol: string;
  instrument_name: string;
  account_id: number;
  account_name: string;
  total_quantity: number;
  total_cost: number;
  avg_cost_per_share: number;
  market_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  pnl_percentage?: number;
  lot_count: number;
}

export interface PortfolioSummary {
  total_cost_basis: number;
  total_market_value: number;
  total_unrealized_pnl: number;
  total_pnl_percentage: number;
  position_count: number;
  valuation_date?: string;
}

export interface PortfolioPositions {
  summary: PortfolioSummary;
  positions: Position[];
}

export interface ProcessingResult {
  action_id: number;
  type: string;
  success: boolean;
  message: string;
  details: Record<string, any>;
}
