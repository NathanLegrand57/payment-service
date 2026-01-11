import os
from pathlib import Path
from dotenv import load_dotenv
import stripe

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_payment(amount: int, currency: str, idempotency_key: str):
    return stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        automatic_payment_methods={"enabled": True},
        idempotency_key=idempotency_key
    )

def refund_payment(payment_intent_id: str):
    return stripe.Refund.create(payment_intent=payment_intent_id)
