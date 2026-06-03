
```
Wait, let's finish the test file.
```python tests/test_routes.py
import pytest
import logging
from app import app, db, User, Product
from services import UserService, ProductService

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['ADMIN_BEARER_TOKEN'] = 'test-admin-token'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def test_register_user(client):
    response = client.post('/register', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    assert response.status_code == 201
    assert response.get_json()['message'] == 'User registered successfully'

def test_register_duplicate_user(client):
    client.post('/register', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    response = client.post('/register', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    assert response.status_code == 400
    assert 'already exists' in response.get_json()['error']

def test_login_user(client):
    client.post('/register', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    response = client.post('/login', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    assert response.status_code == 200
    assert response.get_json()['message'] == 'Logged in successfully'

def test_login_invalid_credentials(client):
    response = client.post('/login', json={
        'email': 'nonexistent@example.com',
        'password': 'password123'
    })
    assert response.status_code == 401

def test_logout_user(client):
    response = client.post('/logout')
    assert response.status_code == 200

def test_create_product_unauthorized(client):
    response = client.post('/products', json={
        'name': 'Laptop',
        'price': 999.99
    })
    assert response.status_code == 401

def test_create_product_authorized(client):
    client.post('/register', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    client.post('/login', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    response = client.post('/products', json={
        'name': 'Laptop',
        'price': 999.99,
        'description': 'A high-end laptop'
    })
    assert response.status_code == 201
    assert response.get_json()['product
