"""
Unit tests for QMS NCR/CAPA Service.
NCR = Non-Conformance Report, CAPA = Corrective And Preventive Action
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime

from services.qms.ncr_service import NCRService, get_ncr_service


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock()
    session.add = Mock()
    session.flush = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def service(mock_session):
    return NCRService(mock_session)


@pytest.fixture
def mock_ncr():
    ncr = MagicMock()
    ncr.id = 1
    ncr.ncr_number = 'NCR-20240115-A1B2'
    ncr.is_deleted = False
    ncr.to_dict.return_value = {'ncr_number': 'NCR-20240115-A1B2', 'status': 'draft'}
    return ncr


@pytest.fixture
def mock_capa():
    capa = MagicMock()
    capa.id = 1
    capa.capa_number = 'CAPA-20240115-TEST'
    capa.actions = []
    capa.to_dict.return_value = {'capa_number': 'CAPA-20240115-TEST', 'status': 'draft'}
    return capa


class TestNCRServiceBasics:
    """Tests for NCRService initialization."""

    def test_service_initialization(self, mock_session):
        svc = NCRService(mock_session)
        assert svc.session == mock_session

    def test_get_ncr_service_with_session(self):
        session = Mock()
        svc = get_ncr_service(session)
        assert isinstance(svc, NCRService)


class TestNCRLifecycle:
    """Tests for NCR lifecycle: create -> disposition -> close."""

    @patch('models.qms.ncr_capa.NonConformanceReport')
    def test_create_ncr(self, mock_ncr_class, service, mock_session):
        mock_instance = MagicMock()
        mock_instance.ncr_number = 'NCR-20240115-TEST'
        mock_instance.to_dict.return_value = {'ncr_number': 'NCR-20240115-TEST', 'status': 'draft'}
        mock_ncr_class.return_value = mock_instance

        result = service.create_ncr({'title': 'Test', 'description': 'Desc', 'detected_by': 'user1'})

        assert result['ncr_number'] == 'NCR-20240115-TEST'
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_get_ncr_found(self, service, mock_session, mock_ncr):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_ncr

        result = service.get_ncr('NCR-20240115-A1B2')

        assert result['ncr_number'] == 'NCR-20240115-A1B2'

    def test_get_ncr_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_ncr('NCR-NONEXISTENT')

        assert result is None

    def test_set_disposition_success(self, service, mock_session, mock_ncr):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_ncr
        mock_ncr.to_dict.return_value = {'ncr_number': 'NCR-001', 'disposition': 'rework'}

        result = service.set_disposition('NCR-001', 'rework', 'Can be reworked', 'qa_mgr')

        assert result['disposition'] == 'rework'
        mock_session.flush.assert_called_once()

    def test_set_disposition_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.set_disposition('NCR-NONE', 'rework', 'Reason', 'user')

        assert result is None

    def test_close_ncr_success(self, service, mock_session, mock_ncr):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_ncr
        mock_ncr.to_dict.return_value = {'status': 'closed', 'actual_cost': 150.0}

        result = service.close_ncr('NCR-001', 'user1', actual_cost=150.0)

        assert result['status'] == 'closed'
        assert result['actual_cost'] == 150.0
        mock_session.flush.assert_called_once()

    def test_close_ncr_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.close_ncr('NCR-NONE', 'user1')

        assert result is None


class TestCAPAWorkflow:
    """Tests for CAPA workflow: create -> add actions -> complete -> verify effectiveness."""

    @patch('models.qms.ncr_capa.CAPA')
    def test_create_capa(self, mock_capa_class, service, mock_session):
        mock_instance = MagicMock()
        mock_instance.capa_number = 'CAPA-20240115-TEST'
        mock_instance.to_dict.return_value = {'capa_number': 'CAPA-20240115-TEST', 'status': 'draft'}
        mock_capa_class.return_value = mock_instance

        result = service.create_capa({'title': 'Action', 'problem_statement': 'Problem', 'owner_id': 'eng1'})

        assert result['capa_number'] == 'CAPA-20240115-TEST'
        mock_session.add.assert_called_once()

    @patch('models.qms.ncr_capa.CAPA')
    def test_create_capa_linked_to_ncr(self, mock_capa_class, service, mock_session, mock_ncr):
        # Setup NCR query to return our mock NCR
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_ncr
        mock_session.query.return_value = mock_query

        mock_instance = MagicMock()
        mock_instance.capa_number = 'CAPA-20240115-TEST'
        mock_instance.to_dict.return_value = {'capa_number': 'CAPA-20240115-TEST', 'status': 'draft'}
        mock_capa_class.return_value = mock_instance

        result = service.create_capa({
            'title': 'Action',
            'problem_statement': 'Problem',
            'owner_id': 'eng1',
            'ncr_number': 'NCR-20240115-A1B2'
        })

        assert result['capa_number'] == 'CAPA-20240115-TEST'
        assert mock_ncr.capa_required is True

    def test_get_capa_found(self, service, mock_session, mock_capa):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_capa

        result = service.get_capa('CAPA-20240115-TEST')

        assert result is not None
        assert 'actions' in result

    def test_get_capa_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_capa('CAPA-NONE')

        assert result is None

    @patch('models.qms.ncr_capa.CAPAAction')
    def test_add_capa_action(self, mock_action_class, service, mock_session, mock_capa):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_capa
        mock_action = MagicMock()
        mock_action.to_dict.return_value = {'action_number': 1, 'status': 'pending'}
        mock_action_class.return_value = mock_action

        result = service.add_capa_action('CAPA-001', {'description': 'Update docs', 'assigned_to': 'doc1'})

        assert result['action_number'] == 1
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_add_capa_action_capa_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.add_capa_action('CAPA-NONE', {'description': 'Update docs', 'assigned_to': 'doc1'})

        assert result is None

    def test_complete_capa_action(self, service, mock_session):
        mock_action = MagicMock()
        mock_action.to_dict.return_value = {'action_number': 1, 'status': 'completed'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_action

        result = service.complete_capa_action('action_001', 'user1', 'Done', evidence=['DOC-001'])

        assert result['status'] == 'completed'
        assert mock_action.status == 'completed'
        assert mock_action.completion_notes == 'Done'
        assert mock_action.evidence == ['DOC-001']
        mock_session.flush.assert_called_once()

    def test_complete_capa_action_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.complete_capa_action('action_none', 'user1', 'Done')

        assert result is None

    def test_verify_capa_effectiveness_positive(self, service, mock_session, mock_capa):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_capa
        mock_capa.to_dict.return_value = {'is_effective': True, 'status': 'closed'}

        result = service.verify_capa_effectiveness('CAPA-001', True, 'No recurrence', 'qa_mgr')

        assert result['is_effective'] is True
        assert result['status'] == 'closed'
        assert mock_capa.is_effective is True
        mock_session.flush.assert_called_once()

    def test_verify_capa_effectiveness_negative(self, service, mock_session, mock_capa):
        mock_session.query.return_value.filter.return_value.first.return_value = mock_capa
        mock_capa.to_dict.return_value = {'is_effective': False, 'status': 'action_planning'}

        result = service.verify_capa_effectiveness('CAPA-001', False, 'Issue recurred', 'qa_mgr')

        assert result['is_effective'] is False
        assert result['status'] == 'action_planning'
        assert mock_capa.is_effective is False

    def test_verify_capa_effectiveness_not_found(self, service, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.verify_capa_effectiveness('CAPA-NONE', True, 'No recurrence', 'qa_mgr')

        assert result is None


class TestNCRMetrics:
    """Tests for NCR metrics and reporting."""

    def test_get_ncr_metrics(self, service, mock_session):
        # Setup mock for the three separate queries in get_ncr_metrics
        mock_severity_enum = MagicMock()
        mock_severity_enum.value = 'critical'

        mock_total_query = Mock()
        mock_total_query.filter.return_value.scalar.return_value = 15

        mock_severity_query = Mock()
        mock_severity_query.filter.return_value.group_by.return_value.all.return_value = [
            (mock_severity_enum, 2),
            (MagicMock(value='minor'), 8)
        ]

        mock_open_query = Mock()
        mock_open_query.filter.return_value.scalar.return_value = 5

        # The method calls session.query three times
        mock_session.query.side_effect = [mock_total_query, mock_severity_query, mock_open_query]

        result = service.get_ncr_metrics(days=30)

        assert result['period_days'] == 30
        assert result['total_ncrs'] == 15
        assert result['open_ncrs'] == 5
        assert 'by_severity' in result

    def test_get_ncr_metrics_default_period(self, service, mock_session):
        mock_total_query = Mock()
        mock_total_query.filter.return_value.scalar.return_value = 10

        mock_severity_query = Mock()
        mock_severity_query.filter.return_value.group_by.return_value.all.return_value = []

        mock_open_query = Mock()
        mock_open_query.filter.return_value.scalar.return_value = 3

        mock_session.query.side_effect = [mock_total_query, mock_severity_query, mock_open_query]

        result = service.get_ncr_metrics()

        assert result['period_days'] == 30


class TestNCRFiltering:
    """Tests for NCR filtering and listing."""

    def _setup_query_mock(self, mock_session, ncrs):
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = ncrs
        mock_session.query.return_value = mock_query
        return mock_query

    def test_get_ncrs_no_filters(self, service, mock_session):
        mock_ncr1, mock_ncr2 = MagicMock(), MagicMock()
        mock_ncr1.to_dict.return_value = {'ncr_number': 'NCR-001'}
        mock_ncr2.to_dict.return_value = {'ncr_number': 'NCR-002'}
        self._setup_query_mock(mock_session, [mock_ncr1, mock_ncr2])

        result = service.get_ncrs()

        assert len(result) == 2
        assert result[0]['ncr_number'] == 'NCR-001'
        assert result[1]['ncr_number'] == 'NCR-002'

    def test_get_ncrs_with_status_filter(self, service, mock_session):
        mock_ncr = MagicMock()
        mock_ncr.to_dict.return_value = {'ncr_number': 'NCR-001', 'status': 'submitted'}
        self._setup_query_mock(mock_session, [mock_ncr])

        result = service.get_ncrs(status='submitted')

        assert len(result) == 1
        assert result[0]['status'] == 'submitted'

    def test_get_ncrs_with_severity_filter(self, service, mock_session):
        mock_ncr = MagicMock()
        mock_ncr.to_dict.return_value = {'ncr_number': 'NCR-001', 'severity': 'critical'}
        self._setup_query_mock(mock_session, [mock_ncr])

        result = service.get_ncrs(severity='critical')

        assert len(result) == 1
        assert result[0]['severity'] == 'critical'

    def test_get_ncrs_with_type_filter(self, service, mock_session):
        mock_ncr = MagicMock()
        mock_ncr.to_dict.return_value = {'ncr_number': 'NCR-001', 'ncr_type': 'product'}
        self._setup_query_mock(mock_session, [mock_ncr])

        result = service.get_ncrs(ncr_type='product')

        assert len(result) == 1
        assert result[0]['ncr_type'] == 'product'

    def test_get_ncrs_with_multiple_filters(self, service, mock_session):
        mock_ncr = MagicMock()
        mock_ncr.to_dict.return_value = {'ncr_number': 'NCR-001', 'severity': 'critical', 'status': 'submitted'}
        self._setup_query_mock(mock_session, [mock_ncr])

        result = service.get_ncrs(status='submitted', severity='critical')

        assert len(result) == 1
        assert result[0]['severity'] == 'critical'

    def test_get_ncrs_with_limit(self, service, mock_session):
        mock_query = self._setup_query_mock(mock_session, [])

        service.get_ncrs(limit=50)

        mock_query.limit.assert_called_with(50)

    def test_get_ncrs_empty_result(self, service, mock_session):
        self._setup_query_mock(mock_session, [])

        result = service.get_ncrs()

        assert len(result) == 0
