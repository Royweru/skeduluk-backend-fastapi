# app/services/payment_service.py
import uuid
import httpx
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .. import crud, models, schemas

class PaymentService:
    @staticmethod
    async def initiate_payment(
        user_id: int,
        plan: str,
        payment_method: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Initiate payment for a subscription plan"""
        # Plan pricing
        plan_prices = {
            "basic": {"amount": 9.99, "currency": "USD"},
            "pro": {"amount": 19.99, "currency": "USD"},
            "enterprise": {"amount": 49.99, "currency": "USD"}
        }
        
        if plan.lower() not in plan_prices:
            return {"success": False, "error": "Invalid plan"}
        
        price_info = plan_prices[plan.lower()]
        
        if payment_method.lower() == "flutterwave":
            return await PaymentService._initiate_flutterwave_payment(
                user_id, plan, price_info
            )
        elif payment_method.lower() == "paypal":
            return await PaymentService._initiate_paypal_payment(
                user_id, plan, price_info
            )
        else:
            return {"success": False, "error": "Unsupported payment method"}
    
    @staticmethod
    async def _initiate_flutterwave_payment(
        user_id: int,
        plan: str,
        price_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Initiate payment with Flutterwave"""
        # Get user details
        # In a real implementation, you'd fetch this from the database
        
        # Generate transaction reference
        tx_ref = f"sub-{user_id}-{plan}-{uuid.uuid4()}"
        
        # Prepare payment data
        payment_data = {
            "tx_ref": tx_ref,
            "amount": price_info["amount"],
            "currency": price_info["currency"],
            "redirect_url": f"{settings.ALLOWED_HOSTS[0]}/payment/verify/flutterwave",
            "payment_options": "card, mpesa",
            "customer": {
                "email": f"user{user_id}@example.com",  # Replace with actual email
                "name": f"User {user_id}"  # Replace with actual name
            },
            "customizations": {
                "title": f"{plan.capitalize()} Subscription",
                "description": f"Monthly {plan.capitalize()} subscription"
            }
        }
        
        # Initialize payment with Flutterwave
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.flutterwave.com/v3/payments",
                headers=headers,
                json=payment_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result["status"] == "success":
                    return {
                        "success": True,
                        "payment_link": result["data"]["link"],
                        "reference": tx_ref
                    }
            
            return {
                "success": False,
                "error": f"Flutterwave payment initialization failed: {response.text}"
            }
    
    @staticmethod
    async def _initiate_paypal_payment(
        user_id: int,
        plan: str,
        price_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Initiate payment with PayPal"""
        # This is a simplified implementation
        # In a real implementation, you'd use PayPal's SDK
        
        return {
            "success": True,
            "payment_link": f"https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=EXAMPLE",
            "reference": f"sub-{user_id}-{plan}-{uuid.uuid4()}"
        }
    
    @staticmethod
    async def verify_flutterwave_payment(
        transaction_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Verify Flutterwave payment and create subscription"""
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if (
                    result["status"] == "success" and
                    result["data"]["status"] == "successful" and
                    result["data"]["currency"] == "USD"
                ):
                    # Extract plan from transaction reference
                    tx_ref = result["data"]["tx_ref"]
                    parts = tx_ref.split('-')
                    
                    if len(parts) >= 3:
                        user_id = int(parts[1])
                        plan = parts[2]
                        
                        # Create subscription
                        subscription = await crud.SubscriptionCRUD.create_subscription(
                            db,
                            schemas.SubscriptionCreate(
                                plan=plan,
                                amount=float(result["data"]["amount"]),
                                currency=result["data"]["currency"],
                                payment_method="flutterwave",
                                payment_reference=transaction_id
                            ),
                            user_id
                        )
                        
                        return {
                            "success": True,
                            "subscription_id": subscription.id,
                            "plan": plan,
                            "user_id": user_id
                        }
            
            return {
                "success": False,
                "error": "Payment verification failed"
            }