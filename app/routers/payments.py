# app/routers/payments.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth, schemas, models
from ..database import get_async_db
from ..services.payment_service import PaymentService
from ..crud import SubscriptionCRUD

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/initiate", response_model=schemas.PaymentInitiateResponse)
async def initiate_payment(
    request: schemas.PaymentInitiateRequest,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Initiate payment for a subscription plan"""
    result = await PaymentService.initiate_payment(
        current_user.id,
        request.plan,
        request.payment_method,
        db
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        "payment_link": result["payment_link"],
        "reference": result["reference"]
    }

@router.get("/verify/flutterwave/{transaction_id}")
async def verify_flutterwave_payment(
    transaction_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Verify Flutterwave payment"""
    result = await PaymentService.verify_flutterwave_payment(transaction_id, db)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        "message": "Payment verified successfully",
        "subscription_id": result["subscription_id"],
        "plan": result["plan"]
    }

@router.get("/subscriptions", response_model=list[schemas.SubscriptionResponse])
async def get_subscriptions(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's subscriptions"""
    # For simplicity, we'll return the active subscription
    subscription = await SubscriptionCRUD.get_active_subscription(db, current_user.id)
    
    if not subscription:
        return []
    
    return [subscription]