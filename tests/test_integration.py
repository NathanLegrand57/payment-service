import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app as fastapi_app
from app.database import Base
from app.models import Payment
import app.routes
import app.auth
import os
import stripe

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_integration.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={
                       "check_same_thread": False})
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    # Setup: Create the tables
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(monkeypatch):
    # Mock SessionLocal everywhere in the application to use the test database
    monkeypatch.setattr("app.routes.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.main.SessionLocal", TestingSessionLocal)

    # Bypass auth verification for tests
    fastapi_app.dependency_overrides[app.auth.verify_token] = lambda: True

    with TestClient(fastapi_app) as c:
        yield c

    # Cleanup dependencies
    fastapi_app.dependency_overrides.clear()


def test_full_payment_lifecycle_integration(client, mocker):
    """
    Test the full lifecycle: 
    1. Create payment (API -> DB + Stripe Mocked)
    2. Webhook success (Stripe -> API -> DB)
    3. Refund payment (API -> DB + Stripe Mocked)
    """

    # --- 1. CREATE PAYMENT ---
    # Mocking stripe.PaymentIntent.create
    mock_pi = mocker.Mock()
    mock_pi.id = "pi_integration_test_123"
    mock_pi.client_secret = "secret_test_456"
    mocker.patch("stripe.PaymentIntent.create", return_value=mock_pi)

    payload = {"order_id": "ORDER-INT-001", "amount": 2500, "currency": "eur"}
    response = client.post("/payments", json=payload)

    assert response.status_code == 200
    assert response.json()["client_secret"] == "secret_test_456"

    # Verify database state after creation
    db = TestingSessionLocal()
    payment = db.query(Payment).filter_by(order_id="ORDER-INT-001").first()
    assert payment is not None
    assert payment.id == "pi_integration_test_123"
    assert payment.status == "created"
    db.close()

    # --- 2. WEBHOOK SUCCESS ---
    # Mocking stripe.Webhook.construct_event
    # We construct a mock event payload
    mock_event = {
        "id": "evt_test",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_integration_test_123"
            }
        }
    }
    mocker.patch("stripe.Webhook.construct_event", return_value=mock_event)
    mocker.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})

    webhook_response = client.post(
        "/webhook",
        content="raw_stripe_payload",
        headers={"stripe-signature": "test_signature"}
    )

    assert webhook_response.status_code == 200
    assert webhook_response.json() == {"ok": True}

    # Verify database state after webhook
    db = TestingSessionLocal()
    updated_payment = db.query(Payment).filter_by(
        id="pi_integration_test_123").first()
    assert updated_payment.status == "paid"
    db.close()

    # --- 3. REFUND ---
    # Mocking stripe.Refund.create
    mocker.patch("stripe.Refund.create", return_value=mocker.Mock())

    refund_response = client.post("/refund?order_id=ORDER-INT-001")

    assert refund_response.status_code == 200
    assert refund_response.json()["status"] == "refunded"

    # Verify database state after refund
    db = TestingSessionLocal()
    final_payment = db.query(Payment).filter_by(
        order_id="ORDER-INT-001").first()
    assert final_payment.status == "refunded"
    db.close()


def test_webhook_non_existent_payment(client, mocker):
    """Test that webhook handles cases where payment ID is not in DB (logged or ignored)."""
    mock_event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_unknown"}}
    }
    mocker.patch("stripe.Webhook.construct_event", return_value=mock_event)

    response = client.post("/webhook", headers={"stripe-signature": "test"})
    assert response.status_code == 200


def test_same_order_id(client, mocker):
    """Test that calling create_payment with same order_id returns existing payment."""
    # First call
    mock_pi = mocker.Mock()
    mock_pi.id = "pi_first"
    mock_pi.client_secret = "secret_first"
    mocker.patch("stripe.PaymentIntent.create", return_value=mock_pi)

    client.post("/payments", json={"order_id": "SAME-ORDER", "amount": 1000})

    # Second call (stripe mock shouldn't be called again if DB check works)
    mock_pi_second = mocker.Mock()
    mocker.patch("stripe.PaymentIntent.create",
                 side_effect=Exception("Should not be called"))

    response = client.post(
        "/payments", json={"order_id": "SAME-ORDER", "amount": 1000})

    assert response.status_code == 200
    assert response.json()["payment_id"] == "pi_first"
    assert response.json()["status"] == "created"


def test_create_payment_database_integrity_on_stripe_error(client, mocker):
    """If Stripe fails, it should return an error and not leave a record in the database."""
    # Mock stripe.PaymentIntent.create to raise an exception
    mocker.patch("stripe.PaymentIntent.create",
                 side_effect=Exception("Stripe Service Unavailable"))

    payload = {"order_id": "ORDER-FAIL-001", "amount": 2500, "currency": "eur"}

    with pytest.raises(Exception): 
        client.post("/payments", json=payload)

    # Verify database is empty (no payment record created)
    db = TestingSessionLocal()
    payment = db.query(Payment).filter_by(order_id="ORDER-FAIL-001").first()
    assert payment is None
    db.close()
