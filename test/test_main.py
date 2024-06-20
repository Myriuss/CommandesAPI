import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, get_db, Base, Order, OrderDetail
from sqlalchemy_utils import database_exists, create_database, drop_database

# Override database settings for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_order.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to override dependency and use TestingSessionLocal
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Update dependency in the app
app.dependency_overrides[get_db] = override_get_db

# Create and drop database for testing
def setup_module(module):
    if not database_exists(engine.url):
        create_database(engine.url)
        Base.metadata.create_all(bind=engine)

def teardown_module(module):
    drop_database(engine.url)

# Test client using TestClient from FastAPI
client = TestClient(app)

# Test data
test_order_data = {
    "customer_name": "John Doe",
    "total_amount": 100.0
}

test_order_update_data = {
    "customer_name": "Jane Smith",
    "total_amount": 150.0
}

test_order_detail_data = {
    "product_id": 1,
    "quantity": 5
}

# Test cases
def test_create_order():
    response = client.post("/orders/", json=test_order_data)
    assert response.status_code == 201
    assert response.json()["customer_name"] == test_order_data["customer_name"]
    assert response.json()["total_amount"] == test_order_data["total_amount"]
    assert "id" in response.json()

def test_read_orders():
    response = client.get("/orders/")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_read_order():
    created_order = client.post("/orders/", json=test_order_data).json()
    order_id = created_order["id"]
    response = client.get(f"/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["customer_name"] == test_order_data["customer_name"]
    assert response.json()["total_amount"] == test_order_data["total_amount"]

def test_update_order():
    created_order = client.post("/orders/", json=test_order_data).json()
    order_id = created_order["id"]
    response = client.put(f"/orders/{order_id}", json=test_order_update_data)
    assert response.status_code == 200
    assert response.json()["customer_name"] == test_order_update_data["customer_name"]
    assert response.json()["total_amount"] == test_order_update_data["total_amount"]

def test_delete_order():
    created_order = client.post("/orders/", json=test_order_data).json()
    order_id = created_order["id"]
    response = client.delete(f"/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Order deleted"

def test_create_order_detail():
    created_order = client.post("/orders/", json=test_order_data).json()
    order_id = created_order["id"]
    test_order_detail_data["order_id"] = order_id
    response = client.post(f"/orders/{order_id}/details/", json=test_order_detail_data)
    assert response.status_code == 201
    assert response.json()["order_id"] == order_id
    assert response.json()["product_id"] == test_order_detail_data["product_id"]

def test_read_order_details():
    created_order = client.post("/orders/", json=test_order_data).json()
    order_id = created_order["id"]
    test_order_detail_data["order_id"] = order_id
    client.post(f"/orders/{order_id}/details/", json=test_order_detail_data)
    response = client.get(f"/orders/{order_id}/details/")
    assert response.status_code == 200
    assert len(response.json()) > 0
    assert response.json()[0]["order_id"] == order_id
    assert response.json()[0]["product_id"] == test_order_detail_data["product_id"]
