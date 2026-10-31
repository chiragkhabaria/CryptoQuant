"""
Pytest Configuration and Fixtures

Shared test configuration and fixtures for the CryptoQuant test suite.
"""
import pytest


@pytest.fixture(autouse=True)
def _disable_job_log(monkeypatch):
    """Keep scheduler job tests from writing to a real database."""
    monkeypatch.setenv("JOB_LOG_ENABLED", "0")


@pytest.fixture
def sample_market_data():
    """Fixture providing sample market data for testing."""
    # TODO: Implement sample data fixture
    pass


@pytest.fixture
def mock_coinbase_client():
    """Fixture providing a mocked Coinbase API client."""
    # TODO: Implement mock client
    pass


@pytest.fixture
def test_database():
    """Fixture providing a test database session."""
    # TODO: Implement test database fixture
    pass
