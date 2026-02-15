import os
import stripe
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException

from app.routes import router
from app.database import Base, engine, SessionLocal
from app.models import Payment

# Force-load .env (Windows-safe)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

app = FastAPI(title="Cinema Payment Microservice")

app.include_router(router)

Base.metadata.create_all(bind=engine)

@app.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = SessionLocal()

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        payment = db.get(Payment, intent["id"])
        if payment and payment.status != "paid":
            payment.status = "paid"
            db.commit()

    db.close()
    return {"ok": True}
