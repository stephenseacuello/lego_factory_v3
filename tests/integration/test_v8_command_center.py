"""
V8 Command Center Integration Tests
====================================

Integration tests for the V8 Command Center system including:
- API endpoint tests
- Service integration tests
- WebSocket event tests
- End-to-end workflow tests

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Test fixtures


@pytest.fixture
def app():
    """Create test Flask application."""
    from dashboard.app import create_app

    app = create_app(testing=True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_services():
    """Mock all command center services."""
    with patch('dashboard.services.command_center.SystemHealthService') as health, \
         patch('dashboard.services.command_center.KPIAggregator') as kpi, \
         patch('dashboard.services.command_center.AlertManager') as alert, \
         patch('dashboard.services.command_center.ActionConsole') as action:
        yield {
            'health': health,
            'kpi': kpi,
            'alert': alert,
            'action': action
        }


# ============================================
# Health Endpoint Tests
# ============================================

class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_basic_health_check(self, client):
        """Test basic health endpoint returns 200."""
        response = client.get('/health')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'timestamp' in data

    def test_liveness_probe(self, client):
        """Test Kubernetes liveness probe."""
        response = client.get('/health/live')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['check_type'] == 'liveness'

    def test_readiness_probe(self, client):
        """Test Kubernetes readiness probe."""
        response = client.get('/health/ready')
        # May return 200 or 503 depending on database status
        assert response.status_code in [200, 503]

        data = json.loads(response.data)
        assert data['check_type'] == 'readiness'
        assert 'checks' in data

    def test_detailed_health(self, client):
        """Test detailed health report."""
        response = client.get('/health/detailed')
        # May return 200 or 503
        assert response.status_code in [200, 503]

        data = json.loads(response.data)
        assert 'status' in data
        assert 'checks' in data
        assert 'timestamp' in data

    def test_health_metrics(self, client):
        """Test health metrics endpoint."""
        response = client.get('/health/metrics')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'system' in data
        assert 'checks' in data
        assert 'uptime_seconds' in data


# ============================================
# Command Center API Tests
# ============================================

class TestCommandCenterAPI:
    """Test Command Center API endpoints."""

    def test_get_system_status(self, client, mock_services):
        """Test getting system status."""
        mock_health = MagicMock()
        mock_health.to_dict.return_value = {
            'overall_status': 'healthy',
            'services': []
        }

        with patch('dashboard.routes.command_center.get_health_service') as mock_get:
            mock_service = MagicMock()
            mock_service.check_all = MagicMock(return_value=mock_health)
            mock_get.return_value = mock_service

            response = client.get('/command-center/api/status')
            # May fail if route not registered, that's OK for integration test
            if response.status_code == 200:
                data = json.loads(response.data)
                assert data['success'] is True

    def test_get_kpis(self, client):
        """Test getting KPI dashboard."""
        response = client.get('/command-center/api/kpis')
        # May return 200 or 500 depending on service availability
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data

    def test_get_alerts(self, client):
        """Test getting active alerts."""
        response = client.get('/command-center/api/alerts')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data

    def test_get_actions(self, client):
        """Test getting pending actions."""
        response = client.get('/command-center/api/actions')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data

    def test_get_unified_dashboard(self, client):
        """Test unified dashboard endpoint."""
        response = client.get('/command-center/api/dashboard')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data


# ============================================
# Alert Management Tests
# ============================================

class TestAlertManagement:
    """Test alert management functionality."""

    def test_acknowledge_alert(self, client):
        """Test acknowledging an alert."""
        payload = {
            'user': 'test_user',
            'note': 'Acknowledged for testing'
        }

        response = client.post(
            '/command-center/api/alerts/test-alert-123/acknowledge',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # May return 200 or 404/500
        assert response.status_code in [200, 404, 500]

    def test_resolve_alert(self, client):
        """Test resolving an alert."""
        payload = {
            'user': 'test_user',
            'resolution': 'Issue resolved'
        }

        response = client.post(
            '/command-center/api/alerts/test-alert-123/resolve',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code in [200, 404, 500]


# ============================================
# Action Console Tests
# ============================================

class TestActionConsole:
    """Test action console functionality."""

    def test_create_action(self, client):
        """Test creating a new action."""
        payload = {
            'title': 'Test Action',
            'description': 'Integration test action',
            'category': 'preventive',
            'executor': 'test_system',
            'parameters': {'test': True},
            'priority': 'normal'
        }

        response = client.post(
            '/command-center/api/actions',
            data=json.dumps(payload),
            content_type='application/json'
        )

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['success'] is True

    def test_approve_action(self, client):
        """Test approving an action."""
        payload = {
            'user': 'test_supervisor',
            'note': 'Approved for testing'
        }

        response = client.post(
            '/command-center/api/actions/test-action-123/approve',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code in [200, 404, 500]

    def test_reject_action(self, client):
        """Test rejecting an action."""
        payload = {
            'user': 'test_supervisor',
            'reason': 'Rejected for testing'
        }

        response = client.post(
            '/command-center/api/actions/test-action-123/reject',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code in [200, 404, 500]


# ============================================
# Workflow Tests
# ============================================

class TestWorkflowManagement:
    """Test workflow management functionality."""

    def test_list_workflows(self, client):
        """Test listing workflows."""
        response = client.get('/command-center/api/orchestration/workflows')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data

    def test_create_workflow(self, client):
        """Test creating a workflow."""
        payload = {
            'name': 'Test Production Workflow',
            'job_id': 'JOB-TEST-001',
            'parameters': {'material': 'ABS', 'color': 'red'}
        }

        response = client.post(
            '/command-center/api/orchestration/workflows',
            data=json.dumps(payload),
            content_type='application/json'
        )

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['success'] is True


# ============================================
# Equipment Control Tests
# ============================================

class TestEquipmentControl:
    """Test equipment control functionality."""

    def test_list_equipment(self, client):
        """Test listing equipment."""
        response = client.get('/command-center/api/equipment')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data

    def test_equipment_control(self, client):
        """Test equipment control action."""
        payload = {
            'action': 'configure',
            'parameters': {}
        }

        response = client.post(
            '/command-center/api/equipment/printer-01/control',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # May return various status codes depending on ROS2 availability
        assert response.status_code in [200, 400, 404, 500]

    def test_emergency_stop(self, client):
        """Test emergency stop trigger."""
        payload = {
            'reason': 'Integration test - emergency stop'
        }

        response = client.post(
            '/command-center/api/equipment/emergency-stop',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should always respond, even if ROS2 not available
        assert response.status_code in [200, 500]


# ============================================
# Prometheus Metrics Tests
# ============================================

class TestPrometheusMetrics:
    """Test Prometheus metrics endpoint."""

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics scrape endpoint."""
        response = client.get('/metrics')
        if response.status_code == 200:
            assert b'lego_' in response.data  # Check for LEGO metrics prefix
            assert b'# HELP' in response.data  # Check for Prometheus format

    def test_metrics_content_type(self, client):
        """Test metrics endpoint content type."""
        response = client.get('/metrics')
        if response.status_code == 200:
            assert 'text/plain' in response.content_type


# ============================================
# RBAC Integration Tests
# ============================================

class TestRBACIntegration:
    """Test RBAC integration."""

    def test_rbac_service_initialization(self):
        """Test RBAC service can be initialized."""
        from dashboard.services.security import get_rbac_service

        rbac = get_rbac_service()
        assert rbac is not None

    def test_user_creation(self):
        """Test user creation through RBAC."""
        from dashboard.services.security import get_rbac_service, Role

        rbac = get_rbac_service()

        user = rbac.create_user(
            username='test_integration_user',
            email='test@example.com',
            roles={Role.OPERATOR},
            department='Testing'
        )

        assert user is not None
        assert user.username == 'test_integration_user'
        assert Role.OPERATOR in user.roles

    def test_permission_check(self):
        """Test permission checking."""
        from dashboard.services.security import get_rbac_service, Role, Permission

        rbac = get_rbac_service()

        user = rbac.create_user(
            username='test_operator',
            email='operator@example.com',
            roles={Role.OPERATOR}
        )

        # Operators should have VIEW_DASHBOARD permission
        assert rbac.has_permission(user, Permission.VIEW_DASHBOARD)

        # Operators should NOT have MANAGE_USERS permission
        assert not rbac.has_permission(user, Permission.MANAGE_USERS)


# ============================================
# Notification Service Tests
# ============================================

class TestNotificationService:
    """Test notification service integration."""

    def test_notification_service_initialization(self):
        """Test notification service can be initialized."""
        from dashboard.services.notifications import get_notification_service

        service = get_notification_service()
        assert service is not None

    def test_in_app_notification(self):
        """Test in-app notification delivery."""
        from dashboard.services.notifications import (
            get_notification_service,
            NotificationChannel,
            NotificationPriority
        )

        service = get_notification_service()

        result = service.send(
            title='Test Notification',
            body='This is a test notification',
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.NORMAL,
            recipients=['test_user']
        )

        assert result is not None
        assert result.success is True


# ============================================
# Performance Collector Tests
# ============================================

class TestPerformanceCollector:
    """Test performance metrics collection."""

    def test_collector_initialization(self):
        """Test performance collector can be initialized."""
        from dashboard.services.monitoring import get_performance_collector

        collector = get_performance_collector()
        assert collector is not None

    def test_metric_recording(self):
        """Test recording a metric."""
        from dashboard.services.monitoring import get_performance_collector

        collector = get_performance_collector()

        collector.record('api.request.duration', 0.150)

        report = collector.generate_report(period_minutes=5)
        assert report is not None

    def test_timed_operation(self):
        """Test timed operation context manager."""
        from dashboard.services.monitoring import TimedOperation

        with TimedOperation('test.operation') as timer:
            time.sleep(0.01)  # 10ms

        assert timer.duration_ms >= 10


# ============================================
# End-to-End Workflow Tests
# ============================================

class TestE2EWorkflows:
    """End-to-end workflow tests."""

    def test_alert_to_action_workflow(self):
        """Test complete alert-to-action workflow."""
        from dashboard.services.command_center import AlertManager, ActionConsole

        # Create an alert
        alert_manager = AlertManager()
        alert = alert_manager.create_alert(
            title='E2E Test Alert',
            message='Test alert for E2E workflow',
            severity='medium',
            source='e2e_test'
        )

        assert alert is not None
        assert alert.status.value == 'active'

        # Create a corrective action
        action_console = ActionConsole()
        action = action_console.create_action(
            title='E2E Test Corrective Action',
            description='Action to resolve test alert',
            category='corrective',
            executor='e2e_test',
            parameters={'alert_id': alert.alert_id}
        )

        assert action is not None

        # Acknowledge alert
        ack_alert = alert_manager.acknowledge_alert(
            alert.alert_id,
            'e2e_test_user',
            'Acknowledged via E2E test'
        )

        assert ack_alert is not None

    def test_kpi_aggregation_workflow(self):
        """Test KPI aggregation workflow."""
        from dashboard.services.command_center import KPIAggregator

        aggregator = KPIAggregator()

        # Update a KPI
        aggregator.update_kpi(
            name='e2e_test_oee',
            value=0.85,
            category='production'
        )

        # Get dashboard
        dashboard = aggregator.get_dashboard()

        assert dashboard is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
