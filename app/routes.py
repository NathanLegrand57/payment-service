from fastapi import APIRouter, Depends
from app.auth import verify_token
from app.database import SessionLocal
from app.models import Payment
from app.stripe_service import create_payment, refund_payment

router = APIRouter()

@router.post("/payments")
def create_payment_api(
    order_id: str,
    amount: int,
    currency: str,
    auth=Depends(verify_token)
):
    db = SessionLocal()

    existing = db.query(Payment).filter_by(order_id=order_id).first()
    if existing:
        return {"payment_id": existing.id, "status": existing.status}

    intent = create_payment(amount, currency, order_id)

    payment = Payment(
        id=intent.id,
        order_id=order_id,
        amount=amount,
        currency=currency,
        status="created"
    )

    db.add(payment)
    db.commit()
    db.close()

    return {"client_secret": intent.client_secret}

@router.post("/refund")
def refund(order_id: str, auth=Depends(verify_token)):
    db = SessionLocal()

    payment = db.query(Payment).filter_by(order_id=order_id).first()
    if not payment or payment.status == "refunded":
        return {"message": "Nothing to refund"}

    refund_payment(payment.id)
    payment.status = "refunded"
    db.commit()
    db.close()

    return {"status": "refunded"}
