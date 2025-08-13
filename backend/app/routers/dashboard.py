"""
Dashboard API endpoints for MVP frontend data aggregation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, field_validator

from app.db import get_db
from app.services.dashboard_service import DashboardService
from app.errors import NotFoundError, ValidationError, BusinessLogicError

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class AccountBalanceItem(BaseModel):
    """Response model for individual account balance."""
    account_id: int
    account_name: str
    account_type: str
    currency: str
    balance: float
    
    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryResponse(BaseModel):
    """Response model for dashboard summary data."""
    net_worth: float
    total_assets: float
    total_liabilities: float
    total_equity: float
    total_income: float
    total_expenses: float
    account_balances: List[AccountBalanceItem]
    
    model_config = ConfigDict(from_attributes=True)


class TimeSeriesDataPoint(BaseModel):
    """Response model for a single time-series data point."""
    date: str
    accounts: dict[str, float]
    net_worth: float
    
    model_config = ConfigDict(from_attributes=True)


class AccountInfo(BaseModel):
    """Response model for account information."""
    name: str
    type: str
    
    model_config = ConfigDict(from_attributes=True)


class TimeSeriesResponse(BaseModel):
    """Response model for time-series data."""
    data_points: List[TimeSeriesDataPoint]
    account_info: dict[str, AccountInfo]
    
    model_config = ConfigDict(from_attributes=True)


class LedgerEntry(BaseModel):
    """Response model for a ledger entry."""
    transaction_id: int
    transaction_line_id: int
    date: str
    memo: str
    transaction_type: str
    side: str
    amount: float
    running_balance: float
    
    model_config = ConfigDict(from_attributes=True)


class AccountLedgerAccount(BaseModel):
    """Response model for account information in ledger."""
    id: int
    name: str
    type: str
    currency: str
    current_balance: float
    
    model_config = ConfigDict(from_attributes=True)


class AccountLedgerResponse(BaseModel):
    """Response model for account ledger data."""
    account: AccountLedgerAccount
    ledger_entries: List[LedgerEntry]
    total_entries: int
    has_more: bool
    
    model_config = ConfigDict(from_attributes=True)


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    account_ids: Optional[List[int]] = Query(None, description="Account IDs to include"),
    as_of_date: Optional[str] = Query(None, description="Calculate as of date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get dashboard summary with net worth and account balances.
    
    This endpoint powers the main dashboard summary cards showing:
    - Net worth (Assets - Liabilities)
    - Total assets, liabilities, equity, income, expenses
    - Individual account balances
    
    Args:
        account_ids: Optional list of account IDs to include (default: all accounts)
        as_of_date: Optional date to calculate balances as of (default: today)
        db: Database session
    """
    try:
        dashboard_service = DashboardService(db)
        
        # Validate date format if provided
        if as_of_date:
            try:
                from datetime import datetime
                datetime.strptime(as_of_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        
        summary_data = dashboard_service.get_account_balances(
            account_ids=account_ids,
            as_of_date=as_of_date
        )
        
        # Convert to response format
        account_balances = [
            AccountBalanceItem(**balance) for balance in summary_data['account_balances']
        ]
        
        return DashboardSummaryResponse(
            net_worth=summary_data['net_worth'],
            total_assets=summary_data['total_assets'],
            total_liabilities=summary_data['total_liabilities'],
            total_equity=summary_data['total_equity'],
            total_income=summary_data['total_income'],
            total_expenses=summary_data['total_expenses'],
            account_balances=account_balances
        )
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve dashboard summary: {str(e)}"
        )


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_dashboard_timeseries(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    account_ids: Optional[List[int]] = Query(None, description="Account IDs to include"),
    frequency: str = Query("daily", description="Data frequency: daily, weekly, monthly"),
    db: Session = Depends(get_db)
):
    """
    Get time-series data for account balances over a date range.
    
    This endpoint powers the main dashboard chart showing account balances
    and net worth over time.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        account_ids: Optional list of account IDs to include (default: all accounts)
        frequency: Data frequency - 'daily', 'weekly', or 'monthly'
        db: Database session
    """
    try:
        # Validate frequency
        if frequency not in ['daily', 'weekly', 'monthly']:
            raise HTTPException(
                status_code=400,
                detail="Frequency must be 'daily', 'weekly', or 'monthly'"
            )
        
        dashboard_service = DashboardService(db)
        
        timeseries_data = dashboard_service.get_timeseries_data(
            start_date=start_date,
            end_date=end_date,
            account_ids=account_ids,
            frequency=frequency
        )
        
        # Convert to response format
        data_points = [
            TimeSeriesDataPoint(**point) for point in timeseries_data['data_points']
        ]
        
        account_info = {
            acc_id: AccountInfo(**info) 
            for acc_id, info in timeseries_data['account_info'].items()
        }
        
        return TimeSeriesResponse(
            data_points=data_points,
            account_info=account_info
        )
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve timeseries data: {str(e)}"
        )


@router.get("/accounts/{account_id}/ledger", response_model=AccountLedgerResponse)
async def get_account_ledger(
    account_id: int,
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(100, description="Maximum number of entries", ge=1, le=1000),
    offset: int = Query(0, description="Number of entries to skip", ge=0),
    db: Session = Depends(get_db)
):
    """
    Get ledger entries for a specific account in T-account format.
    
    This endpoint powers the T-account view showing debits and credits
    for a specific account with running balance calculations.
    
    Args:
        account_id: ID of the account
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        limit: Maximum number of entries to return
        offset: Number of entries to skip for pagination
        db: Database session
    """
    try:
        # Validate date formats if provided
        if start_date:
            try:
                from datetime import datetime
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                from datetime import datetime
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        dashboard_service = DashboardService(db)
        
        ledger_data = dashboard_service.get_account_ledger(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        # Convert to response format
        account_info = AccountLedgerAccount(**ledger_data['account'])
        ledger_entries = [
            LedgerEntry(**entry) for entry in ledger_data['ledger_entries']
        ]
        
        return AccountLedgerResponse(
            account=account_info,
            ledger_entries=ledger_entries,
            total_entries=ledger_data['total_entries'],
            has_more=ledger_data['has_more']
        )
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve account ledger: {str(e)}"
        )