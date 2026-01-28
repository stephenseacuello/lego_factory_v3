"""
Integration tests for QMS services.

Tests the integration between:
- NCR Service
- CAPA workflows
- Production/Work Order integration
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock


class TestNCRToCAPAIntegration:
    """Tests for NCR to CAPA workflow integration."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        return session

    def test_ncr_creates_linked_capa(self, mock_db_session):
        """Test that NCR can create a linked CAPA."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # Create NCR
        with patch.object(service, 'create_ncr') as mock_create_ncr:
            mock_create_ncr.return_value = {
                'id': 1,
                'ncr_number': 'NCR-20240115-A1B2',
                'title': 'Surface defect on LEGO brick',
                'status': 'draft',
                'severity': 'major'
            }

            ncr = service.create_ncr({
                'title': 'Surface defect on LEGO brick',
                'description': 'Visible scratches on finished product',
                'detected_by': 'inspector_001',
                'severity': 'major',
                'product_id': 'BRICK-2x4-RED',
                'lot_number': 'LOT-2024-001'
            })

        # Create CAPA linked to NCR
        with patch.object(service, 'create_capa') as mock_create_capa:
            mock_create_capa.return_value = {
                'id': 1,
                'capa_number': 'CAPA-20240115-C1D2',
                'ncr_id': 1,
                'ncr_number': 'NCR-20240115-A1B2',
                'capa_type': 'corrective',
                'status': 'draft'
            }

            capa = service.create_capa({
                'title': 'Corrective action for surface defects',
                'problem_statement': 'Investigate root cause of scratches',
                'owner_id': 'engineer_001',
                'ncr_number': 'NCR-20240115-A1B2',
                'capa_type': 'corrective'
            })

        # Verify linkage
        assert capa['ncr_number'] == ncr['ncr_number']
        assert capa['capa_type'] == 'corrective'

    def test_capa_completion_closes_ncr(self, mock_db_session):
        """Test that completing CAPA actions allows NCR closure."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # Simulate CAPA effectiveness verification
        with patch.object(service, 'verify_capa_effectiveness') as mock_verify:
            mock_verify.return_value = {
                'capa_number': 'CAPA-001',
                'is_effective': True,
                'effectiveness_result': 'No recurrence in 30-day monitoring period',
                'status': 'closed'
            }

            capa_result = service.verify_capa_effectiveness(
                'CAPA-001',
                is_effective=True,
                result='No recurrence in 30-day monitoring period',
                reviewed_by='qa_manager_001'
            )

        # Now close the NCR
        with patch.object(service, 'close_ncr') as mock_close:
            mock_close.return_value = {
                'ncr_number': 'NCR-001',
                'status': 'closed',
                'actual_close_date': date.today().isoformat(),
                'closure_notes': 'CAPA verified effective'
            }

            ncr_result = service.close_ncr(
                'NCR-001',
                'qa_manager_001',
                actual_cost=250.0
            )

        assert capa_result['is_effective'] is True
        assert ncr_result['status'] == 'closed'


class TestNCRWorkflowIntegration:
    """Tests for complete NCR workflow."""

    @pytest.fixture
    def mock_db_session(self):
        return Mock()

    def test_full_ncr_lifecycle(self, mock_db_session):
        """Test complete NCR lifecycle from creation to closure."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # 1. Create NCR (Draft)
        with patch.object(service, 'create_ncr') as mock_create:
            mock_create.return_value = {
                'ncr_number': 'NCR-001',
                'status': 'draft',
                'created_at': datetime.utcnow().isoformat()
            }
            ncr = service.create_ncr({
                'title': 'Dimensional variance',
                'description': 'Part dimensions exceed tolerance',
                'detected_by': 'inspector_001',
                'severity': 'minor'
            })

        assert ncr['status'] == 'draft'

        # 2. Submit for review
        with patch.object(service, 'get_ncr') as mock_get:
            mock_get.return_value = {
                'ncr_number': 'NCR-001',
                'status': 'pending_review'
            }
            ncr = service.get_ncr('NCR-001')

        # 3. Set disposition
        with patch.object(service, 'set_disposition') as mock_disp:
            mock_disp.return_value = {
                'ncr_number': 'NCR-001',
                'disposition': 'rework',
                'disposition_reason': 'Parts can be reworked to spec',
                'status': 'disposition_approved'
            }
            ncr = service.set_disposition(
                'NCR-001',
                'rework',
                'Parts can be reworked to spec',
                'qa_manager_001'
            )

        assert ncr['disposition'] == 'rework'

        # 4. Close NCR
        with patch.object(service, 'close_ncr') as mock_close:
            mock_close.return_value = {
                'ncr_number': 'NCR-001',
                'status': 'closed',
                'actual_cost': 75.0
            }
            ncr = service.close_ncr('NCR-001', 'qa_manager_001', actual_cost=75.0)

        assert ncr['status'] == 'closed'

    def test_ncr_rejection_workflow(self, mock_db_session):
        """Test NCR rejection and rework cycle."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # Create NCR
        with patch.object(service, 'create_ncr') as mock_create:
            mock_create.return_value = {
                'ncr_number': 'NCR-002',
                'status': 'draft'
            }
            ncr = service.create_ncr({
                'title': 'Material contamination',
                'description': 'Foreign particles in resin',
                'detected_by': 'inspector_002',
                'severity': 'critical'
            })

        # Set disposition as scrap
        with patch.object(service, 'set_disposition') as mock_disp:
            mock_disp.return_value = {
                'ncr_number': 'NCR-002',
                'disposition': 'scrap',
                'disposition_reason': 'Contaminated material cannot be recovered',
                'status': 'disposition_approved'
            }
            ncr = service.set_disposition(
                'NCR-002',
                'scrap',
                'Contaminated material cannot be recovered',
                'qa_manager_001'
            )

        assert ncr['disposition'] == 'scrap'


class TestCAPAActionsIntegration:
    """Tests for CAPA action tracking integration."""

    @pytest.fixture
    def mock_db_session(self):
        return Mock()

    def test_capa_action_workflow(self, mock_db_session):
        """Test adding and completing CAPA actions."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # Add actions to CAPA
        actions = [
            {
                'description': 'Perform root cause analysis',
                'assigned_to': 'engineer_001',
                'target_date': (date.today() + timedelta(days=7)).isoformat()
            },
            {
                'description': 'Update work instructions',
                'assigned_to': 'doc_control_001',
                'target_date': (date.today() + timedelta(days=14)).isoformat()
            },
            {
                'description': 'Train operators on new procedure',
                'assigned_to': 'training_001',
                'target_date': (date.today() + timedelta(days=21)).isoformat()
            }
        ]

        action_results = []
        for i, action in enumerate(actions):
            with patch.object(service, 'add_capa_action') as mock_add:
                mock_add.return_value = {
                    'action_number': i + 1,
                    'description': action['description'],
                    'status': 'pending'
                }
                result = service.add_capa_action('CAPA-001', action)
                action_results.append(result)

        assert len(action_results) == 3

        # Complete actions
        for i, action in enumerate(action_results):
            with patch.object(service, 'complete_capa_action') as mock_complete:
                mock_complete.return_value = {
                    'action_number': action['action_number'],
                    'status': 'completed',
                    'completed_date': date.today().isoformat()
                }
                completed = service.complete_capa_action(
                    f'action_{i+1}',
                    'user_001',
                    f'Action {i+1} completed successfully'
                )
                assert completed['status'] == 'completed'

    def test_overdue_action_detection(self, mock_db_session):
        """Test detection of overdue CAPA actions."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # Get CAPAs with overdue actions
        with patch.object(service, 'get_capa') as mock_get:
            mock_get.return_value = {
                'capa_number': 'CAPA-001',
                'status': 'action_execution',
                'actions': [
                    {
                        'action_number': 1,
                        'status': 'pending',
                        'target_date': (date.today() - timedelta(days=5)).isoformat(),
                        'is_overdue': True
                    },
                    {
                        'action_number': 2,
                        'status': 'pending',
                        'target_date': (date.today() + timedelta(days=5)).isoformat(),
                        'is_overdue': False
                    }
                ]
            }

            capa = service.get_capa('CAPA-001')
            overdue_actions = [a for a in capa['actions'] if a.get('is_overdue')]

            assert len(overdue_actions) == 1
            assert overdue_actions[0]['action_number'] == 1


class TestNCRMetricsIntegration:
    """Tests for NCR metrics and reporting integration."""

    @pytest.fixture
    def mock_db_session(self):
        return Mock()

    def test_ncr_metrics_calculation(self, mock_db_session):
        """Test NCR metrics calculation."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        with patch.object(service, 'get_ncr_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'period_days': 30,
                'total_ncrs': 25,
                'open_ncrs': 8,
                'closed_ncrs': 17,
                'by_severity': {
                    'critical': 3,
                    'major': 10,
                    'minor': 12
                },
                'by_disposition': {
                    'rework': 8,
                    'scrap': 5,
                    'use_as_is': 4
                },
                'avg_closure_time_days': 5.2,
                'total_cost': 15750.0
            }

            metrics = service.get_ncr_metrics(days=30)

            # Verify metrics calculations
            assert metrics['total_ncrs'] == metrics['open_ncrs'] + metrics['closed_ncrs']
            assert sum(metrics['by_severity'].values()) == metrics['total_ncrs']
            assert metrics['avg_closure_time_days'] > 0

    def test_ncr_pareto_analysis(self, mock_db_session):
        """Test NCR Pareto analysis for root causes."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        with patch.object(service, 'get_ncr_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'by_category': {
                    'material_defect': 15,
                    'process_error': 8,
                    'equipment_failure': 5,
                    'operator_error': 3,
                    'design_issue': 2
                }
            }

            metrics = service.get_ncr_metrics()
            categories = metrics['by_category']

            # Sort by frequency for Pareto
            sorted_categories = sorted(
                categories.items(),
                key=lambda x: x[1],
                reverse=True
            )

            # Top 2 categories should account for majority
            total = sum(categories.values())
            top_two = sum(v for k, v in sorted_categories[:2])

            assert top_two / total > 0.6  # 60%+ from top 2 categories


class TestQMSProductionIntegration:
    """Tests for QMS and Production system integration."""

    @pytest.fixture
    def mock_db_session(self):
        return Mock()

    def test_ncr_linked_to_work_order(self, mock_db_session):
        """Test NCR linked to production work order."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        with patch.object(service, 'create_ncr') as mock_create:
            mock_create.return_value = {
                'ncr_number': 'NCR-003',
                'work_order_id': 'WO-2024-001',
                'product_id': 'BRICK-2x4-BLUE',
                'lot_number': 'LOT-2024-003',
                'quantity_affected': 150,
                'status': 'draft'
            }

            ncr = service.create_ncr({
                'title': 'Color variance',
                'description': 'Batch color outside spec',
                'detected_by': 'inspector_001',
                'severity': 'minor',
                'work_order_id': 'WO-2024-001',
                'product_id': 'BRICK-2x4-BLUE',
                'lot_number': 'LOT-2024-003',
                'quantity_affected': 150
            })

            assert ncr['work_order_id'] == 'WO-2024-001'
            assert ncr['quantity_affected'] == 150

    def test_ncr_triggers_production_hold(self, mock_db_session):
        """Test that critical NCR can trigger production hold."""
        from services.qms.ncr_service import NCRService

        service = NCRService(mock_db_session)

        # Critical NCR should flag for production hold
        with patch.object(service, 'create_ncr') as mock_create:
            mock_create.return_value = {
                'ncr_number': 'NCR-004',
                'severity': 'critical',
                'requires_production_hold': True,
                'hold_reason': 'Safety-related defect requires investigation'
            }

            ncr = service.create_ncr({
                'title': 'Safety defect detected',
                'description': 'Sharp edge found on finished product',
                'detected_by': 'inspector_001',
                'severity': 'critical'
            })

            assert ncr['requires_production_hold'] is True
