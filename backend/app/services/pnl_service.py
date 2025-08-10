"""P&L Calculation Engine for Epic 2-4.

This service implements comprehensive profit and loss calculations for the financial 
planning application, including:
- Realized P&L from completed lot sales
- Unrealized P&L from current positions (mark-to-market)
- Performance attribution by instrument, account, time period
- Total return calculations using Time-Weighted Return (TWR) methodology
- P&L reconciliation and validation
"""

from typing import List, Optional, Dict, Any, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.models import Account, Instrument, Price, Transaction, TransactionLine, Lot
from app.services.base_service import BaseService
from app.services.lot_service import LotService
from app.errors import ValidationError, NotFoundError, BusinessLogicError
from app.logging import get_logger


class PnLService(BaseService):
    """Service for comprehensive P&L calculations and performance analytics."""
    
    def __init__(self, db: Session):
        """
        Initialize P&L service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        super().__init__(db)
        self.lot_service = LotService(db)
        
    def get_entity_name(self) -> str:
        """Return the name of the primary entity this service manages."""
        return "pnl_calculation"
    
    def calculate_realized_pnl(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate realized P&L from completed lot sales.
        
        Args:
            account_id: Optional account filter
            instrument_id: Optional instrument filter
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            
        Returns:
            Dictionary with realized P&L details:
            {
                'total_realized_pnl': Decimal,
                'total_proceeds': Decimal,
                'total_cost_basis': Decimal,
                'trades_count': int,
                'positions': [
                    {
                        'instrument_id': int,
                        'instrument_symbol': str,
                        'account_id': int,
                        'account_name': str,
                        'realized_pnl': Decimal,
                        'proceeds': Decimal,
                        'cost_basis': Decimal,
                        'trades': [...]
                    }
                ]
            }
        """
        self.log_operation("calculate_realized_pnl", 
                          account_id=account_id, 
                          instrument_id=instrument_id,
                          start_date=start_date,
                          end_date=end_date)
        
        try:
            # Build query for sell transactions
            query = self.db.query(TransactionLine).join(Transaction).join(Account).join(Instrument)
            
            # Filter for sell transactions (negative quantity)
            query = query.filter(TransactionLine.quantity < 0)
            
            # Apply filters
            if account_id:
                query = query.filter(TransactionLine.account_id == account_id)
            if instrument_id:
                query = query.filter(TransactionLine.instrument_id == instrument_id)
            if start_date:
                query = query.filter(Transaction.date >= start_date)
            if end_date:
                query = query.filter(Transaction.date <= end_date)
            
            # Get all sell transactions
            sell_transactions = query.all()
            
            positions_pnl = {}
            total_realized_pnl = Decimal('0')
            total_proceeds = Decimal('0')
            total_cost_basis = Decimal('0')
            trades_count = 0
            
            for tx_line in sell_transactions:
                key = (tx_line.instrument_id, tx_line.account_id)
                
                if key not in positions_pnl:
                    positions_pnl[key] = {
                        'instrument_id': tx_line.instrument_id,
                        'instrument_symbol': tx_line.instrument.symbol,
                        'instrument_name': tx_line.instrument.name,
                        'account_id': tx_line.account_id,
                        'account_name': tx_line.account.name,
                        'realized_pnl': Decimal('0'),
                        'proceeds': Decimal('0'),
                        'cost_basis': Decimal('0'),
                        'trades': []
                    }
                
                # Calculate sale proceeds (amount is positive for sale proceeds)
                sale_proceeds = Decimal(str(abs(tx_line.amount)))
                quantity_sold = abs(Decimal(str(tx_line.quantity)))
                
                # Get lot closures for this sale to calculate cost basis
                try:
                    # Close lots FIFO to get cost basis (simulation - don't actually close)
                    available_lots = self.lot_service.get_available_lots(
                        tx_line.instrument_id, 
                        tx_line.account_id
                    )
                    
                    # Calculate cost basis using FIFO
                    cost_basis = self._calculate_fifo_cost_basis(available_lots, quantity_sold)
                    
                except Exception as e:
                    self.logger.warning(f"Could not calculate cost basis for transaction {tx_line.id}: {e}")
                    # Use average cost as fallback
                    cost_basis_info = self.lot_service.calculate_cost_basis(
                        tx_line.instrument_id, 
                        tx_line.account_id
                    )
                    avg_cost = cost_basis_info.get('average_cost_per_share', Decimal('0'))
                    cost_basis = avg_cost * quantity_sold
                
                # Calculate realized P&L
                trade_pnl = sale_proceeds - cost_basis
                
                # Add to position totals
                positions_pnl[key]['realized_pnl'] += trade_pnl
                positions_pnl[key]['proceeds'] += sale_proceeds
                positions_pnl[key]['cost_basis'] += cost_basis
                
                # Add trade details
                positions_pnl[key]['trades'].append({
                    'transaction_id': tx_line.transaction_id,
                    'date': tx_line.transaction.date,
                    'quantity_sold': quantity_sold,
                    'sale_proceeds': sale_proceeds,
                    'cost_basis': cost_basis,
                    'realized_pnl': trade_pnl,
                    'memo': tx_line.transaction.memo
                })
                
                # Add to grand totals
                total_realized_pnl += trade_pnl
                total_proceeds += sale_proceeds
                total_cost_basis += cost_basis
                trades_count += 1
            
            return {
                'total_realized_pnl': total_realized_pnl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'total_proceeds': total_proceeds.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'total_cost_basis': total_cost_basis.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'trades_count': trades_count,
                'positions': list(positions_pnl.values()),
                'calculation_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating realized P&L: {str(e)}")
            raise BusinessLogicError(
                message=f"Failed to calculate realized P&L: {str(e)}",
                details={"error_type": "calculation_error"}
            )
    
    def calculate_unrealized_pnl(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        valuation_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate unrealized P&L from current positions using mark-to-market.
        
        Args:
            account_id: Optional account filter
            instrument_id: Optional instrument filter
            valuation_date: Optional valuation date (defaults to latest available prices)
            
        Returns:
            Dictionary with unrealized P&L details:
            {
                'total_unrealized_pnl': Decimal,
                'total_market_value': Decimal,
                'total_cost_basis': Decimal,
                'positions': [
                    {
                        'instrument_id': int,
                        'instrument_symbol': str,
                        'account_id': int,
                        'account_name': str,
                        'quantity': Decimal,
                        'cost_basis': Decimal,
                        'market_price': Decimal,
                        'market_value': Decimal,
                        'unrealized_pnl': Decimal,
                        'pnl_percentage': Decimal
                    }
                ]
            }
        """
        self.log_operation("calculate_unrealized_pnl",
                          account_id=account_id,
                          instrument_id=instrument_id,
                          valuation_date=valuation_date)
        
        try:
            # Get current positions
            positions = self.lot_service.get_current_positions(account_id, instrument_id)
            
            if not positions:
                return {
                    'total_unrealized_pnl': Decimal('0'),
                    'total_market_value': Decimal('0'),
                    'total_cost_basis': Decimal('0'),
                    'positions': [],
                    'valuation_date': valuation_date or datetime.now().date().isoformat()
                }
            
            positions_pnl = []
            total_unrealized_pnl = Decimal('0')
            total_market_value = Decimal('0')
            total_cost_basis = Decimal('0')
            
            for position in positions:
                # Get market price
                market_price = self._get_market_price(
                    position['instrument_id'], 
                    valuation_date
                )
                
                if market_price is None:
                    self.logger.warning(f"No price found for instrument {position['instrument_id']}")
                    continue
                
                quantity = Decimal(str(position['total_quantity']))
                cost_basis = Decimal(str(position['total_cost']))
                market_value = quantity * market_price
                unrealized_pnl = market_value - cost_basis
                
                pnl_percentage = (
                    (unrealized_pnl / cost_basis * Decimal('100')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    ) if cost_basis > 0 else Decimal('0')
                )
                
                position_pnl = {
                    'instrument_id': position['instrument_id'],
                    'instrument_symbol': position['instrument_symbol'],
                    'instrument_name': position['instrument_name'],
                    'account_id': position['account_id'],
                    'account_name': position['account_name'],
                    'quantity': quantity,
                    'cost_basis': cost_basis.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'average_cost_per_share': (cost_basis / quantity).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    ) if quantity > 0 else Decimal('0'),
                    'market_price': market_price,
                    'market_value': market_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'unrealized_pnl': unrealized_pnl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'pnl_percentage': pnl_percentage,
                    'lot_count': position['lot_count']
                }
                
                positions_pnl.append(position_pnl)
                
                total_unrealized_pnl += unrealized_pnl
                total_market_value += market_value
                total_cost_basis += cost_basis
            
            return {
                'total_unrealized_pnl': total_unrealized_pnl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'total_market_value': total_market_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'total_cost_basis': total_cost_basis.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'total_pnl_percentage': (
                    (total_unrealized_pnl / total_cost_basis * Decimal('100')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    ) if total_cost_basis > 0 else Decimal('0')
                ),
                'positions': positions_pnl,
                'valuation_date': valuation_date or self._get_latest_price_date(),
                'calculation_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating unrealized P&L: {str(e)}")
            raise BusinessLogicError(
                message=f"Failed to calculate unrealized P&L: {str(e)}",
                details={"error_type": "calculation_error"}
            )
    
    def calculate_total_return(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        method: str = "time_weighted"
    ) -> Dict[str, Any]:
        """
        Calculate total return using Time-Weighted Return (TWR) methodology.
        
        Args:
            account_id: Optional account filter
            instrument_id: Optional instrument filter
            start_date: Start date for calculation period
            end_date: End date for calculation period
            method: Calculation method ("time_weighted" or "money_weighted")
            
        Returns:
            Dictionary with total return metrics:
            {
                'total_return': Decimal,
                'annualized_return': Decimal,
                'total_return_percentage': Decimal,
                'periods': [
                    {
                        'start_date': str,
                        'end_date': str,
                        'beginning_value': Decimal,
                        'ending_value': Decimal,
                        'cash_flows': Decimal,
                        'period_return': Decimal
                    }
                ]
            }
        """
        self.log_operation("calculate_total_return",
                          account_id=account_id,
                          instrument_id=instrument_id,
                          start_date=start_date,
                          end_date=end_date,
                          method=method)
        
        if method != "time_weighted":
            raise ValidationError("Only time_weighted method is currently supported")
        
        try:
            # Set default dates if not provided
            if not end_date:
                end_date = datetime.now().date().isoformat()
            if not start_date:
                # Default to 1 year ago
                start_date = (datetime.now().date() - timedelta(days=365)).isoformat()
            
            # Get cash flows (transactions) during the period
            cash_flows = self._get_cash_flows(account_id, instrument_id, start_date, end_date)
            
            # Get beginning and ending portfolio values
            beginning_value = self._get_portfolio_value(account_id, instrument_id, start_date)
            ending_value = self._get_portfolio_value(account_id, instrument_id, end_date)
            
            # Calculate time-weighted return
            if method == "time_weighted":
                return self._calculate_time_weighted_return(
                    beginning_value, ending_value, cash_flows, start_date, end_date
                )
            
        except Exception as e:
            self.logger.error(f"Error calculating total return: {str(e)}")
            raise BusinessLogicError(
                message=f"Failed to calculate total return: {str(e)}",
                details={"error_type": "calculation_error"}
            )
    
    def generate_pnl_report(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_positions: bool = True,
        include_transactions: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive P&L report.
        
        Args:
            account_id: Optional account filter
            instrument_id: Optional instrument filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            include_positions: Whether to include current positions
            include_transactions: Whether to include transaction details
            
        Returns:
            Comprehensive P&L report dictionary
        """
        self.log_operation("generate_pnl_report",
                          account_id=account_id,
                          instrument_id=instrument_id,
                          start_date=start_date,
                          end_date=end_date)
        
        try:
            # Calculate components
            realized_pnl = self.calculate_realized_pnl(
                account_id, instrument_id, start_date, end_date
            )
            
            unrealized_pnl = self.calculate_unrealized_pnl(
                account_id, instrument_id, end_date
            ) if include_positions else None
            
            total_return = self.calculate_total_return(
                account_id, instrument_id, start_date, end_date
            )
            
            # Calculate summary metrics
            total_pnl = realized_pnl['total_realized_pnl']
            if unrealized_pnl:
                total_pnl += unrealized_pnl['total_unrealized_pnl']
            
            report = {
                'report_metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'account_id': account_id,
                    'instrument_id': instrument_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'report_period_days': self._calculate_days_between(start_date, end_date) if start_date and end_date else None
                },
                'summary': {
                    'total_pnl': total_pnl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'realized_pnl': realized_pnl['total_realized_pnl'],
                    'unrealized_pnl': unrealized_pnl['total_unrealized_pnl'] if unrealized_pnl else Decimal('0'),
                    'total_return_percentage': total_return.get('total_return_percentage', Decimal('0')),
                    'annualized_return': total_return.get('annualized_return', Decimal('0'))
                },
                'realized_pnl_detail': realized_pnl,
                'performance_metrics': total_return
            }
            
            if include_positions and unrealized_pnl:
                report['unrealized_pnl_detail'] = unrealized_pnl
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating P&L report: {str(e)}")
            raise BusinessLogicError(
                message=f"Failed to generate P&L report: {str(e)}",
                details={"error_type": "report_generation_error"}
            )
    
    def reconcile_pnl(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        tolerance: Decimal = Decimal('0.01')
    ) -> Dict[str, Any]:
        """
        Reconcile P&L calculations against transaction history.
        
        Args:
            account_id: Optional account filter
            instrument_id: Optional instrument filter
            tolerance: Acceptable difference tolerance for reconciliation
            
        Returns:
            Dictionary with reconciliation results:
            {
                'is_reconciled': bool,
                'discrepancies': List[Dict],
                'summary': Dict
            }
        """
        self.log_operation("reconcile_pnl", 
                          account_id=account_id,
                          instrument_id=instrument_id)
        
        try:
            # Reconcile lots with transactions first
            lot_reconciliation = self.lot_service.reconcile_lots_with_transactions(
                account_id, instrument_id
            )
            
            # Get P&L calculations
            realized_pnl = self.calculate_realized_pnl(account_id, instrument_id)
            
            # Get transaction totals
            transaction_totals = self._get_transaction_totals(account_id, instrument_id)
            
            discrepancies = []
            
            # Check lot reconciliation
            if not lot_reconciliation['is_reconciled']:
                discrepancies.extend([
                    {
                        'type': 'lot_reconciliation',
                        'description': 'Lot positions do not match transaction history',
                        'details': lot_reconciliation['discrepancies']
                    }
                ])
            
            # Check P&L calculation consistency
            expected_cash_impact = (
                transaction_totals.get('total_sales', Decimal('0')) -
                transaction_totals.get('total_purchases', Decimal('0'))
            )
            calculated_cash_impact = (
                realized_pnl['total_proceeds'] - realized_pnl['total_cost_basis']
            )
            
            cash_difference = abs(expected_cash_impact - calculated_cash_impact)
            if cash_difference > tolerance:
                discrepancies.append({
                    'type': 'cash_flow_mismatch',
                    'description': 'Calculated P&L does not match transaction cash flows',
                    'expected_cash_impact': expected_cash_impact,
                    'calculated_cash_impact': calculated_cash_impact,
                    'difference': expected_cash_impact - calculated_cash_impact
                })
            
            return {
                'is_reconciled': len(discrepancies) == 0,
                'discrepancies': discrepancies,
                'lot_reconciliation': lot_reconciliation,
                'summary': {
                    'total_discrepancies': len(discrepancies),
                    'tolerance_used': tolerance,
                    'reconciliation_date': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error reconciling P&L: {str(e)}")
            raise BusinessLogicError(
                message=f"Failed to reconcile P&L: {str(e)}",
                details={"error_type": "reconciliation_error"}
            )
    
    # Private helper methods
    
    def _calculate_fifo_cost_basis(self, available_lots: List[Dict], quantity_to_sell: Decimal) -> Decimal:
        """Calculate cost basis using FIFO methodology."""
        cost_basis = Decimal('0')
        remaining_to_sell = quantity_to_sell
        
        # Sort by open_date to ensure FIFO
        sorted_lots = sorted(available_lots, key=lambda x: x['open_date'])
        
        for lot in sorted_lots:
            if remaining_to_sell <= 0:
                break
                
            available_in_lot = lot['remaining_quantity']
            to_sell_from_lot = min(remaining_to_sell, available_in_lot)
            
            lot_cost_basis = lot['cost_per_share'] * to_sell_from_lot
            cost_basis += lot_cost_basis
            remaining_to_sell -= to_sell_from_lot
        
        return cost_basis.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def _get_market_price(self, instrument_id: int, valuation_date: Optional[str] = None) -> Optional[Decimal]:
        """Get market price for an instrument on a specific date."""
        query = self.db.query(Price).filter(Price.instrument_id == instrument_id)
        
        if valuation_date:
            query = query.filter(Price.date <= valuation_date)
        
        # Get the most recent price
        price_record = query.order_by(desc(Price.date)).first()
        
        if price_record:
            return Decimal(str(price_record.close))
        return None
    
    def _get_latest_price_date(self) -> str:
        """Get the latest price date available in the system."""
        latest_price = self.db.query(Price).order_by(desc(Price.date)).first()
        if latest_price:
            return latest_price.date
        return datetime.now().date().isoformat()
    
    def _get_cash_flows(
        self,
        account_id: Optional[int],
        instrument_id: Optional[int],
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get cash flows (net transactions) during a period."""
        query = self.db.query(TransactionLine).join(Transaction)
        
        # Apply filters
        if account_id:
            query = query.filter(TransactionLine.account_id == account_id)
        if instrument_id:
            query = query.filter(TransactionLine.instrument_id == instrument_id)
        
        query = query.filter(Transaction.date >= start_date)
        query = query.filter(Transaction.date <= end_date)
        
        # Only include trade transactions
        query = query.filter(Transaction.type == 'TRADE')
        
        transactions = query.all()
        
        cash_flows = []
        for tx in transactions:
            cash_flows.append({
                'date': tx.transaction.date,
                'amount': Decimal(str(tx.amount)),
                'quantity': Decimal(str(tx.quantity)) if tx.quantity else Decimal('0'),
                'transaction_type': tx.transaction.type
            })
        
        return cash_flows
    
    def _get_portfolio_value(
        self,
        account_id: Optional[int],
        instrument_id: Optional[int],
        valuation_date: str
    ) -> Decimal:
        """Get portfolio value on a specific date."""
        # This is a simplified implementation
        # In practice, you'd need to calculate positions as of the valuation date
        # and apply prices from that date
        
        unrealized_pnl = self.calculate_unrealized_pnl(account_id, instrument_id, valuation_date)
        return unrealized_pnl['total_market_value']
    
    def _calculate_time_weighted_return(
        self,
        beginning_value: Decimal,
        ending_value: Decimal,
        cash_flows: List[Dict],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """Calculate time-weighted return."""
        # Simplified TWR calculation
        # For a more accurate TWR, you'd need to break into sub-periods around each cash flow
        
        # Calculate net cash flows
        net_cash_flows = sum(cf['amount'] for cf in cash_flows)
        
        # Adjust ending value for net contributions/withdrawals
        adjusted_ending_value = ending_value - net_cash_flows
        
        # Calculate return
        if beginning_value > 0:
            total_return = (adjusted_ending_value - beginning_value) / beginning_value
        else:
            total_return = Decimal('0')
        
        # Calculate annualized return
        days = self._calculate_days_between(start_date, end_date)
        if days > 0:
            years = Decimal(str(days)) / Decimal('365')
            if years > 0 and total_return > -1:
                annualized_return = ((1 + total_return) ** (1 / years)) - 1
            else:
                annualized_return = Decimal('0')
        else:
            annualized_return = Decimal('0')
        
        return {
            'total_return': total_return.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
            'total_return_percentage': (total_return * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'annualized_return': annualized_return.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
            'annualized_return_percentage': (annualized_return * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'beginning_value': beginning_value,
            'ending_value': ending_value,
            'net_cash_flows': net_cash_flows,
            'period_days': days
        }
    
    def _get_transaction_totals(
        self,
        account_id: Optional[int],
        instrument_id: Optional[int]
    ) -> Dict[str, Decimal]:
        """Get transaction totals for reconciliation."""
        query = self.db.query(TransactionLine).join(Transaction)
        
        # Apply filters
        if account_id:
            query = query.filter(TransactionLine.account_id == account_id)
        if instrument_id:
            query = query.filter(TransactionLine.instrument_id == instrument_id)
        
        # Only include trade transactions
        query = query.filter(Transaction.type == 'TRADE')
        
        transactions = query.all()
        
        total_sales = Decimal('0')
        total_purchases = Decimal('0')
        
        for tx in transactions:
            amount = Decimal(str(abs(tx.amount)))
            
            if tx.quantity and Decimal(str(tx.quantity)) < 0:
                # Sale transaction
                total_sales += amount
            else:
                # Purchase transaction
                total_purchases += amount
        
        return {
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'net_cash_flow': total_sales - total_purchases
        }
    
    def _calculate_days_between(self, start_date: Optional[str], end_date: Optional[str]) -> int:
        """Calculate days between two dates."""
        if not start_date or not end_date:
            return 0
        
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
            return (end - start).days
        except ValueError:
            return 0
    
    # Multi-currency support methods
    
    def calculate_multi_currency_pnl(
        self,
        account_id: Optional[int] = None,
        base_currency: str = "USD",
        fx_rates: Optional[Dict[str, Decimal]] = None
    ) -> Dict[str, Any]:
        """
        Calculate P&L with multi-currency support.
        
        Args:
            account_id: Optional account filter
            base_currency: Base currency for reporting
            fx_rates: Optional FX rates dict {currency: rate_to_base}
            
        Returns:
            P&L calculations in base currency
        """
        self.validate_currency_code(base_currency)
        
        # Get positions by currency
        positions = self.lot_service.get_current_positions(account_id)
        currency_groups = {}
        
        for position in positions:
            # Get instrument currency from the instrument
            instrument = self.db.query(Instrument).filter(
                Instrument.id == position['instrument_id']
            ).first()
            
            if not instrument:
                continue
                
            currency = instrument.currency
            if currency not in currency_groups:
                currency_groups[currency] = []
            currency_groups[currency].append(position)
        
        # Calculate P&L for each currency and convert to base
        total_pnl_base = Decimal('0')
        currency_breakdown = {}
        
        for currency, currency_positions in currency_groups.items():
            # Calculate P&L in local currency
            local_pnl = self._calculate_pnl_for_positions(currency_positions)
            
            # Convert to base currency
            if currency == base_currency:
                fx_rate = Decimal('1')
            elif fx_rates and currency in fx_rates:
                fx_rate = fx_rates[currency]
            else:
                # Get FX rate from database or external source
                fx_rate = self._get_fx_rate(currency, base_currency)
            
            pnl_base = local_pnl * fx_rate
            total_pnl_base += pnl_base
            
            currency_breakdown[currency] = {
                'local_pnl': local_pnl,
                'fx_rate': fx_rate,
                'pnl_in_base': pnl_base,
                'position_count': len(currency_positions)
            }
        
        return {
            'total_pnl_base_currency': total_pnl_base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'base_currency': base_currency,
            'currency_breakdown': currency_breakdown,
            'calculation_date': datetime.now().isoformat()
        }
    
    def _calculate_pnl_for_positions(self, positions: List[Dict]) -> Decimal:
        """Calculate total P&L for a list of positions."""
        total_pnl = Decimal('0')
        
        for position in positions:
            # This would need to be implemented based on position structure
            # For now, return zero as placeholder
            pass
        
        return total_pnl
    
    def _get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Get FX rate between currencies."""
        # Placeholder implementation
        # In practice, this would query an FX rates table or external service
        if from_currency == to_currency:
            return Decimal('1')
        
        # Return default rate for now
        return Decimal('1')