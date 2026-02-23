"""
Compliance Module Tests.

Tests for Phase 6 ISO 9001/13485 QMS components:
- Document Control
- CAPA Management
- Internal Audit
- Management Review
"""

import unittest
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDocumentControl(unittest.TestCase):
    """Tests for document control system."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.compliance.qms.document_control import (
            DocumentType, DocumentStatus, ApprovalLevel,
            Document, DocumentVersion, DocumentController, ISO9001DocumentControl
        )
        self.DocumentType = DocumentType
        self.DocumentStatus = DocumentStatus
        self.ApprovalLevel = ApprovalLevel
        self.Document = Document
        self.DocumentVersion = DocumentVersion
        self.DocumentController = DocumentController
        self.ISO9001DocumentControl = ISO9001DocumentControl

    def test_document_types(self):
        """Test document type enumeration."""
        types = list(self.DocumentType)

        self.assertIn(self.DocumentType.QUALITY_MANUAL, types)
        self.assertIn(self.DocumentType.PROCEDURE, types)
        self.assertIn(self.DocumentType.FORM, types)
        self.assertIn(self.DocumentType.DESIGN_HISTORY_FILE, types)

    def test_document_status_lifecycle(self):
        """Test document status lifecycle."""
        statuses = list(self.DocumentStatus)

        self.assertIn(self.DocumentStatus.DRAFT, statuses)
        self.assertIn(self.DocumentStatus.IN_REVIEW, statuses)
        self.assertIn(self.DocumentStatus.APPROVED, statuses)
        self.assertIn(self.DocumentStatus.EFFECTIVE, statuses)
        self.assertIn(self.DocumentStatus.OBSOLETE, statuses)

    def test_document_version_creation(self):
        """Test document version creation."""
        version = self.DocumentVersion(
            version_number="1.0",
            major_version=1,
            minor_version=0,
            created_date=datetime.now(),
            created_by="Author",
            change_description="Initial release",
            content_hash="abc123"
        )

        self.assertEqual(version.version_number, "1.0")
        self.assertTrue(version.is_major_change())

    def test_document_controller_creation(self):
        """Test document controller creation."""
        controller = self.DocumentController()

        self.assertIsNotNone(controller)
        self.assertEqual(len(controller.documents), 0)

    def test_create_document(self):
        """Test creating a new document."""
        controller = self.DocumentController()

        doc = controller.create_document(
            title="Quality Manual",
            doc_type=self.DocumentType.QUALITY_MANUAL,
            department="Quality",
            author="John Doe",
            content="This is the quality manual content."
        )

        self.assertIsNotNone(doc.document_id)
        self.assertIn("QM-QUA", doc.document_number)
        self.assertEqual(doc.status, self.DocumentStatus.DRAFT)

    def test_submit_for_review(self):
        """Test submitting document for review."""
        controller = self.DocumentController()

        doc = controller.create_document(
            title="SOP-001",
            doc_type=self.DocumentType.STANDARD_OPERATING_PROCEDURE,
            department="Production",
            author="Jane Doe"
        )

        result = controller.submit_for_review(doc.document_id, "Jane Doe")

        self.assertTrue(result["success"])
        self.assertEqual(doc.status, self.DocumentStatus.IN_REVIEW)

    def test_approve_document(self):
        """Test document approval workflow."""
        controller = self.DocumentController()

        doc = controller.create_document(
            title="Work Instruction",
            doc_type=self.DocumentType.WORK_INSTRUCTION,
            department="Assembly",
            author="Author"
        )

        controller.submit_for_review(doc.document_id, "Author")

        # Approve at each level
        result = controller.approve_document(
            doc.document_id,
            "Reviewer",
            self.ApprovalLevel.AUTHOR,
            True,
            "Approved"
        )

        self.assertTrue(result["success"])

    def test_make_document_effective(self):
        """Test making document effective."""
        controller = self.DocumentController()

        doc = controller.create_document(
            title="Form",
            doc_type=self.DocumentType.FORM,
            department="Quality",
            author="Author"
        )

        controller.submit_for_review(doc.document_id, "Author")

        # Approve all levels
        controller.approve_document(doc.document_id, "Author", self.ApprovalLevel.AUTHOR, True)
        controller.approve_document(doc.document_id, "QA", self.ApprovalLevel.QUALITY_ASSURANCE, True)

        result = controller.make_effective(doc.document_id)

        self.assertTrue(result["success"])
        self.assertEqual(doc.status, self.DocumentStatus.EFFECTIVE)

    def test_document_revision(self):
        """Test document revision."""
        controller = self.DocumentController()

        doc = controller.create_document(
            title="Procedure",
            doc_type=self.DocumentType.PROCEDURE,
            department="Engineering",
            author="Author"
        )

        # Get to effective status first
        controller.submit_for_review(doc.document_id, "Author")
        controller.approve_document(doc.document_id, "A", self.ApprovalLevel.AUTHOR, True)
        controller.approve_document(doc.document_id, "R", self.ApprovalLevel.REVIEWER, True)
        controller.approve_document(doc.document_id, "QA", self.ApprovalLevel.QUALITY_ASSURANCE, True)
        controller.make_effective(doc.document_id)

        # Revise
        result = controller.revise_document(
            doc.document_id,
            "Revisor",
            "Updated content",
            "Updated section 3",
            major_change=False
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["new_version"], "1.1")

    def test_iso9001_compliance_check(self):
        """Test ISO 9001 compliance check."""
        controller = self.ISO9001DocumentControl()

        # Check compliance (should fail with no documents)
        result = controller.check_compliance()

        self.assertIn("compliance_score", result)
        self.assertIn("issues", result)

    def test_document_search(self):
        """Test document search."""
        controller = self.DocumentController()

        # Create multiple documents
        controller.create_document("Quality Manual", self.DocumentType.QUALITY_MANUAL, "QA", "A")
        controller.create_document("SOP for Assembly", self.DocumentType.PROCEDURE, "Prod", "B")
        controller.create_document("Form Template", self.DocumentType.FORM, "QA", "C")

        results = controller.search_documents("SOP")

        self.assertEqual(len(results), 1)
        self.assertIn("Assembly", results[0].title)


class TestCAPAService(unittest.TestCase):
    """Tests for CAPA management service."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.compliance.qms.capa_service import (
            CAPAType, CAPAStatus, CAPAPriority, RootCauseCategory,
            CAPA, RootCauseAnalysis, CAPAService, ISO13485CAPA
        )
        self.CAPAType = CAPAType
        self.CAPAStatus = CAPAStatus
        self.CAPAPriority = CAPAPriority
        self.RootCauseCategory = RootCauseCategory
        self.CAPA = CAPA
        self.RootCauseAnalysis = RootCauseAnalysis
        self.CAPAService = CAPAService
        self.ISO13485CAPA = ISO13485CAPA

    def test_capa_types(self):
        """Test CAPA type enumeration."""
        types = list(self.CAPAType)

        self.assertIn(self.CAPAType.CORRECTIVE, types)
        self.assertIn(self.CAPAType.PREVENTIVE, types)
        self.assertIn(self.CAPAType.COMBINED, types)

    def test_capa_service_creation(self):
        """Test CAPA service creation."""
        service = self.CAPAService()

        self.assertIsNotNone(service)
        self.assertEqual(len(service.capas), 0)

    def test_initiate_capa(self):
        """Test initiating a new CAPA."""
        service = self.CAPAService()

        capa = service.initiate_capa(
            capa_type=self.CAPAType.CORRECTIVE,
            priority=self.CAPAPriority.HIGH,
            source_type="Customer Complaint",
            source_reference="CC-2024-001",
            problem_title="Product defect reported",
            problem_description="Customer reported surface defects on parts",
            initiator="Quality Manager"
        )

        self.assertIsNotNone(capa.capa_id)
        self.assertIn("CAPA-", capa.capa_number)
        self.assertEqual(capa.status, self.CAPAStatus.INITIATED)

    def test_assign_investigation_team(self):
        """Test assigning investigation team."""
        service = self.CAPAService()

        capa = service.initiate_capa(
            capa_type=self.CAPAType.CORRECTIVE,
            priority=self.CAPAPriority.MEDIUM,
            source_type="Audit",
            source_reference="IA-2024-001",
            problem_title="Procedure not followed",
            problem_description="Operators not following work instructions",
            initiator="QA"
        )

        result = service.assign_investigation_team(
            capa.capa_id,
            team_members=["Engineer A", "Engineer B"],
            lead="Senior Engineer"
        )

        self.assertTrue(result["success"])
        self.assertEqual(capa.status, self.CAPAStatus.INVESTIGATION)

    def test_root_cause_analysis(self):
        """Test performing root cause analysis."""
        service = self.CAPAService()

        capa = service.initiate_capa(
            capa_type=self.CAPAType.CORRECTIVE,
            priority=self.CAPAPriority.HIGH,
            source_type="NCR",
            source_reference="NCR-001",
            problem_title="Dimension out of spec",
            problem_description="Part dimensions outside tolerance",
            initiator="QA"
        )

        service.assign_investigation_team(capa.capa_id, ["Engineer"], "Lead")

        rca = service.perform_root_cause_analysis(
            capa.capa_id,
            analyst="Lead Engineer",
            method="5 Whys",
            problem_statement="Part dimension is 2mm over specification",
            immediate_cause="Incorrect machine settings",
            root_cause="No calibration verification procedure",
            category=self.RootCauseCategory.PROCEDURE_COMPLIANCE
        )

        self.assertIsNotNone(rca.analysis_id)
        self.assertEqual(rca.method_used, "5 Whys")

    def test_five_whys_analysis(self):
        """Test 5 Whys analysis method."""
        service = self.CAPAService()

        capa = service.initiate_capa(
            capa_type=self.CAPAType.CORRECTIVE,
            priority=self.CAPAPriority.MEDIUM,
            source_type="Internal",
            source_reference="INT-001",
            problem_title="Equipment failure",
            problem_description="Printer stopped during print",
            initiator="Production"
        )

        whys = [
            ("Why did the printer stop?", "Motor overheated"),
            ("Why did the motor overheat?", "Insufficient cooling"),
            ("Why was cooling insufficient?", "Fan filter clogged"),
            ("Why was filter clogged?", "No maintenance schedule"),
            ("Why no maintenance schedule?", "Procedure not established"),
        ]

        rca = service.generate_five_whys(capa.capa_id, "Engineer", "Printer stopped", whys)

        self.assertEqual(rca.method_used, "5 Whys")
        self.assertEqual(len(rca.analysis_steps), 5)

    def test_plan_actions(self):
        """Test planning corrective and preventive actions."""
        service = self.CAPAService()

        capa = service.initiate_capa(
            capa_type=self.CAPAType.COMBINED,
            priority=self.CAPAPriority.MEDIUM,
            source_type="Trend",
            source_reference="TREND-001",
            problem_title="Recurring defects",
            problem_description="Same defect type appearing frequently",
            initiator="QA"
        )

        result = service.plan_actions(
            capa.capa_id,
            planner="QA Manager",
            corrective_actions=[
                {
                    "description": "Retrain operators",
                    "responsible": "Training Manager",
                    "due_date": (datetime.now() + timedelta(days=14)).isoformat(),
                    "verification_method": "Competency test"
                }
            ],
            preventive_actions=[
                {
                    "description": "Update procedure with visual aids",
                    "responsible": "Process Engineer",
                    "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
                    "verification_method": "Document review"
                }
            ]
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["corrective_count"], 1)
        self.assertEqual(result["preventive_count"], 1)

    def test_capa_metrics(self):
        """Test CAPA program metrics."""
        service = self.CAPAService()

        # Create some CAPAs
        for i in range(5):
            service.initiate_capa(
                capa_type=self.CAPAType.CORRECTIVE,
                priority=self.CAPAPriority.MEDIUM,
                source_type="Audit",
                source_reference=f"IA-{i}",
                problem_title=f"Issue {i}",
                problem_description=f"Description {i}",
                initiator="QA"
            )

        metrics = service.get_capa_metrics()

        self.assertEqual(metrics["total"], 5)
        self.assertIn("status_distribution", metrics)

    def test_iso13485_capa(self):
        """Test ISO 13485 medical device CAPA."""
        service = self.ISO13485CAPA()

        capa = service.initiate_medical_device_capa(
            capa_type=self.CAPAType.CORRECTIVE,
            priority=self.CAPAPriority.CRITICAL,
            source_type="Field Safety",
            source_reference="FSN-001",
            problem_title="Device malfunction",
            problem_description="Device failed during use",
            initiator="QA",
            device_identifier="MD-001",
            device_name="Medical Monitor",
            lot_numbers=["LOT-A", "LOT-B"],
            patient_impact=True
        )

        # Check regulatory reporting
        report = service.check_regulatory_reporting(capa.capa_id)

        self.assertTrue(report["reporting_required"])
        self.assertIn("MDR", report["regulatory_frameworks"][0])


class TestInternalAudit(unittest.TestCase):
    """Tests for internal audit management."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.compliance.qms.internal_audit import (
            AuditType, AuditStatus, FindingSeverity,
            AuditFinding, AuditChecklist, InternalAudit,
            AuditScheduler, ISO9001AuditProgram
        )
        self.AuditType = AuditType
        self.AuditStatus = AuditStatus
        self.FindingSeverity = FindingSeverity
        self.AuditFinding = AuditFinding
        self.AuditChecklist = AuditChecklist
        self.InternalAudit = InternalAudit
        self.AuditScheduler = AuditScheduler
        self.ISO9001AuditProgram = ISO9001AuditProgram

    def test_audit_types(self):
        """Test audit type enumeration."""
        types = list(self.AuditType)

        self.assertIn(self.AuditType.SYSTEM, types)
        self.assertIn(self.AuditType.PROCESS, types)
        self.assertIn(self.AuditType.SUPPLIER, types)

    def test_finding_severity(self):
        """Test finding severity levels."""
        severities = list(self.FindingSeverity)

        self.assertEqual(self.FindingSeverity.MAJOR_NONCONFORMITY.value, 1)
        self.assertEqual(self.FindingSeverity.MINOR_NONCONFORMITY.value, 2)
        self.assertEqual(self.FindingSeverity.OBSERVATION.value, 3)

    def test_audit_scheduler(self):
        """Test audit scheduling."""
        scheduler = self.AuditScheduler()

        # Calculate risk
        risk = scheduler.calculate_process_risk(
            process_name="Production",
            impact=4,
            complexity=3,
            change_frequency=2,
            previous_findings=2
        )

        self.assertGreater(risk, 0)

        # Get frequency
        frequency = scheduler.get_recommended_frequency("Production")

        self.assertIn(frequency, [3, 6, 12, 24])

    def test_annual_audit_plan(self):
        """Test generating annual audit plan."""
        scheduler = self.AuditScheduler()

        # Set up process risks
        scheduler.calculate_process_risk("Production", 4, 3, 3)
        scheduler.calculate_process_risk("Quality", 5, 4, 2)
        scheduler.calculate_process_risk("Purchasing", 3, 2, 2)

        plan = scheduler.generate_annual_plan(2024, ["Production", "Quality", "Purchasing"])

        self.assertGreater(len(plan), 0)
        self.assertIn("audit_number", plan[0])
        self.assertIn("process", plan[0])

    def test_iso9001_audit_program(self):
        """Test ISO 9001 audit program."""
        program = self.ISO9001AuditProgram()

        audit = program.plan_audit(
            audit_type=self.AuditType.PROCESS,
            scope="Production process audit",
            processes=["Manufacturing", "Assembly"],
            clauses=["8.5", "8.6"],
            departments=["Production"],
            planned_date=datetime.now() + timedelta(days=30),
            lead_auditor="Lead Auditor"
        )

        self.assertIsNotNone(audit.audit_id)
        self.assertEqual(audit.status, self.AuditStatus.PLANNED)

    def test_conduct_audit(self):
        """Test conducting an audit."""
        program = self.ISO9001AuditProgram()

        audit = program.plan_audit(
            audit_type=self.AuditType.SYSTEM,
            scope="Full QMS audit",
            processes=["All"],
            clauses=["4", "5", "6", "7", "8", "9", "10"],
            departments=["All"],
            planned_date=datetime.now(),
            lead_auditor="Auditor"
        )

        program.schedule_audit(
            audit.audit_id,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=2),
            audit_team=["Auditor 1", "Auditor 2"],
            auditees=["Manager A", "Manager B"]
        )

        result = program.start_audit(audit.audit_id, "Lead Auditor")

        self.assertTrue(result["success"])
        self.assertEqual(audit.status, self.AuditStatus.IN_PROGRESS)

    def test_record_finding(self):
        """Test recording audit finding."""
        program = self.ISO9001AuditProgram()

        audit = program.plan_audit(
            audit_type=self.AuditType.PROCESS,
            scope="Process audit",
            processes=["Production"],
            clauses=["8.5"],
            departments=["Production"],
            planned_date=datetime.now(),
            lead_auditor="Auditor"
        )

        program.schedule_audit(audit.audit_id, datetime.now(), datetime.now(), ["A"], ["B"])
        program.start_audit(audit.audit_id, "Auditor")

        finding = program.record_finding(
            audit.audit_id,
            severity=self.FindingSeverity.MINOR_NONCONFORMITY,
            clause="8.5.1",
            process_area="Production Control",
            statement="Work instructions not available at workstation",
            evidence="Observed during floor walk",
            auditor="Auditor"
        )

        self.assertIsNotNone(finding.finding_id)
        self.assertTrue(finding.capa_required)

    def test_audit_completion(self):
        """Test completing audit."""
        program = self.ISO9001AuditProgram()

        audit = program.plan_audit(
            audit_type=self.AuditType.PROCESS,
            scope="Test audit",
            processes=["Test"],
            clauses=["8.5"],
            departments=["Test"],
            planned_date=datetime.now(),
            lead_auditor="Auditor"
        )

        program.schedule_audit(audit.audit_id, datetime.now(), datetime.now(), ["A"], ["B"])
        program.start_audit(audit.audit_id, "Auditor")

        result = program.complete_audit(
            audit.audit_id,
            summary="Audit completed successfully",
            lead_auditor="Auditor"
        )

        self.assertTrue(result["success"])
        self.assertIn("score", result)

    def test_program_metrics(self):
        """Test audit program metrics."""
        program = self.ISO9001AuditProgram()

        metrics = program.get_program_metrics()

        self.assertIn("total_audits", metrics)
        self.assertIn("total_findings", metrics)


class TestManagementReview(unittest.TestCase):
    """Tests for management review service."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.compliance.qms.management_review import (
            ReviewFrequency, ReviewStatus, ActionPriority,
            ReviewInput, ReviewOutput, ManagementReviewMeeting,
            ManagementReviewService, ISO9001ManagementReview
        )
        self.ReviewFrequency = ReviewFrequency
        self.ReviewStatus = ReviewStatus
        self.ActionPriority = ActionPriority
        self.ReviewInput = ReviewInput
        self.ReviewOutput = ReviewOutput
        self.ManagementReviewMeeting = ManagementReviewMeeting
        self.ManagementReviewService = ManagementReviewService
        self.ISO9001ManagementReview = ISO9001ManagementReview

    def test_review_frequency(self):
        """Test review frequency enumeration."""
        frequencies = list(self.ReviewFrequency)

        self.assertEqual(self.ReviewFrequency.QUARTERLY.value, 3)
        self.assertEqual(self.ReviewFrequency.ANNUAL.value, 12)

    def test_management_review_service(self):
        """Test management review service creation."""
        service = self.ManagementReviewService()

        self.assertIsNotNone(service)
        self.assertGreater(len(service.required_inputs), 0)

    def test_schedule_review(self):
        """Test scheduling management review."""
        service = self.ManagementReviewService()

        review = service.schedule_review(
            scheduled_date=datetime.now() + timedelta(days=30),
            frequency=self.ReviewFrequency.QUARTERLY,
            chairperson="CEO",
            attendees=["QA Manager", "Production Manager", "Engineering Manager"]
        )

        self.assertIsNotNone(review.review_id)
        self.assertEqual(review.status, self.ReviewStatus.SCHEDULED)

    def test_submit_input(self):
        """Test submitting review input."""
        service = self.ManagementReviewService()

        review = service.schedule_review(
            scheduled_date=datetime.now() + timedelta(days=30),
            frequency=self.ReviewFrequency.QUARTERLY,
            chairperson="CEO",
            attendees=["QA"]
        )

        service.start_input_collection(review.review_id, "QA")

        input_item = service.submit_input(
            review.review_id,
            category="Customer Satisfaction",
            title="Q3 Customer Survey Results",
            description="Summary of customer satisfaction survey",
            data={
                "current": 4.2,
                "previous": 4.0,
                "target": 4.5,
            },
            submitter="QA Manager"
        )

        self.assertIsNotNone(input_item.input_id)
        self.assertEqual(input_item.trend, "Improving")

    def test_conduct_review(self):
        """Test conducting management review."""
        service = self.ManagementReviewService()

        review = service.schedule_review(
            scheduled_date=datetime.now(),
            frequency=self.ReviewFrequency.QUARTERLY,
            chairperson="CEO",
            attendees=["QA", "Prod", "Eng"]
        )

        result = service.conduct_review(
            review.review_id,
            actual_date=datetime.now(),
            duration_hours=2.5,
            attendees=["QA", "Prod"],
            absentees=["Eng"]
        )

        self.assertTrue(result["success"])

    def test_record_decision(self):
        """Test recording review decision."""
        service = self.ManagementReviewService()

        review = service.schedule_review(
            scheduled_date=datetime.now(),
            frequency=self.ReviewFrequency.QUARTERLY,
            chairperson="CEO",
            attendees=["QA"]
        )

        service.conduct_review(review.review_id, datetime.now(), 2.0, ["QA"], [])

        output = service.record_decision(
            review.review_id,
            category="Resource Needs",
            decision="Hire additional QA technician",
            rationale="Increased inspection requirements",
            owner="HR Manager",
            actions=[
                {
                    "description": "Post job requisition",
                    "responsible": "HR",
                    "due_date": (datetime.now() + timedelta(days=7)).isoformat(),
                    "priority": "HIGH"
                }
            ]
        )

        self.assertIsNotNone(output.output_id)
        self.assertEqual(len(output.actions), 1)

    def test_generate_minutes(self):
        """Test generating meeting minutes."""
        service = self.ManagementReviewService()

        review = service.schedule_review(
            scheduled_date=datetime.now(),
            frequency=self.ReviewFrequency.QUARTERLY,
            chairperson="CEO",
            attendees=["QA", "Prod"]
        )

        service.start_input_collection(review.review_id, "QA")
        service.submit_input(review.review_id, "Audit Results", "Q3 Audits", "", {}, "QA")
        service.conduct_review(review.review_id, datetime.now(), 2.0, ["QA", "Prod"], [])

        result = service.generate_minutes(review.review_id, "QA")

        self.assertTrue(result["success"])
        self.assertIn("MANAGEMENT REVIEW MINUTES", result["minutes"])

    def test_iso9001_compliance_check(self):
        """Test ISO 9001 management review compliance."""
        service = self.ISO9001ManagementReview()

        review = service.schedule_review(
            scheduled_date=datetime.now(),
            frequency=self.ReviewFrequency.QUARTERLY,
            chairperson="CEO",
            attendees=["QA"]
        )

        input_coverage = service.check_input_coverage(review.review_id)

        self.assertIn("coverage_percentage", input_coverage)
        self.assertIn("missing_inputs", input_coverage)

    def test_review_metrics(self):
        """Test management review metrics."""
        service = self.ManagementReviewService()

        metrics = service.get_review_metrics()

        self.assertIn("total_reviews", metrics)
        self.assertIn("action_completion_rate", metrics)


if __name__ == "__main__":
    unittest.main()
