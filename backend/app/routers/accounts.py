"""
Accounts API endpoints for managing accounts (cash, brokerage, etc.).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.db import get_db
from app.models import Account
from app.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountResponse(BaseModel):
    """Response model for an account."""
    id: int
    name: str
    type: str
    currency: str
    created_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class AccountCreateRequest(BaseModel):
    """Request model for creating an account."""
    name: str
    type: str
    currency: str = "USD"


class AccountUpdateRequest(BaseModel):
    """Request model for updating an account."""
    name: Optional[str] = None
    type: Optional[str] = None
    currency: Optional[str] = None


@router.get("/", response_model=List[AccountResponse])
async def get_accounts(
    type: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get list of accounts with optional filtering.
    
    Args:
        type: Optional account type filter
        currency: Optional currency filter
        db: Database session
    """
    try:
        query = db.query(Account)
        
        # Apply filters
        if type:
            query = query.filter(Account.type == type)
        if currency:
            query = query.filter(Account.currency == currency)
        
        accounts = query.order_by(Account.name).all()
        return accounts
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve accounts: {str(e)}"
        )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific account by ID."""
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account with ID {account_id} not found"
            )
        
        return account
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve account: {str(e)}"
        )


@router.post("/", response_model=AccountResponse)
async def create_account(
    account_data: AccountCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new account."""
    try:
        # Check if account name already exists
        existing = db.query(Account).filter(Account.name == account_data.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Account with name '{account_data.name}' already exists"
            )
        
        # Validate account type
        valid_types = ["ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"]
        if account_data.type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid account type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Create account
        account = Account(
            name=account_data.name,
            type=account_data.type,
            currency=account_data.currency.upper()
        )
        
        db.add(account)
        db.commit()
        db.refresh(account)
        
        return account
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create account: {str(e)}"
        )


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    account_data: AccountUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update an existing account."""
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account with ID {account_id} not found"
            )
        
        # Update fields if provided
        if account_data.name is not None:
            # Check if new name conflicts with existing account
            existing = db.query(Account).filter(
                Account.name == account_data.name,
                Account.id != account_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Account with name '{account_data.name}' already exists"
                )
            account.name = account_data.name
        
        if account_data.type is not None:
            valid_types = ["ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"]
            if account_data.type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid account type. Must be one of: {', '.join(valid_types)}"
                )
            account.type = account_data.type
            
        if account_data.currency is not None:
            account.currency = account_data.currency.upper()
        
        db.commit()
        db.refresh(account)
        
        return account
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update account: {str(e)}"
        )


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """Delete an account (only if no related data exists)."""
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account with ID {account_id} not found"
            )
        
        # Check for related data (this would be handled by foreign key constraints)
        db.delete(account)
        db.commit()
        
        return {"ok": True, "message": "Account deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        if "FOREIGN KEY constraint failed" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Cannot delete account: it has associated transactions or other data"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete account: {str(e)}"
        )
