import pytest
from fastapi.testclient import TestClient
from main import app, create_access_token
from datetime import datetime, timedelta

client = TestClient(app)

# Simulating token generation for testing purposes
@pytest.fixture(scope="module")
def access_token():
    return create_access_token(data={"sub": "user"})

# Test endpoint for login and obtaining access token
def test_login():
    # Attempt to log in with valid credentials
    response = client.post("/token", params={"username": "user", "password": "password"})

    # Print out the response content for debugging purposes
    #print(response.content)

    assert response.status_code == 200
    assert "access_token" in response.json()


# Test CRUD operations for orders
def test_create_order(access_token):
    response = client.post("/orders/",
                           headers={"Authorization": f"Bearer {access_token}"},
                           json={"customer_name": "John Doe", "total_amount": 100.0})
    assert response.status_code == 201
    assert response.json()["customer_name"] == "John Doe"

def test_read_orders(access_token):
    response = client.get("/orders/",
                          headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# Test CRUD operations for order details
def test_create_order_detail(access_token):
    # Assuming order_id 1 exists (you may need to adjust based on existing data)
    response = client.post("/orders/1/details/",
                           headers={"Authorization": f"Bearer {access_token}"},
                           json={"product_id": 1, "quantity": 5})
    assert response.status_code == 201
    assert response.json()["product_id"] == 1

def test_read_order_details(access_token):
    # Assuming order_id 1 exists (you may need to adjust based on existing data)
    response = client.get("/orders/1/details/",
                          headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
