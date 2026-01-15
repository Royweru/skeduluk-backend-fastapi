# app/services/payment_service.py
import uuid
import httpx
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import hmac
import json

from ..config import settings
from .. import crud, models, schemas
from app.crud.subscription_crud import SubscriptionCRUD
class PaymentService:
    @staticmethod
    async def initiate_payment(
        user_id: int,
        plan: str,
        payment_method: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Initiate payment for a subscription plan"""
        
        # 1. Define Pricing (USD for Global, KES for Paystack/Kenya)
        # You should probably move this to a database config later
        plan_prices_usd = {
            "basic": {"amount": 9.99, "currency": "USD"},
            "pro": {"amount": 19.99, "currency": "USD"},
            "enterprise": {"amount": 49.99, "currency": "USD"}
        }
        
        # Approximate KES conversion (1 USD = ~130 KES)
        plan_prices_kes = {
            "basic": {"amount": 1300, "currency": "KES"},
            "pro": {"amount": 2600, "currency": "KES"},
            "enterprise": {"amount": 6500, "currency": "KES"}
        }
        
        plan_key = plan.lower()
        if plan_key not in plan_prices_usd:
            return {"success": False, "error": "Invalid plan"}
            
        # 2. Route to correct provider logic
        if payment_method.lower() == "paystack":
            # Use KES pricing for Paystack (Best for M-PESA)
            price_info = plan_prices_kes[plan_key]
            return await PaymentService._initiate_paystack_payment(
                user_id, plan, price_info
            )
            
        elif payment_method.lower() == "flutterwave":
            price_info = plan_prices_usd[plan_key]
            return await PaymentService._initiate_flutterwave_payment(
                user_id, plan, price_info
            )
            
        elif payment_method.lower() == "paypal":
            price_info = plan_prices_usd[plan_key]
            return await PaymentService._initiate_paypal_payment(
                user_id, plan,price_info
            )
        else:
            return {"success": False, "error": "Unsupported payment method"}

    # ==========================================
    # PAYSTACK INTEGRATION
    # ==========================================
    @staticmethod
    async def _initiate_paystack_payment(
        user_id: int,
        plan: str,
        price_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Initiate payment with Paystack"""
        
        # 1. Generate a unique reference
        tx_ref = f"sub-{user_id}-{plan}-{uuid.uuid4().hex[:8]}"
        
        # 2. Prepare payload
        # Paystack expects amount in "kobo" (lowest currency unit). 
        # So 100 KES = 10000 sent to API.
        amount_in_kobo = int(price_info["amount"] * 100)
        
        # This URL is where Paystack sends the user AFTER payment
        # Point this to your NEXT.JS Frontend verification page
        callback_url = f"{settings.FRONTEND_URL}/payment/verify?provider=paystack"

        payload = {
            "email": f"user{user_id}@example.com", # TODO: Get real email from User DB
            "amount": amount_in_kobo,
            "currency": price_info["currency"],
            "reference": tx_ref,
            "callback_url": callback_url,
            "metadata": {
                "user_id": user_id,
                "plan": plan,
                "cancel_action": f"{settings.FRONTEND_URL}/pricing"
            }
        }
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        # 3. Call Paystack API
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.paystack.co/transaction/initialize",
                    headers=headers,
                    json=payload
                )
                
                data = response.json()
                
                if response.status_code == 200 and data["status"] is True:
                    return {
                        "success": True,
                        "payment_link": data["data"]["authorization_url"],
                        "reference": tx_ref
                    }
                else:
                    return {
                        "success": False, 
                        "error": data.get("message", "Paystack initialization failed")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

    @staticmethod
    async def verify_paystack_payment(
        reference: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Verify Paystack payment"""
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }
        
        async with httpx.AsyncClient() as client:
            # Verify endpoint takes the reference
            response = await client.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=headers
            )
            
            if response.status_code != 200:
                 return {"success": False, "error": "Verification request failed"}

            result = response.json()
            
            # Check logic: Status MUST be 'success'
            if result["status"] is True and result["data"]["status"] == "success":
                data = result["data"]
                
                # Extract metadata we sent earlier
                metadata = data.get("metadata", {})
                user_id = metadata.get("user_id")
                plan = metadata.get("plan")
                
                # Fallback extraction if metadata is missing (parsing reference)
                if not user_id or not plan:
                    parts = data["reference"].split('-')
                    if len(parts) >= 3:
                        user_id = int(parts[1])
                        plan = parts[2]

                # Convert amount back from Kobo to Main Unit
                paid_amount = float(data["amount"]) / 100
                currency = data["currency"]

                # Create the subscription in DB
                subscription = await SubscriptionCRUD.create_subscription(
                    db,
                    schemas.SubscriptionCreate(
                        plan=plan,
                        amount=paid_amount,
                        currency=currency,
                        payment_method="paystack",
                        payment_reference=reference
                    ),
                    user_id
                )
                
                return {
                    "success": True,
                    "subscription_id": subscription.id,
                    "plan": plan,
                    "user_id": user_id
                }
            
            return {"success": False, "error": "Payment was not successful"}
            
    
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
                        subscription = await SubscriptionCRUD.create_subscription(
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
    @staticmethod
    async def process_webhook_event(
        signature: str,
        payload_bytes: bytes, 
        db: AsyncSession
    ) -> bool:
        """
        Securely process Paystack webhook.
        Returns True if processed successfully (or ignored safely).
        """
        # 1. SECURITY: Verify the HMAC Signature
        # We must use the raw bytes of the body, not parsed JSON
        secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
        expected_signature = hmac.new(secret, payload_bytes, hashlib.sha512).hexdigest()
        
        if signature != expected_signature:
            print(f"⚠️ Security Alert: Invalid Webhook Signature. Received: {signature}")
            return False

        # 2. Parse the Event
        try:
            event = json.loads(payload_bytes)
        except json.JSONDecodeError:
            return False

        event_type = event.get("event")
        data = event.get("data", {})
        reference = data.get("reference")

        print(f"🔔 Webhook received: {event_type} for ref: {reference}")

        # 3. Handle 'charge.success' (The only one we care about for now)
        if event_type == "charge.success":
            # A. Idempotency Check: Did we already save this?
            existing_sub = await SubscriptionCRUD.get_by_payment_reference(db, reference)
            if existing_sub:
                print(f"✓ Payment {reference} already processed. Skipping.")
                return True

            # B. Extract Metadata (We sent this during initialization)
            metadata = data.get("metadata", {})
            user_id = metadata.get("user_id")
            plan = metadata.get("plan")

            # Fallback if metadata is missing
            if not user_id or not plan:
                parts = reference.split('-') # Assumes format: sub-{user_id}-{plan}-{uuid}
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    plan = parts[2]
            
            if not user_id:
                print(" Could not identify user from webhook")
                return True # Return True to stop Paystack from retrying bad data

            # C. Create the Subscription
            # Convert Kobo to Main Currency (e.g., 1000 Kobo -> 10 KES)
            amount = float(data.get("amount", 0)) / 100
            currency = data.get("currency", "KES")

            await SubscriptionCRUD.create_subscription(
                db,
                schemas.SubscriptionCreate(
                    plan=plan,
                    amount=amount,
                    currency=currency,
                    payment_method="paystack",
                    payment_reference=reference
                ),
                user_id
            )
            print(f"✅ Subscription created via Webhook for User {user_id}")
            return True

        # Return True for other events (like 'transfer.success') to acknowledge receipt
        return True