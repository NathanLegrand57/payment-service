import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app as fastapi_app
from app.routes import router
from app.database import Base
import app.routes
import app.auth

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_temp.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={
                       "check_same_thread": False})
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(monkeypatch):
    # Mock SessionLocal in routes
    monkeypatch.setattr(app.routes, "SessionLocal", TestingSessionLocal)
    # Mock auth verification
    fastapi_app.dependency_overrides[app.auth.verify_token] = lambda: True
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def test_create_payment_success(client, mocker):
    # Mock stripe_service.create_payment
    mock_intent = mocker.Mock()
    mock_intent.id = "pi_123"
    mock_intent.client_secret = "secret_123"
    mocker.patch("app.routes.create_payment", return_value=mock_intent)

    response = client.post(
        "/payments",
        json={"order_id": "ORDER-100", "amount": 5000, "currency": "eur"}
    )

    assert response.status_code == 200
    assert response.json() == {"client_secret": "secret_123"}


def test_refund_payment_success(client, mocker):
    # Setup: create a paid payment in DB
    db = TestingSessionLocal()
    from app.models import Payment
    p = Payment(id="pi_123", order_id="ORDER-100",
                amount=5000, currency="eur", status="paid")
    db.add(p)
    db.commit()
    db.close()

    # Mock stripe_service.refund_payment
    mocker.patch("app.routes.refund_payment", return_value=True)

    response = client.post("/refund?order_id=ORDER-100")

    assert response.status_code == 200
    assert response.json()["status"] == "refunded"
