"""
First Tests for Kiyanshi Organics
Simple tests to get you started

Run with: pytest tests/test_app.py -v
"""

import json


# ==================== TEST 1: Health Check ====================

def test_health_check_returns_json(client):
    """
    Test that health check returns JSON data
    """
    # ACT
    response = client.get('/api/health')
    
    # ASSERT
    assert response.content_type == 'application/json'
    print("✅ Health check returns JSON!")


