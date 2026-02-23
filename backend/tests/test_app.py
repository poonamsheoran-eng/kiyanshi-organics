"""
First Tests for Kiyanshi Organics
Simple tests to get you started

Run with: pytest tests/test_app.py -v
"""

import json


# ==================== TEST 1: Health Check ====================

def test_health_check_works(client):
    """
    Test that the health check endpoint returns 200 OK
    
    This is the simplest possible test - just check if endpoint responds
    """
    # ARRANGE: Nothing needed, client is provided by pytest
    
    # ACT: Make a GET request to /api/health
    response = client.get('/api/health')
    
    # ASSERT: Check response
    assert response.status_code == 200
    print("✅ Health check endpoint is working!")


def test_health_check_returns_json(client):
    """
    Test that health check returns JSON data
    """
    # ACT
    response = client.get('/api/health')
    
    # ASSERT
    assert response.content_type == 'application/json'
    print("✅ Health check returns JSON!")


def test_health_check_has_status(client):
    """
    Test that health check response includes 'status' field
    """
    # ACT
    response = client.get('/api/health')
    data = json.loads(response.data)
    
    # ASSERT
    assert 'status' in data
    assert data['status'] == 'healthy'
    print(f"✅ Health status: {data['status']}")


# ==================== TEST 2: Metrics Endpoint ====================

def test_metrics_endpoint_exists(client):
    """
    Test that /api/metrics endpoint is accessible
    """
    response = client.get('/api/metrics')
    
    assert response.status_code == 200
    print("✅ Metrics endpoint is accessible!")


def test_metrics_returns_uptime(client):
    """
    Test that metrics includes uptime information
    """
    response = client.get('/api/metrics')
    data = json.loads(response.data)
    
    # Check that uptime fields exist
    assert 'uptime_seconds' in data
    assert 'uptime_hours' in data
    
    # Check they're numbers
    assert isinstance(data['uptime_seconds'], int)
    assert isinstance(data['uptime_hours'], float)
    
    print(f"✅ App uptime: {data['uptime_hours']} hours")


# ==================== TEST 3: Products Endpoint ====================

def test_get_products_works(client):
    """
    Test that we can fetch products list
    """
    response = client.get('/api/products')
    
    assert response.status_code == 200
    print("✅ Can fetch products!")


def test_products_returns_list(client):
    """
    Test that products endpoint returns an array/list
    """
    response = client.get('/api/products')
    data = json.loads(response.data)
    
    # Should be a list (even if empty)
    assert isinstance(data, list)
    print(f"✅ Products list has {len(data)} items")


# ==================== TEST 4: Authentication ====================

def test_auth_endpoint_exists(client):
    """
    Test that authentication endpoint is accessible
    """
    response = client.post('/api/auth',
                          data=json.dumps({
                              'mobile': '1234567890',
                              'password': 'test123'
                          }),
                          content_type='application/json')
    
    # Should respond (even if validation fails)
    assert response.status_code in [200, 201, 400, 401]
    print("✅ Auth endpoint is responding!")


def test_auth_rejects_missing_data(client):
    """
    Test that auth rejects requests with missing fields
    """
    # Try without password
    response = client.post('/api/auth',
                          data=json.dumps({'mobile': '1234567890'}),
                          content_type='application/json')
    
    assert response.status_code == 400
    print("✅ Auth correctly rejects incomplete data!")


def test_auth_rejects_short_password(client):
    """
    Test that auth enforces minimum password length
    """
    response = client.post('/api/auth',
                          data=json.dumps({
                              'mobile': '1234567890',
                              'password': 'abc'  # Too short!
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'at least 6 characters' in data['error']
    print("✅ Auth enforces password length!")


# ==================== BONUS: Integration Test ====================

def test_complete_flow(client):
    """
    Test a complete user flow: health check → view products → check metrics
    """
    # Step 1: Verify app is healthy
    health = client.get('/api/health')
    assert health.status_code == 200
    
    # Step 2: View products
    products = client.get('/api/products')
    assert products.status_code == 200
    
    # Step 3: Check that metrics were updated
    metrics = client.get('/api/metrics')
    data = json.loads(metrics.data)
    
    # products_viewed should have incremented
    assert data.get('products_viewed', 0) >= 1
    
    print("✅ Complete flow works end-to-end!")
