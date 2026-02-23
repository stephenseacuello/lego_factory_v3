"""
Unit Tests for QMS and Compliance Services.

Tests Document Control, CAPA, Deviation Management, Batch Records, and Training Services.
"""

import pytest
from datetime import datetime, timedelta
import asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.services.compliance.qms.document_control import (
    DocumentControlService, DocumentType, DocumentStatus, ChangeType,
    create_document_control_service
)
from dashboard.services.compliance.qms.capa_service import (
    CAPAService, CAPAType, CAPAStatus, CAPAPriority, RootCauseMethod,
    create_capa_service
)
from dashboard.services.compliance.qms.deviation_service import (
    DeviationService, DeviationType, DeviationSeverity, DeviationStatus,
    create_deviation_service
)
from dashboard.services.compliance.qms.batch_record import (
    BatchRecordService, BatchStatus, StepStatus, ParameterType,
    create_batch_record_service
)
from dashboard.services.compliance.qms.training_service import (
    TrainingManagementService, CourseType, TrainingStatus, CompetencyLevel,
    AssessmentType, create_training_service
)


class TestDocumentControlService:
    """Tests for Document Control (ISO 9001 / 21 CFR Part 11)."""

    @pytest.fixture
    def doc_service(self):
        """Create document control service instance."""
        return create_document_control_service()

    @pytest.mark.asyncio
    async def test_create_document(self, doc_service):
        """Test creating a controlled document."""
        doc = await doc_service.create_document(
            document_number="SOP-001",
            title="Standard Operating Procedure - Assembly",
            document_type=DocumentType.SOP,
            department="Manufacturing",
            author="quality_engineer",
            content="This SOP describes the assembly process..."
        )

        assert doc.document_number == "SOP-001"
        assert doc.document_type == DocumentType.SOP
        assert doc.status == DocumentStatus.DRAFT
        assert doc.version == "1.0"

    @pytest.mark.asyncio
    async def test_submit_for_review(self, doc_service):
        """Test submitting document for review."""
        doc = await doc_service.create_document(
            "SOP-002", "Test SOP", DocumentType.SOP,
            "QA", "author1", "Content here"
        )

        submitted = await doc_service.submit_for_review(
            document_id=doc.document_id,
            reviewers=["reviewer1", "reviewer2"],
            due_date=datetime.now() + timedelta(days=7)
        )

        assert submitted.status == DocumentStatus.UNDER_REVIEW
        assert len(submitted.pending_reviewers) == 2

    @pytest.mark.asyncio
    async def test_approve_document(self, doc_service):
        """Test document approval workflow."""
        doc = await doc_service.create_document(
            "SOP-003", "Approval Test", DocumentType.WORK_INSTRUCTION,
            "Production", "author2", "Work instruction content"
        )
        await doc_service.submit_for_review(doc.document_id, ["approver1"])

        # Reviewer approves
        await doc_service.record_review(
            document_id=doc.document_id,
            reviewer="approver1",
            approved=True,
            comments="Looks good"
        )

        # Final approval
        approved = await doc_service.approve_document(
            document_id=doc.document_id,
            approver="quality_manager",
            effective_date=datetime.now() + timedelta(days=1)
        )

        assert approved.status == DocumentStatus.APPROVED

    @pytest.mark.asyncio
    async def test_make_effective(self, doc_service):
        """Test making document effective."""
        doc = await doc_service.create_document(
            "SOP-004", "Effective Test", DocumentType.SOP,
            "QA", "author3", "Content"
        )
        await doc_service.submit_for_review(doc.document_id, ["reviewer"])
        await doc_service.record_review(doc.document_id, "reviewer", True)
        await doc_service.approve_document(
            doc.document_id, "approver",
            effective_date=datetime.now()
        )

        effective = await doc_service.make_effective(doc.document_id)

        assert effective.status == DocumentStatus.EFFECTIVE
        assert effective.effective_date is not None

    @pytest.mark.asyncio
    async def test_create_revision(self, doc_service):
        """Test creating document revision."""
        # Create and make effective
        doc = await doc_service.create_document(
            "SOP-005", "Revision Test", DocumentType.SPECIFICATION,
            "Engineering", "author4", "Original content"
        )
        await doc_service.submit_for_review(doc.document_id, ["rev"])
        await doc_service.record_review(doc.document_id, "rev", True)
        await doc_service.approve_document(doc.document_id, "app", datetime.now())
        await doc_service.make_effective(doc.document_id)

        # Create revision
        revision = await doc_service.create_revision(
            document_id=doc.document_id,
            change_type=ChangeType.MAJOR,
            change_reason="Process improvement",
            revised_by="engineer1",
            new_content="Updated content with improvements"
        )

        assert revision.version == "2.0"  # Major revision
        assert revision.status == DocumentStatus.DRAFT

    @pytest.mark.asyncio
    async def test_obsolete_document(self, doc_service):
        """Test obsoleting a document."""
        doc = await doc_service.create_document(
            "SOP-006", "Obsolete Test", DocumentType.FORM,
            "Admin", "author5", "Form template"
        )
        # Fast track to effective
        await doc_service.submit_for_review(doc.document_id, ["r"])
        await doc_service.record_review(doc.document_id, "r", True)
        await doc_service.approve_document(doc.document_id, "a", datetime.now())
        await doc_service.make_effective(doc.document_id)

        obsoleted = await doc_service.obsolete_document(
            document_id=doc.document_id,
            reason="Replaced by SOP-007",
            obsoleted_by="doc_controller"
        )

        assert obsoleted.status == DocumentStatus.OBSOLETE

    @pytest.mark.asyncio
    async def test_electronic_signature(self, doc_service):
        """Test 21 CFR Part 11 electronic signature."""
        doc = await doc_service.create_document(
            "SOP-007", "E-Sig Test", DocumentType.SOP,
            "QA", "author6", "Content requiring signature"
        )

        signature = await doc_service.apply_electronic_signature(
            document_id=doc.document_id,
            user_id="signer1",
            signature_meaning="Author",
            credentials={"password": "secure_password"}
        )

        assert signature is not None
        assert signature.user_id == "signer1"
        assert signature.timestamp is not None
        assert signature.is_valid


class TestCAPAService:
    """Tests for Corrective and Preventive Action (CAPA)."""

    @pytest.fixture
    def capa_service(self):
        """Create CAPA service instance."""
        return create_capa_service()

    @pytest.mark.asyncio
    async def test_initiate_capa(self, capa_service):
        """Test initiating a CAPA."""
        capa = await capa_service.initiate_capa(
            title="Quality Issue - Assembly Defects",
            capa_type=CAPAType.CORRECTIVE,
            priority=CAPAPriority.HIGH,
            source="Customer Complaint",
            description="Increased defect rate in assembly line 3",
            affected_products=["PROD-001", "PROD-002"],
            initiated_by="quality_engineer"
        )

        assert capa.capa_number is not None
        assert capa.capa_type == CAPAType.CORRECTIVE
        assert capa.status == CAPAStatus.INITIATED
        assert capa.priority == CAPAPriority.HIGH

    @pytest.mark.asyncio
    async def test_conduct_investigation(self, capa_service):
        """Test conducting CAPA investigation."""
        capa = await capa_service.initiate_capa(
            "Investigation Test", CAPAType.CORRECTIVE, CAPAPriority.MEDIUM,
            "Internal Audit", "Test issue", ["PROD-003"], "engineer1"
        )

        investigation = await capa_service.conduct_investigation(
            capa_id=capa.capa_id,
            investigator="senior_engineer",
            findings="Tool calibration drift detected",
            evidence=["Calibration records", "SPC charts", "Operator interviews"]
        )

        assert investigation is not None
        assert capa.status == CAPAStatus.INVESTIGATION

    @pytest.mark.asyncio
    async def test_root_cause_analysis(self, capa_service):
        """Test performing root cause analysis."""
        capa = await capa_service.initiate_capa(
            "RCA Test", CAPAType.CORRECTIVE, CAPAPriority.HIGH,
            "Production Issue", "Root cause needed", [], "qa1"
        )
        await capa_service.conduct_investigation(
            capa.capa_id, "investigator", "Initial findings"
        )

        rca = await capa_service.perform_root_cause_analysis(
            capa_id=capa.capa_id,
            method=RootCauseMethod.FIVE_WHY,
            analysis_data={
                "why_1": "Parts were defective",
                "why_2": "Supplier quality issue",
                "why_3": "No incoming inspection",
                "why_4": "Inspection procedure not defined",
                "why_5": "Process not designed during supplier qualification"
            },
            root_cause="Missing incoming inspection procedure",
            performed_by="rca_specialist"
        )

        assert rca is not None
        assert rca.method == RootCauseMethod.FIVE_WHY
        assert rca.root_cause == "Missing incoming inspection procedure"

    @pytest.mark.asyncio
    async def test_define_actions(self, capa_service):
        """Test defining corrective/preventive actions."""
        capa = await capa_service.initiate_capa(
            "Action Test", CAPAType.PREVENTIVE, CAPAPriority.MEDIUM,
            "Risk Assessment", "Prevent potential issue", [], "qa2"
        )

        actions = await capa_service.define_actions(
            capa_id=capa.capa_id,
            actions=[
                {
                    "description": "Create incoming inspection procedure",
                    "owner": "qa_manager",
                    "due_date": datetime.now() + timedelta(days=14),
                    "action_type": "corrective"
                },
                {
                    "description": "Train inspectors on new procedure",
                    "owner": "training_coordinator",
                    "due_date": datetime.now() + timedelta(days=21),
                    "action_type": "corrective"
                },
                {
                    "description": "Update supplier qualification process",
                    "owner": "supplier_quality",
                    "due_date": datetime.now() + timedelta(days=30),
                    "action_type": "preventive"
                }
            ]
        )

        assert len(actions) == 3
        assert capa.status == CAPAStatus.ACTION_PLANNING

    @pytest.mark.asyncio
    async def test_implement_and_verify(self, capa_service):
        """Test implementing and verifying actions."""
        capa = await capa_service.initiate_capa(
            "Verify Test", CAPAType.CORRECTIVE, CAPAPriority.LOW,
            "Internal", "Test", [], "qa3"
        )
        await capa_service.define_actions(capa.capa_id, [
            {"description": "Fix issue", "owner": "tech", "due_date": datetime.now() + timedelta(days=7)}
        ])

        # Implement action
        implemented = await capa_service.implement_action(
            capa_id=capa.capa_id,
            action_index=0,
            implementation_notes="Procedure created and published",
            evidence=["SOP-NEW-001"]
        )

        assert implemented is True

        # Verify effectiveness
        verification = await capa_service.verify_effectiveness(
            capa_id=capa.capa_id,
            verifier="qa_manager",
            verification_method="Audit and data review",
            results="Defect rate reduced by 95%",
            effective=True
        )

        assert verification.effective is True
        assert capa.status == CAPAStatus.VERIFICATION

    @pytest.mark.asyncio
    async def test_close_capa(self, capa_service):
        """Test closing a CAPA."""
        capa = await capa_service.initiate_capa(
            "Close Test", CAPAType.CORRECTIVE, CAPAPriority.MEDIUM,
            "Test", "Closing test", [], "qa4"
        )
        # Fast track through workflow
        await capa_service.define_actions(capa.capa_id, [
            {"description": "Action", "owner": "owner", "due_date": datetime.now()}
        ])
        await capa_service.implement_action(capa.capa_id, 0, "Done", [])
        await capa_service.verify_effectiveness(
            capa.capa_id, "verifier", "Method", "Effective", True
        )

        closed = await capa_service.close_capa(
            capa_id=capa.capa_id,
            closed_by="quality_director",
            closure_summary="All actions completed and verified effective"
        )

        assert closed.status == CAPAStatus.CLOSED
        assert closed.closure_date is not None


class TestDeviationService:
    """Tests for Deviation/Non-Conformance Management."""

    @pytest.fixture
    def deviation_service(self):
        """Create deviation service instance."""
        return create_deviation_service()

    @pytest.mark.asyncio
    async def test_report_deviation(self, deviation_service):
        """Test reporting a deviation."""
        deviation = await deviation_service.report_deviation(
            title="Out of Specification Temperature",
            deviation_type=DeviationType.PROCESS,
            severity=DeviationSeverity.MAJOR,
            description="Molding temperature exceeded upper limit by 5°C",
            area="Injection Molding",
            detected_by="operator_123",
            affected_batch="BATCH-2024-001"
        )

        assert deviation.deviation_number is not None
        assert deviation.severity == DeviationSeverity.MAJOR
        assert deviation.status == DeviationStatus.REPORTED

    @pytest.mark.asyncio
    async def test_assess_impact(self, deviation_service):
        """Test assessing deviation impact."""
        deviation = await deviation_service.report_deviation(
            "Impact Test", DeviationType.PRODUCT, DeviationSeverity.MINOR,
            "Visual defect detected", "Assembly", "inspector_1", "BATCH-002"
        )

        assessment = await deviation_service.assess_impact(
            deviation_id=deviation.deviation_id,
            assessor="quality_engineer",
            product_impact="Cosmetic only, no functional impact",
            safety_impact="None",
            regulatory_impact="None",
            affected_quantity=150,
            containment_required=True
        )

        assert assessment is not None
        assert deviation.status == DeviationStatus.UNDER_INVESTIGATION

    @pytest.mark.asyncio
    async def test_containment_actions(self, deviation_service):
        """Test implementing containment actions."""
        deviation = await deviation_service.report_deviation(
            "Containment Test", DeviationType.MATERIAL, DeviationSeverity.CRITICAL,
            "Contaminated raw material", "Warehouse", "qa_inspector", "BATCH-003"
        )

        containment = await deviation_service.implement_containment(
            deviation_id=deviation.deviation_id,
            actions=[
                {"action": "Quarantine affected material", "responsible": "warehouse_mgr"},
                {"action": "Stop production using this lot", "responsible": "production_mgr"},
                {"action": "Notify supplier", "responsible": "purchasing"}
            ],
            implemented_by="quality_supervisor"
        )

        assert containment is not None
        assert len(containment.actions) == 3

    @pytest.mark.asyncio
    async def test_disposition_decision(self, deviation_service):
        """Test making disposition decision."""
        deviation = await deviation_service.report_deviation(
            "Disposition Test", DeviationType.PRODUCT, DeviationSeverity.MAJOR,
            "Dimension out of tolerance", "Machining", "inspector_2", "BATCH-004"
        )
        await deviation_service.assess_impact(
            deviation.deviation_id, "qa_eng", "Functional impact", "None", "None", 500, True
        )

        disposition = await deviation_service.make_disposition(
            deviation_id=deviation.deviation_id,
            disposition="USE_AS_IS",
            justification="Engineering review confirms dimensions within acceptable range for non-critical application",
            approved_by="engineering_manager",
            conditions=["Limited to non-precision applications"]
        )

        assert disposition.disposition == "USE_AS_IS"
        assert deviation.status == DeviationStatus.DISPOSITION_MADE

    @pytest.mark.asyncio
    async def test_capa_linkage(self, deviation_service):
        """Test linking deviation to CAPA."""
        deviation = await deviation_service.report_deviation(
            "CAPA Link Test", DeviationType.PROCESS, DeviationSeverity.MAJOR,
            "Recurring issue requiring systemic fix", "Assembly", "qa3", "BATCH-005"
        )

        linked = await deviation_service.link_to_capa(
            deviation_id=deviation.deviation_id,
            capa_id="CAPA-2024-001",
            linked_by="quality_manager"
        )

        assert linked is True
        assert deviation.linked_capa == "CAPA-2024-001"

    @pytest.mark.asyncio
    async def test_close_deviation(self, deviation_service):
        """Test closing a deviation."""
        deviation = await deviation_service.report_deviation(
            "Close Test", DeviationType.DOCUMENTATION, DeviationSeverity.MINOR,
            "Wrong revision used", "Production", "supervisor", "BATCH-006"
        )
        await deviation_service.assess_impact(
            deviation.deviation_id, "qa", "None", "None", "None", 0, False
        )
        await deviation_service.make_disposition(
            deviation.deviation_id, "ACCEPT", "No impact", "qa_mgr"
        )

        closed = await deviation_service.close_deviation(
            deviation_id=deviation.deviation_id,
            closed_by="quality_manager",
            closure_notes="Deviation resolved, no product impact"
        )

        assert closed.status == DeviationStatus.CLOSED


class TestBatchRecordService:
    """Tests for Electronic Batch Records (21 CFR Part 211)."""

    @pytest.fixture
    def batch_service(self):
        """Create batch record service instance."""
        return create_batch_record_service()

    @pytest.mark.asyncio
    async def test_create_master_batch_record(self, batch_service):
        """Test creating a Master Batch Record."""
        mbr = await batch_service.create_master_batch_record(
            product_id="LEGO-SET-42100",
            product_name="LEGO Technic Liebherr",
            version="1.0",
            batch_size=1000,
            unit_of_measure="sets",
            steps=[
                {
                    "step_number": 1,
                    "description": "Verify incoming materials",
                    "critical": True,
                    "parameters": [
                        {"name": "Material lot number", "type": "text", "required": True}
                    ]
                },
                {
                    "step_number": 2,
                    "description": "Set up injection molding machine",
                    "critical": True,
                    "parameters": [
                        {"name": "Temperature", "type": "numeric", "min": 180, "max": 220, "unit": "°C"},
                        {"name": "Pressure", "type": "numeric", "min": 50, "max": 80, "unit": "bar"}
                    ]
                }
            ],
            created_by="process_engineer"
        )

        assert mbr.product_id == "LEGO-SET-42100"
        assert len(mbr.steps) == 2
        assert mbr.version == "1.0"

    @pytest.mark.asyncio
    async def test_initiate_batch(self, batch_service):
        """Test initiating an Electronic Batch Record."""
        await batch_service.create_master_batch_record(
            "PROD-EBR", "Test Product", "1.0", 500, "units",
            steps=[{"step_number": 1, "description": "Step 1"}],
            created_by="engineer"
        )

        ebr = await batch_service.initiate_batch(
            mbr_id="PROD-EBR",
            batch_number="BATCH-2024-100",
            planned_quantity=500,
            initiated_by="production_supervisor",
            equipment=["MOLD-001", "ASSEMBLY-LINE-1"]
        )

        assert ebr.batch_number == "BATCH-2024-100"
        assert ebr.status == BatchStatus.IN_PROGRESS
        assert ebr.start_time is not None

    @pytest.mark.asyncio
    async def test_record_parameter(self, batch_service):
        """Test recording a process parameter."""
        await batch_service.create_master_batch_record(
            "PROD-PARAM", "Param Test", "1.0", 100, "units",
            steps=[{
                "step_number": 1,
                "description": "Process step",
                "parameters": [
                    {"name": "Temperature", "type": "numeric", "min": 20, "max": 25}
                ]
            }],
            created_by="eng"
        )
        ebr = await batch_service.initiate_batch(
            "PROD-PARAM", "BATCH-PARAM-001", 100, "supervisor"
        )

        recorded = await batch_service.record_parameter(
            batch_id=ebr.batch_id,
            step_number=1,
            parameter_name="Temperature",
            value=22.5,
            recorded_by="operator_1",
            equipment_id="SENSOR-001"
        )

        assert recorded is True

    @pytest.mark.asyncio
    async def test_record_deviation_in_batch(self, batch_service):
        """Test recording a deviation in batch record."""
        await batch_service.create_master_batch_record(
            "PROD-DEV", "Dev Test", "1.0", 200, "units",
            steps=[{"step_number": 1, "description": "Critical step", "critical": True}],
            created_by="eng"
        )
        ebr = await batch_service.initiate_batch(
            "PROD-DEV", "BATCH-DEV-001", 200, "super"
        )

        deviation = await batch_service.record_batch_deviation(
            batch_id=ebr.batch_id,
            step_number=1,
            description="Temperature excursion detected",
            severity="MAJOR",
            reported_by="operator_2",
            immediate_action="Stopped process and notified QA"
        )

        assert deviation is not None
        assert deviation.severity == "MAJOR"

    @pytest.mark.asyncio
    async def test_complete_step(self, batch_service):
        """Test completing a batch step."""
        await batch_service.create_master_batch_record(
            "PROD-STEP", "Step Test", "1.0", 50, "units",
            steps=[
                {"step_number": 1, "description": "First step"},
                {"step_number": 2, "description": "Second step"}
            ],
            created_by="eng"
        )
        ebr = await batch_service.initiate_batch(
            "PROD-STEP", "BATCH-STEP-001", 50, "super"
        )

        completed = await batch_service.complete_step(
            batch_id=ebr.batch_id,
            step_number=1,
            completed_by="operator_3",
            verified_by="qa_inspector",
            notes="Step completed successfully"
        )

        assert completed.status == StepStatus.COMPLETED
        assert completed.verified_by == "qa_inspector"

    @pytest.mark.asyncio
    async def test_calculate_yield(self, batch_service):
        """Test calculating batch yield."""
        await batch_service.create_master_batch_record(
            "PROD-YIELD", "Yield Test", "1.0", 1000, "units",
            steps=[{"step_number": 1, "description": "Production"}],
            created_by="eng"
        )
        ebr = await batch_service.initiate_batch(
            "PROD-YIELD", "BATCH-YIELD-001", 1000, "super"
        )

        yield_data = await batch_service.calculate_yield(
            batch_id=ebr.batch_id,
            actual_output=950,
            reject_quantity=30,
            rework_quantity=20
        )

        assert yield_data["theoretical_yield"] == 1000
        assert yield_data["actual_yield"] == 950
        assert yield_data["yield_percentage"] == 95.0
        assert yield_data["reject_percentage"] == 3.0

    @pytest.mark.asyncio
    async def test_release_batch(self, batch_service):
        """Test batch release/rejection."""
        await batch_service.create_master_batch_record(
            "PROD-REL", "Release Test", "1.0", 100, "units",
            steps=[{"step_number": 1, "description": "Final"}],
            created_by="eng"
        )
        ebr = await batch_service.initiate_batch(
            "PROD-REL", "BATCH-REL-001", 100, "super"
        )
        await batch_service.complete_step(ebr.batch_id, 1, "op", "qa")
        await batch_service.calculate_yield(ebr.batch_id, 98, 2, 0)

        released = await batch_service.release_batch(
            batch_id=ebr.batch_id,
            decision="RELEASE",
            released_by="qa_manager",
            comments="All parameters within specification"
        )

        assert released.status == BatchStatus.RELEASED
        assert released.release_date is not None


class TestTrainingService:
    """Tests for Training Management (21 CFR Part 211.25)."""

    @pytest.fixture
    def training_service(self):
        """Create training service instance."""
        return create_training_service()

    @pytest.mark.asyncio
    async def test_create_course(self, training_service):
        """Test creating a training course."""
        course = await training_service.create_course(
            course_id="TRN-GMP-001",
            title="Good Manufacturing Practices",
            course_type=CourseType.REGULATORY,
            description="Introduction to GMP requirements",
            duration_hours=4,
            passing_score=80,
            validity_months=12,
            prerequisites=[],
            created_by="training_coordinator"
        )

        assert course.course_id == "TRN-GMP-001"
        assert course.course_type == CourseType.REGULATORY
        assert course.passing_score == 80

    @pytest.mark.asyncio
    async def test_assign_training(self, training_service):
        """Test assigning training to employee."""
        await training_service.create_course(
            "TRN-ASSIGN", "Assignment Test", CourseType.JOB_SPECIFIC,
            "Test course", 2, 70, 24, [], "coordinator"
        )

        assignment = await training_service.assign_training(
            course_id="TRN-ASSIGN",
            employee_id="EMP-001",
            assigned_by="supervisor",
            due_date=datetime.now() + timedelta(days=30),
            priority="HIGH"
        )

        assert assignment.employee_id == "EMP-001"
        assert assignment.status == TrainingStatus.ASSIGNED

    @pytest.mark.asyncio
    async def test_record_completion(self, training_service):
        """Test recording training completion."""
        await training_service.create_course(
            "TRN-COMP", "Completion Test", CourseType.SAFETY,
            "Safety training", 1, 100, 12, [], "coord"
        )
        await training_service.assign_training(
            "TRN-COMP", "EMP-002", "mgr", datetime.now() + timedelta(days=7)
        )

        completion = await training_service.record_completion(
            course_id="TRN-COMP",
            employee_id="EMP-002",
            completion_date=datetime.now(),
            trainer="certified_trainer",
            training_method="classroom"
        )

        assert completion.status == TrainingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_record_assessment(self, training_service):
        """Test recording training assessment."""
        await training_service.create_course(
            "TRN-ASSESS", "Assessment Test", CourseType.TECHNICAL,
            "Technical skills", 8, 75, 24, [], "coord"
        )
        await training_service.assign_training(
            "TRN-ASSESS", "EMP-003", "mgr", datetime.now() + timedelta(days=14)
        )
        await training_service.record_completion(
            "TRN-ASSESS", "EMP-003", datetime.now(), "trainer", "online"
        )

        assessment = await training_service.record_assessment(
            course_id="TRN-ASSESS",
            employee_id="EMP-003",
            assessment_type=AssessmentType.WRITTEN_TEST,
            score=85,
            passed=True,
            assessed_by="examiner"
        )

        assert assessment.score == 85
        assert assessment.passed is True
        assert assessment.status == TrainingStatus.PASSED

    @pytest.mark.asyncio
    async def test_competency_evaluation(self, training_service):
        """Test evaluating employee competency."""
        await training_service.create_course(
            "TRN-COMP-EVAL", "Competency Eval", CourseType.JOB_SPECIFIC,
            "Job skills", 4, 80, 12, [], "coord"
        )
        await training_service.assign_training(
            "TRN-COMP-EVAL", "EMP-004", "mgr", datetime.now() + timedelta(days=7)
        )
        await training_service.record_completion(
            "TRN-COMP-EVAL", "EMP-004", datetime.now(), "trainer", "hands_on"
        )
        await training_service.record_assessment(
            "TRN-COMP-EVAL", "EMP-004", AssessmentType.PRACTICAL,
            90, True, "evaluator"
        )

        competency = await training_service.evaluate_competency(
            employee_id="EMP-004",
            skill_area="Injection Molding",
            competency_level=CompetencyLevel.PROFICIENT,
            evaluator="senior_engineer",
            evidence=["TRN-COMP-EVAL completed", "6 months experience"]
        )

        assert competency.competency_level == CompetencyLevel.PROFICIENT

    @pytest.mark.asyncio
    async def test_generate_training_matrix(self, training_service):
        """Test generating training matrix."""
        # Create courses
        await training_service.create_course(
            "TRN-M1", "Matrix Course 1", CourseType.REGULATORY,
            "Course 1", 2, 80, 12, [], "coord"
        )
        await training_service.create_course(
            "TRN-M2", "Matrix Course 2", CourseType.SAFETY,
            "Course 2", 1, 100, 6, [], "coord"
        )

        # Assign and complete for employees
        for emp_id in ["EMP-M1", "EMP-M2", "EMP-M3"]:
            await training_service.assign_training(
                "TRN-M1", emp_id, "mgr", datetime.now() + timedelta(days=30)
            )

        matrix = await training_service.generate_training_matrix(
            department="Manufacturing"
        )

        assert "courses" in matrix
        assert "employees" in matrix
        assert "compliance_rate" in matrix

    @pytest.mark.asyncio
    async def test_expiring_training_report(self, training_service):
        """Test getting expiring training report."""
        await training_service.create_course(
            "TRN-EXP", "Expiring Test", CourseType.REGULATORY,
            "Expires soon", 2, 80, 1, [], "coord"  # 1 month validity
        )

        report = await training_service.get_expiring_training(
            days_ahead=60,
            department="All"
        )

        assert "expiring_soon" in report
        assert "expired" in report


class TestQMSIntegration:
    """Integration tests for QMS scenarios."""

    @pytest.mark.asyncio
    async def test_deviation_to_capa_workflow(self):
        """Test deviation triggering CAPA workflow."""
        deviation_svc = create_deviation_service()
        capa_svc = create_capa_service()

        # Report significant deviation
        deviation = await deviation_svc.report_deviation(
            "Recurring Quality Issue",
            DeviationType.PRODUCT,
            DeviationSeverity.CRITICAL,
            "Third occurrence of same defect type",
            "Assembly",
            "qa_inspector",
            "BATCH-RECURRING"
        )

        # Assess and determine CAPA needed
        await deviation_svc.assess_impact(
            deviation.deviation_id, "qa_eng",
            "Significant - affects product function",
            "None", "Regulatory reporting may be required",
            1500, True
        )

        # Initiate CAPA
        capa = await capa_svc.initiate_capa(
            f"CAPA for {deviation.deviation_number}",
            CAPAType.CORRECTIVE,
            CAPAPriority.CRITICAL,
            f"Deviation {deviation.deviation_number}",
            "Recurring defect requires root cause analysis",
            [deviation.affected_batch],
            "quality_manager"
        )

        # Link deviation to CAPA
        await deviation_svc.link_to_capa(
            deviation.deviation_id, capa.capa_id, "qa_manager"
        )

        assert deviation.linked_capa == capa.capa_id

    @pytest.mark.asyncio
    async def test_batch_deviation_to_document_update(self):
        """Test batch deviation triggering document update."""
        batch_svc = create_batch_record_service()
        doc_svc = create_document_control_service()

        # Create MBR and batch
        await batch_svc.create_master_batch_record(
            "PROD-DOC-INT", "Doc Integration", "1.0", 100, "units",
            steps=[{"step_number": 1, "description": "Process", "critical": True}],
            created_by="eng"
        )
        ebr = await batch_svc.initiate_batch(
            "PROD-DOC-INT", "BATCH-DOC-001", 100, "super"
        )

        # Record deviation indicating procedure issue
        await batch_svc.record_batch_deviation(
            ebr.batch_id, 1,
            "Procedure unclear - operators confused on parameter limits",
            "MINOR", "operator", "Clarified with supervisor"
        )

        # Create document revision request
        doc = await doc_svc.create_document(
            "SOP-PROC-001", "Process Procedure", DocumentType.SOP,
            "Production", "engineer", "Original procedure"
        )

        # Procedure needs revision based on batch deviation
        await doc_svc.submit_for_review(doc.document_id, ["reviewer"])
        await doc_svc.record_review(doc.document_id, "reviewer", True)
        await doc_svc.approve_document(doc.document_id, "approver", datetime.now())
        await doc_svc.make_effective(doc.document_id)

        revision = await doc_svc.create_revision(
            doc.document_id,
            ChangeType.MINOR,
            f"Clarify parameter limits per batch deviation BATCH-DOC-001",
            "process_engineer",
            "Updated procedure with clearer parameter specifications"
        )

        assert revision.version == "1.1"

    @pytest.mark.asyncio
    async def test_training_for_document_change(self):
        """Test training requirements for document changes."""
        doc_svc = create_document_control_service()
        training_svc = create_training_service()

        # Create and revise document
        doc = await doc_svc.create_document(
            "SOP-TRN-REQ", "Training Required SOP", DocumentType.SOP,
            "Quality", "author", "Original content"
        )

        # Create training course for this SOP
        course = await training_svc.create_course(
            "TRN-SOP-REQ", "SOP Training", CourseType.JOB_SPECIFIC,
            f"Training for {doc.document_number}", 1, 80, 24,
            [], "training_coord"
        )

        # Assign training to affected employees
        affected_employees = ["EMP-A", "EMP-B", "EMP-C"]
        for emp_id in affected_employees:
            await training_svc.assign_training(
                course.course_id, emp_id, "supervisor",
                datetime.now() + timedelta(days=14)
            )

        # Verify all employees assigned
        matrix = await training_svc.generate_training_matrix("Quality")
        assert matrix is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
