"""
LegoMCP v5.0 UI Template Tests
World-Class Manufacturing System

Verifies that all UI pages render correctly with the Flask app.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client():
    """Create test client."""
    from app import create_app
    app = create_app('testing')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestUIPages:
    """Test all UI pages render correctly."""

    def test_index_page(self, client):
        """Test main dashboard page."""
        response = client.get('/')
        assert response.status_code == 200

    def test_catalog_page(self, client):
        """Test catalog list page."""
        response = client.get('/catalog/')
        assert response.status_code == 200

    def test_builder_page(self, client):
        """Test builder page."""
        response = client.get('/builder/')
        assert response.status_code == 200

    def test_workspace_page(self, client):
        """Test workspace page."""
        response = client.get('/workspace/')
        assert response.status_code == 200

    def test_collection_page(self, client):
        """Test collection page."""
        response = client.get('/collection/')
        assert response.status_code == 200

    def test_builds_page(self, client):
        """Test builds page."""
        response = client.get('/builds/')
        assert response.status_code == 200

    def test_insights_page(self, client):
        """Test insights page."""
        response = client.get('/insights/')
        assert response.status_code == 200

    def test_scan_page(self, client):
        """Test scan page."""
        response = client.get('/scan/')
        assert response.status_code == 200

    def test_status_page(self, client):
        """Test status page."""
        response = client.get('/status/')
        assert response.status_code == 200

    def test_history_page(self, client):
        """Test history page."""
        response = client.get('/history/')
        assert response.status_code == 200

    def test_tools_page(self, client):
        """Test tools page."""
        response = client.get('/tools/')
        assert response.status_code == 200

    def test_settings_page(self, client):
        """Test settings page."""
        response = client.get('/settings/')
        assert response.status_code == 200

    def test_files_page(self, client):
        """Test files page."""
        response = client.get('/files/')
        assert response.status_code == 200


class TestErrorPages:
    """Test error page handling."""

    def test_404_page(self, client):
        """Test 404 error page."""
        response = client.get('/nonexistent-page-12345')
        assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
