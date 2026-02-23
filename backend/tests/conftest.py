"""
Test configuration and fixtures
This file is automatically loaded by pytest
"""

import pytest
import os
from app import app as flask_app

@pytest.fixture
def app():
    """Create application for testing"""
    flask_app.config['TESTING'] = True
    
    # Use test database (optional - for now we'll use same DB)
    # In production, you'd use a separate test database
    
    yield flask_app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()
