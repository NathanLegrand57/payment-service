from sqlalchemy import Column, String, Integer
from app.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)          # Stripe PaymentIntent ID
    order_id = Column(String, unique=True, index=True)
    amount = Column(Integer)
    currency = Column(String)
    status = Column(String)                        # created | paid | refunded
