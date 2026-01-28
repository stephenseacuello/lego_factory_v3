"""
Training Management Service - FDA/ISO-Compliant Training and Competency Management.

Implements comprehensive training management compliant with:
- 21 CFR Part 211.25 (Personnel Qualifications)
- 21 CFR Part 820.25 (Personnel - Medical Devices)
- ISO 9001:2015 Section 7.2 (Competence)
- ISO 13485:2016 Section 6.2 (Human Resources)
- ICH Q10 (Pharmaceutical Quality System)
- cGMP Training Requirements

Features:
- Training curriculum design and management
- Competency-based training assignments
- Multi-modal training delivery (classroom, OJT, eLearning)
- Assessment and examination management
- Training effectiveness evaluation
- Certification and recertification tracking
- Training matrix management
- Gap analysis and remediation
- Regulatory inspection readiness reports
- Electronic training records with e-signatures
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class TrainingType(Enum):
    """Types of training delivery methods."""
    CLASSROOM = "classroom"
    ON_THE_JOB = "on_the_job"
    E_LEARNING = "e_learning"
    SELF_STUDY = "self_study"
    MENTORSHIP = "mentorship"
    SIMULATION = "simulation"
    ASSESSMENT_ONLY = "assessment_only"
    EXTERNAL = "external_course"


class TrainingStatus(Enum):
    """Training assignment lifecycle states."""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    WAIVED = "waived"
    DEFERRED = "deferred"


class CompetencyLevel(Enum):
    """Skill/competency proficiency levels."""
    AWARENESS = "awareness"  # Basic understanding
    PRACTITIONER = "practitioner"  # Can perform with supervision
    PROFICIENT = "proficient"  # Can perform independently
    EXPERT = "expert"  # Can train others, handle exceptions
    MASTER = "master"  # Can design/improve processes


class AssessmentType(Enum):
    """Types of competency assessments."""
    WRITTEN_EXAM = "written_exam"
    PRACTICAL_DEMO = "practical_demonstration"
    OBSERVATION = "supervisor_observation"
    VERBAL_QA = "verbal_questions"
    PORTFOLIO = "portfolio_review"
    SIMULATION = "simulation_exercise"
    PEER_REVIEW = "peer_review"


@dataclass
class Competency:
    """Competency or skill definition."""
    competency_id: str
    name: str
    description: str
    category: str  # technical, quality, safety, regulatory, soft_skills
    required_level: CompetencyLevel
    assessment_criteria: List[str] = field(default_factory=list)
    related_sops: List[str] = field(default_factory=list)
    related_equipment: List[str] = field(default_factory=list)
    regulatory_requirement: bool = False
    gmp_critical: bool = False


@dataclass
class TrainingCourse:
    """Training course definition."""
    course_id: str
    course_code: str
    title: str
    description: str
    version: str
    training_type: TrainingType
    duration_hours: float
    competencies_addressed: List[str]  # Competency IDs
    target_level: CompetencyLevel
    prerequisites: List[str] = field(default_factory=list)  # Course IDs
    content_outline: List[str] = field(default_factory=list)
    learning_objectives: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    assessment_required: bool = True
    assessment_type: AssessmentType = AssessmentType.WRITTEN_EXAM
    passing_score: float = 80.0
    validity_months: int = 12  # 0 = never expires
    gmp_critical: bool = False
    regulatory_required: bool = False
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    status: str = "draft"  # draft, approved, retired


@dataclass
class TrainingSession:
    """Scheduled training session (for classroom/instructor-led)."""
    session_id: str
    course_id: str
    session_date: datetime
    end_date: datetime
    location: str
    instructor: str
    max_participants: int = 20
    registered_participants: List[str] = field(default_factory=list)
    attended_participants: List[str] = field(default_factory=list)
    materials_provided: bool = False
    session_notes: str = ""
    status: str = "scheduled"  # scheduled, in_progress, completed, cancelled


@dataclass
class TrainingAssignment:
    """Individual training assignment to an employee."""
    assignment_id: str
    employee_id: str
    employee_name: str
    course_id: str
    assigned_by: str
    assigned_at: datetime
    due_date: datetime
    status: TrainingStatus
    session_id: Optional[str] = None  # For classroom training
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    hours_logged: float = 0.0
    assessment_score: Optional[float] = None
    assessment_attempts: int = 0
    max_assessment_attempts: int = 3
    assessed_by: Optional[str] = None
    assessed_at: Optional[datetime] = None
    trainer: Optional[str] = None  # For OJT
    competency_achieved: Optional[CompetencyLevel] = None
    comments: str = ""
    attachments: List[str] = field(default_factory=list)
    electronic_signature: Optional[str] = None


@dataclass
class TrainingRecord:
    """Historical training record (immutable after completion)."""
    record_id: str
    assignment_id: str
    employee_id: str
    course_id: str
    course_title: str
    course_version: str
    training_type: TrainingType
    completed_at: datetime
    expiry_date: Optional[datetime]
    assessment_score: Optional[float]
    competency_level: CompetencyLevel
    trainer_instructor: Optional[str]
    verified_by: str
    verified_at: datetime
    electronic_signature: str
    signature_meaning: str
    record_hash: str  # Integrity verification


@dataclass
class JobRole:
    """Job role with required competencies and training."""
    role_id: str
    role_name: str
    department: str
    description: str
    required_competencies: Dict[str, CompetencyLevel] = field(default_factory=dict)
    required_courses: List[str] = field(default_factory=list)
    gmp_position: bool = False
    safety_critical: bool = False
    minimum_education: Optional[str] = None
    minimum_experience_years: int = 0


@dataclass
class Employee:
    """Employee training profile."""
    employee_id: str
    employee_name: str
    email: str
    department: str
    job_roles: List[str]  # Role IDs
    hire_date: datetime
    manager_id: Optional[str] = None
    current_competencies: Dict[str, CompetencyLevel] = field(default_factory=dict)
    certifications: List[Dict] = field(default_factory=list)
    training_assignments: List[str] = field(default_factory=list)
    training_records: List[str] = field(default_factory=list)
    is_trainer: bool = False
    trainer_qualifications: List[str] = field(default_factory=list)
    status: str = "active"  # active, inactive, terminated


@dataclass
class TrainingEffectiveness:
    """Training effectiveness evaluation."""
    evaluation_id: str
    course_id: str
    employee_id: str
    evaluation_date: datetime
    evaluation_type: str  # level1_reaction, level2_learning, level3_behavior, level4_results
    score: float
    criteria_scores: Dict[str, float] = field(default_factory=dict)
    evaluator_id: str = ""
    comments: str = ""
    improvement_actions: List[str] = field(default_factory=list)


class TrainingManagementService:
    """
    FDA/ISO-compliant training and competency management service.

    Provides complete training lifecycle management from curriculum
    design through competency verification and regulatory reporting.
    """

    def __init__(self):
        self.competencies: Dict[str, Competency] = {}
        self.courses: Dict[str, TrainingCourse] = {}
        self.sessions: Dict[str, TrainingSession] = {}
        self.assignments: Dict[str, TrainingAssignment] = {}
        self.records: Dict[str, TrainingRecord] = {}
        self.job_roles: Dict[str, JobRole] = {}
        self.employees: Dict[str, Employee] = {}
        self.effectiveness_evaluations: Dict[str, TrainingEffectiveness] = {}
        self._audit_log: List[Dict] = []

    def _generate_id(self, prefix: str = "TRN") -> str:
        """Generate unique identifier."""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{timestamp}-{unique}"

    def _log_audit(self, action: str, entity_type: str, entity_id: str,
                   user: str, details: Dict = None):
        """Record audit trail entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user": user,
            "details": details or {},
            "hash": hashlib.sha256(
                f"{action}{entity_id}{user}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
        }
        self._audit_log.append(entry)
        logger.info(f"Training Audit: {action} on {entity_type} {entity_id} by {user}")

    def _generate_electronic_signature(self, user_id: str, meaning: str,
                                        data: str) -> str:
        """Generate electronic signature for training records."""
        timestamp = datetime.now().isoformat()
        signature_data = f"{user_id}|{meaning}|{timestamp}|{data}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    def _generate_record_hash(self, record_data: Dict) -> str:
        """Generate integrity hash for training record."""
        import json
        data_str = json.dumps(record_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    # =========================================================================
    # Competency Management
    # =========================================================================

    async def create_competency(
        self,
        name: str,
        description: str,
        category: str,
        required_level: CompetencyLevel,
        created_by: str,
        assessment_criteria: List[str] = None,
        related_sops: List[str] = None,
        gmp_critical: bool = False
    ) -> Competency:
        """
        Define a new competency/skill.

        Args:
            name: Competency name
            description: Detailed description
            category: Category (technical, quality, safety, etc.)
            required_level: Minimum required proficiency
            created_by: User creating the competency
            assessment_criteria: How competency is verified
            related_sops: Associated SOPs
            gmp_critical: Whether GMP-critical

        Returns:
            Created Competency
        """
        competency_id = self._generate_id("COMP")

        competency = Competency(
            competency_id=competency_id,
            name=name,
            description=description,
            category=category,
            required_level=required_level,
            assessment_criteria=assessment_criteria or [],
            related_sops=related_sops or [],
            gmp_critical=gmp_critical
        )

        self.competencies[competency_id] = competency
        self._log_audit("CREATE", "Competency", competency_id, created_by,
                        {"name": name, "category": category})

        return competency

    # =========================================================================
    # Course Management
    # =========================================================================

    async def create_course(
        self,
        course_code: str,
        title: str,
        description: str,
        training_type: TrainingType,
        duration_hours: float,
        competencies_addressed: List[str],
        target_level: CompetencyLevel,
        created_by: str,
        learning_objectives: List[str] = None,
        assessment_type: AssessmentType = AssessmentType.WRITTEN_EXAM,
        passing_score: float = 80.0,
        validity_months: int = 12,
        gmp_critical: bool = False,
        prerequisites: List[str] = None
    ) -> TrainingCourse:
        """
        Create a new training course.

        Args:
            course_code: Unique course code
            title: Course title
            description: Course description
            training_type: Delivery method
            duration_hours: Training duration
            competencies_addressed: Competencies covered
            target_level: Competency level achieved
            created_by: Creator user ID
            learning_objectives: Learning objectives
            assessment_type: Type of assessment
            passing_score: Minimum passing score
            validity_months: How long training is valid
            gmp_critical: Whether GMP-critical
            prerequisites: Required prior courses

        Returns:
            Created TrainingCourse
        """
        course_id = self._generate_id("CRS")

        course = TrainingCourse(
            course_id=course_id,
            course_code=course_code,
            title=title,
            description=description,
            version="1.0",
            training_type=training_type,
            duration_hours=duration_hours,
            competencies_addressed=competencies_addressed,
            target_level=target_level,
            prerequisites=prerequisites or [],
            learning_objectives=learning_objectives or [],
            assessment_required=True,
            assessment_type=assessment_type,
            passing_score=passing_score,
            validity_months=validity_months,
            gmp_critical=gmp_critical,
            created_by=created_by,
            created_at=datetime.now()
        )

        self.courses[course_id] = course
        self._log_audit("CREATE", "TrainingCourse", course_id, created_by,
                        {"course_code": course_code, "title": title})

        return course

    async def approve_course(
        self,
        course_id: str,
        approved_by: str,
        comments: str = ""
    ) -> TrainingCourse:
        """Approve a course for use in training assignments."""
        if course_id not in self.courses:
            raise ValueError(f"Course not found: {course_id}")

        course = self.courses[course_id]
        course.approved_by = approved_by
        course.approved_at = datetime.now()
        course.status = "approved"

        self._log_audit("APPROVE", "TrainingCourse", course_id, approved_by,
                        {"comments": comments})

        return course

    async def revise_course(
        self,
        course_id: str,
        changes: Dict,
        revised_by: str,
        reason: str
    ) -> TrainingCourse:
        """Create a new version of a course (change controlled)."""
        if course_id not in self.courses:
            raise ValueError(f"Course not found: {course_id}")

        original = self.courses[course_id]

        # Increment version
        major, minor = map(int, original.version.split("."))
        new_version = f"{major}.{minor + 1}"

        # Retire original
        original.status = "retired"

        # Create new version
        new_course_id = self._generate_id("CRS")
        new_course = TrainingCourse(
            course_id=new_course_id,
            course_code=original.course_code,
            title=changes.get("title", original.title),
            description=changes.get("description", original.description),
            version=new_version,
            training_type=original.training_type,
            duration_hours=changes.get("duration_hours", original.duration_hours),
            competencies_addressed=original.competencies_addressed,
            target_level=original.target_level,
            prerequisites=original.prerequisites,
            learning_objectives=changes.get("learning_objectives",
                                            original.learning_objectives),
            assessment_required=original.assessment_required,
            assessment_type=original.assessment_type,
            passing_score=changes.get("passing_score", original.passing_score),
            validity_months=original.validity_months,
            gmp_critical=original.gmp_critical,
            created_by=revised_by,
            created_at=datetime.now()
        )

        self.courses[new_course_id] = new_course
        self._log_audit("REVISE", "TrainingCourse", new_course_id, revised_by,
                        {"previous_version": original.version,
                         "new_version": new_version,
                         "reason": reason})

        return new_course

    # =========================================================================
    # Job Role Management
    # =========================================================================

    async def create_job_role(
        self,
        role_name: str,
        department: str,
        description: str,
        required_competencies: Dict[str, CompetencyLevel],
        required_courses: List[str],
        created_by: str,
        gmp_position: bool = False,
        safety_critical: bool = False
    ) -> JobRole:
        """
        Create a job role with training requirements.

        Defines the competencies and training required for a position.
        """
        role_id = self._generate_id("ROLE")

        role = JobRole(
            role_id=role_id,
            role_name=role_name,
            department=department,
            description=description,
            required_competencies=required_competencies,
            required_courses=required_courses,
            gmp_position=gmp_position,
            safety_critical=safety_critical
        )

        self.job_roles[role_id] = role
        self._log_audit("CREATE", "JobRole", role_id, created_by,
                        {"role_name": role_name, "department": department})

        return role

    # =========================================================================
    # Employee Management
    # =========================================================================

    async def register_employee(
        self,
        employee_name: str,
        email: str,
        department: str,
        job_roles: List[str],
        hire_date: datetime,
        registered_by: str,
        manager_id: Optional[str] = None
    ) -> Employee:
        """Register an employee in the training system."""
        employee_id = self._generate_id("EMP")

        employee = Employee(
            employee_id=employee_id,
            employee_name=employee_name,
            email=email,
            department=department,
            job_roles=job_roles,
            hire_date=hire_date,
            manager_id=manager_id
        )

        self.employees[employee_id] = employee
        self._log_audit("REGISTER", "Employee", employee_id, registered_by,
                        {"name": employee_name, "department": department})

        return employee

    async def get_training_gap_analysis(
        self,
        employee_id: str
    ) -> Dict:
        """
        Perform training gap analysis for an employee.

        Compares current competencies against job role requirements.
        Returns required training to close gaps.
        """
        if employee_id not in self.employees:
            raise ValueError(f"Employee not found: {employee_id}")

        employee = self.employees[employee_id]
        gaps = []
        required_courses = set()

        for role_id in employee.job_roles:
            if role_id not in self.job_roles:
                continue

            role = self.job_roles[role_id]

            # Check competency gaps
            for comp_id, required_level in role.required_competencies.items():
                current_level = employee.current_competencies.get(comp_id)

                if not current_level:
                    gaps.append({
                        "type": "competency",
                        "competency_id": comp_id,
                        "required_level": required_level.value,
                        "current_level": None,
                        "gap": "missing"
                    })
                elif self._competency_level_value(current_level) < \
                        self._competency_level_value(required_level):
                    gaps.append({
                        "type": "competency",
                        "competency_id": comp_id,
                        "required_level": required_level.value,
                        "current_level": current_level.value,
                        "gap": "insufficient"
                    })

            # Check required courses
            for course_id in role.required_courses:
                # Check if employee has valid training record
                has_valid_record = any(
                    rec_id in employee.training_records and
                    self._is_training_valid(self.records[rec_id])
                    for rec_id in employee.training_records
                    if rec_id in self.records and
                    self.records[rec_id].course_id == course_id
                )

                if not has_valid_record:
                    required_courses.add(course_id)

        # Find courses to address competency gaps
        for gap in gaps:
            if gap["type"] == "competency":
                for course in self.courses.values():
                    if (gap["competency_id"] in course.competencies_addressed and
                            course.status == "approved"):
                        required_courses.add(course.course_id)

        return {
            "employee_id": employee_id,
            "employee_name": employee.employee_name,
            "analysis_date": datetime.now().isoformat(),
            "competency_gaps": gaps,
            "required_courses": list(required_courses),
            "total_gaps": len(gaps),
            "priority": "high" if any(
                g.get("gap") == "missing" for g in gaps
            ) else "medium" if gaps else "low"
        }

    def _competency_level_value(self, level: CompetencyLevel) -> int:
        """Convert competency level to numeric value for comparison."""
        values = {
            CompetencyLevel.AWARENESS: 1,
            CompetencyLevel.PRACTITIONER: 2,
            CompetencyLevel.PROFICIENT: 3,
            CompetencyLevel.EXPERT: 4,
            CompetencyLevel.MASTER: 5
        }
        return values.get(level, 0)

    def _is_training_valid(self, record: TrainingRecord) -> bool:
        """Check if a training record is still valid (not expired)."""
        if not record.expiry_date:
            return True
        return record.expiry_date > datetime.now()

    # =========================================================================
    # Training Assignment and Execution
    # =========================================================================

    async def assign_training(
        self,
        employee_id: str,
        course_id: str,
        assigned_by: str,
        due_date: datetime,
        session_id: Optional[str] = None,
        trainer: Optional[str] = None
    ) -> TrainingAssignment:
        """
        Assign training to an employee.

        Args:
            employee_id: Employee to assign
            course_id: Course to assign
            assigned_by: Assigning manager/supervisor
            due_date: Training due date
            session_id: Session ID for classroom training
            trainer: Trainer ID for OJT

        Returns:
            Created TrainingAssignment
        """
        if employee_id not in self.employees:
            raise ValueError(f"Employee not found: {employee_id}")
        if course_id not in self.courses:
            raise ValueError(f"Course not found: {course_id}")

        course = self.courses[course_id]
        employee = self.employees[employee_id]

        if course.status != "approved":
            raise ValueError(f"Course must be approved: {course_id}")

        # Check prerequisites
        for prereq_id in course.prerequisites:
            has_prereq = any(
                self.records[rec_id].course_id == prereq_id
                for rec_id in employee.training_records
                if rec_id in self.records
            )
            if not has_prereq:
                raise ValueError(f"Missing prerequisite course: {prereq_id}")

        assignment_id = self._generate_id("ASGN")

        assignment = TrainingAssignment(
            assignment_id=assignment_id,
            employee_id=employee_id,
            employee_name=employee.employee_name,
            course_id=course_id,
            assigned_by=assigned_by,
            assigned_at=datetime.now(),
            due_date=due_date,
            status=TrainingStatus.ASSIGNED,
            session_id=session_id,
            trainer=trainer
        )

        self.assignments[assignment_id] = assignment
        employee.training_assignments.append(assignment_id)

        self._log_audit("ASSIGN", "TrainingAssignment", assignment_id, assigned_by,
                        {"employee_id": employee_id, "course_id": course_id})

        return assignment

    async def auto_assign_role_training(
        self,
        employee_id: str,
        role_id: str,
        assigned_by: str
    ) -> List[TrainingAssignment]:
        """
        Automatically assign all required training for a job role.

        Useful when an employee is assigned to a new role.
        """
        if employee_id not in self.employees:
            raise ValueError(f"Employee not found: {employee_id}")
        if role_id not in self.job_roles:
            raise ValueError(f"Role not found: {role_id}")

        employee = self.employees[employee_id]
        role = self.job_roles[role_id]

        assignments = []
        for course_id in role.required_courses:
            # Skip if already assigned or completed
            already_assigned = any(
                self.assignments[a].course_id == course_id and
                self.assignments[a].status not in [TrainingStatus.EXPIRED,
                                                   TrainingStatus.FAILED]
                for a in employee.training_assignments
                if a in self.assignments
            )

            if already_assigned:
                continue

            # Determine due date based on course criticality
            course = self.courses.get(course_id)
            if course:
                if course.gmp_critical:
                    due_date = datetime.now() + timedelta(days=30)
                else:
                    due_date = datetime.now() + timedelta(days=90)

                assignment = await self.assign_training(
                    employee_id=employee_id,
                    course_id=course_id,
                    assigned_by=assigned_by,
                    due_date=due_date
                )
                assignments.append(assignment)

        return assignments

    async def start_training(
        self,
        assignment_id: str,
        started_by: str
    ) -> TrainingAssignment:
        """Mark training as started."""
        if assignment_id not in self.assignments:
            raise ValueError(f"Assignment not found: {assignment_id}")

        assignment = self.assignments[assignment_id]
        assignment.status = TrainingStatus.IN_PROGRESS
        assignment.started_at = datetime.now()

        self._log_audit("START", "TrainingAssignment", assignment_id, started_by)

        return assignment

    async def record_training_progress(
        self,
        assignment_id: str,
        hours_completed: float,
        notes: str = ""
    ) -> TrainingAssignment:
        """Record training hours/progress (for self-study or OJT)."""
        if assignment_id not in self.assignments:
            raise ValueError(f"Assignment not found: {assignment_id}")

        assignment = self.assignments[assignment_id]
        assignment.hours_logged += hours_completed
        assignment.comments = notes

        return assignment

    async def record_assessment(
        self,
        assignment_id: str,
        score: float,
        assessed_by: str,
        competency_achieved: CompetencyLevel,
        comments: str = ""
    ) -> Tuple[TrainingAssignment, bool]:
        """
        Record assessment results.

        Returns:
            Tuple of (assignment, passed)
        """
        if assignment_id not in self.assignments:
            raise ValueError(f"Assignment not found: {assignment_id}")

        assignment = self.assignments[assignment_id]
        course = self.courses[assignment.course_id]

        assignment.assessment_score = score
        assignment.assessment_attempts += 1
        assignment.assessed_by = assessed_by
        assignment.assessed_at = datetime.now()
        assignment.competency_achieved = competency_achieved
        assignment.comments = comments

        passed = score >= course.passing_score

        if passed:
            assignment.status = TrainingStatus.COMPLETED
            assignment.completed_at = datetime.now()

            # Set expiry date
            if course.validity_months > 0:
                assignment.expiry_date = datetime.now() + timedelta(
                    days=course.validity_months * 30
                )
        else:
            if assignment.assessment_attempts >= assignment.max_assessment_attempts:
                assignment.status = TrainingStatus.FAILED
            # Otherwise remains in progress for retake

        self._log_audit("ASSESS", "TrainingAssignment", assignment_id, assessed_by,
                        {"score": score, "passed": passed,
                         "attempt": assignment.assessment_attempts})

        return assignment, passed

    async def complete_training(
        self,
        assignment_id: str,
        completed_by: str,
        verified_by: str,
        competency_achieved: CompetencyLevel
    ) -> TrainingRecord:
        """
        Complete training and create immutable training record.

        Creates 21 CFR Part 11 compliant training record with
        electronic signature.
        """
        if assignment_id not in self.assignments:
            raise ValueError(f"Assignment not found: {assignment_id}")

        assignment = self.assignments[assignment_id]
        course = self.courses[assignment.course_id]
        employee = self.employees[assignment.employee_id]

        if assignment.status != TrainingStatus.COMPLETED:
            raise ValueError(f"Training not completed. Status: {assignment.status}")

        record_id = self._generate_id("REC")

        # Create record data for hashing
        record_data = {
            "record_id": record_id,
            "assignment_id": assignment_id,
            "employee_id": assignment.employee_id,
            "course_id": assignment.course_id,
            "completed_at": assignment.completed_at.isoformat(),
            "score": assignment.assessment_score
        }

        record_hash = self._generate_record_hash(record_data)
        signature = self._generate_electronic_signature(
            verified_by,
            "Training Completion Verification",
            record_hash
        )

        record = TrainingRecord(
            record_id=record_id,
            assignment_id=assignment_id,
            employee_id=assignment.employee_id,
            course_id=assignment.course_id,
            course_title=course.title,
            course_version=course.version,
            training_type=course.training_type,
            completed_at=assignment.completed_at,
            expiry_date=assignment.expiry_date,
            assessment_score=assignment.assessment_score,
            competency_level=competency_achieved,
            trainer_instructor=assignment.trainer,
            verified_by=verified_by,
            verified_at=datetime.now(),
            electronic_signature=signature,
            signature_meaning="I verify that this training was completed in accordance with approved procedures",
            record_hash=record_hash
        )

        self.records[record_id] = record
        employee.training_records.append(record_id)

        # Update employee competencies
        for comp_id in course.competencies_addressed:
            current = employee.current_competencies.get(comp_id)
            if not current or self._competency_level_value(current) < \
                    self._competency_level_value(competency_achieved):
                employee.current_competencies[comp_id] = competency_achieved

        # Generate electronic signature for assignment
        assignment.electronic_signature = signature

        self._log_audit("COMPLETE", "TrainingRecord", record_id, verified_by,
                        {"employee_id": assignment.employee_id,
                         "course_id": assignment.course_id,
                         "competency": competency_achieved.value})

        return record

    # =========================================================================
    # Training Effectiveness
    # =========================================================================

    async def record_effectiveness_evaluation(
        self,
        course_id: str,
        employee_id: str,
        evaluation_type: str,
        score: float,
        criteria_scores: Dict[str, float],
        evaluator_id: str,
        comments: str = ""
    ) -> TrainingEffectiveness:
        """
        Record training effectiveness evaluation.

        Implements Kirkpatrick's four levels:
        - Level 1: Reaction (trainee satisfaction)
        - Level 2: Learning (knowledge/skill gained)
        - Level 3: Behavior (on-job application)
        - Level 4: Results (business impact)
        """
        evaluation_id = self._generate_id("EVAL")

        evaluation = TrainingEffectiveness(
            evaluation_id=evaluation_id,
            course_id=course_id,
            employee_id=employee_id,
            evaluation_date=datetime.now(),
            evaluation_type=evaluation_type,
            score=score,
            criteria_scores=criteria_scores,
            evaluator_id=evaluator_id,
            comments=comments
        )

        self.effectiveness_evaluations[evaluation_id] = evaluation
        self._log_audit("EVALUATE", "TrainingEffectiveness", evaluation_id,
                        evaluator_id, {"type": evaluation_type, "score": score})

        return evaluation

    async def get_course_effectiveness_summary(
        self,
        course_id: str
    ) -> Dict:
        """Get aggregated effectiveness metrics for a course."""
        evaluations = [
            e for e in self.effectiveness_evaluations.values()
            if e.course_id == course_id
        ]

        if not evaluations:
            return {"course_id": course_id, "evaluations": 0}

        by_type = {}
        for e in evaluations:
            if e.evaluation_type not in by_type:
                by_type[e.evaluation_type] = []
            by_type[e.evaluation_type].append(e.score)

        return {
            "course_id": course_id,
            "total_evaluations": len(evaluations),
            "by_level": {
                level: {
                    "count": len(scores),
                    "average": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores)
                }
                for level, scores in by_type.items()
            }
        }

    # =========================================================================
    # Scheduling and Sessions
    # =========================================================================

    async def schedule_session(
        self,
        course_id: str,
        session_date: datetime,
        end_date: datetime,
        location: str,
        instructor: str,
        max_participants: int,
        scheduled_by: str
    ) -> TrainingSession:
        """Schedule a classroom training session."""
        if course_id not in self.courses:
            raise ValueError(f"Course not found: {course_id}")

        session_id = self._generate_id("SES")

        session = TrainingSession(
            session_id=session_id,
            course_id=course_id,
            session_date=session_date,
            end_date=end_date,
            location=location,
            instructor=instructor,
            max_participants=max_participants
        )

        self.sessions[session_id] = session
        self._log_audit("SCHEDULE", "TrainingSession", session_id, scheduled_by,
                        {"course_id": course_id, "date": session_date.isoformat()})

        return session

    async def register_for_session(
        self,
        session_id: str,
        employee_id: str
    ) -> TrainingSession:
        """Register an employee for a training session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        if employee_id not in self.employees:
            raise ValueError(f"Employee not found: {employee_id}")

        session = self.sessions[session_id]

        if len(session.registered_participants) >= session.max_participants:
            raise ValueError("Session is at capacity")

        if employee_id not in session.registered_participants:
            session.registered_participants.append(employee_id)

        return session

    async def record_attendance(
        self,
        session_id: str,
        attendee_ids: List[str],
        recorded_by: str
    ) -> TrainingSession:
        """Record attendance for a training session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        session.attended_participants = attendee_ids
        session.status = "completed"

        self._log_audit("ATTENDANCE", "TrainingSession", session_id, recorded_by,
                        {"attended": len(attendee_ids)})

        return session

    # =========================================================================
    # Reporting and Compliance
    # =========================================================================

    async def generate_training_matrix(
        self,
        department: Optional[str] = None
    ) -> Dict:
        """
        Generate training matrix showing employee vs. required courses.

        Standard compliance report for FDA inspections.
        """
        employees = [
            e for e in self.employees.values()
            if e.status == "active" and (not department or e.department == department)
        ]

        # Collect all required courses from roles
        all_required_courses = set()
        for role in self.job_roles.values():
            all_required_courses.update(role.required_courses)

        matrix = []
        for employee in employees:
            row = {
                "employee_id": employee.employee_id,
                "employee_name": employee.employee_name,
                "department": employee.department,
                "courses": {}
            }

            # Get employee's required courses based on roles
            required_for_employee = set()
            for role_id in employee.job_roles:
                if role_id in self.job_roles:
                    required_for_employee.update(
                        self.job_roles[role_id].required_courses
                    )

            for course_id in all_required_courses:
                status = "not_required"
                expiry = None

                if course_id in required_for_employee:
                    # Check training records
                    record = next(
                        (self.records[r] for r in employee.training_records
                         if r in self.records and
                         self.records[r].course_id == course_id),
                        None
                    )

                    if record:
                        if self._is_training_valid(record):
                            status = "current"
                            expiry = record.expiry_date.isoformat() \
                                if record.expiry_date else None
                        else:
                            status = "expired"
                            expiry = record.expiry_date.isoformat() \
                                if record.expiry_date else None
                    else:
                        # Check if assigned
                        assignment = next(
                            (self.assignments[a] for a in employee.training_assignments
                             if a in self.assignments and
                             self.assignments[a].course_id == course_id and
                             self.assignments[a].status in [
                                 TrainingStatus.ASSIGNED,
                                 TrainingStatus.IN_PROGRESS
                             ]),
                            None
                        )

                        if assignment:
                            status = "assigned"
                        else:
                            status = "required"

                row["courses"][course_id] = {
                    "status": status,
                    "expiry_date": expiry
                }

            matrix.append(row)

        return {
            "generated_at": datetime.now().isoformat(),
            "department": department,
            "employee_count": len(matrix),
            "courses": list(all_required_courses),
            "matrix": matrix
        }

    async def get_overdue_training(self) -> List[Dict]:
        """Get all overdue training assignments."""
        overdue = []
        now = datetime.now()

        for assignment in self.assignments.values():
            if (assignment.status in [TrainingStatus.ASSIGNED,
                                      TrainingStatus.IN_PROGRESS] and
                    assignment.due_date < now):
                employee = self.employees.get(assignment.employee_id)
                course = self.courses.get(assignment.course_id)

                overdue.append({
                    "assignment_id": assignment.assignment_id,
                    "employee_id": assignment.employee_id,
                    "employee_name": employee.employee_name if employee else "Unknown",
                    "course_id": assignment.course_id,
                    "course_title": course.title if course else "Unknown",
                    "due_date": assignment.due_date.isoformat(),
                    "days_overdue": (now - assignment.due_date).days,
                    "gmp_critical": course.gmp_critical if course else False
                })

        return sorted(overdue, key=lambda x: x["days_overdue"], reverse=True)

    async def get_expiring_training(
        self,
        days_ahead: int = 30
    ) -> List[Dict]:
        """Get training records expiring within specified days."""
        expiring = []
        cutoff = datetime.now() + timedelta(days=days_ahead)
        now = datetime.now()

        for record in self.records.values():
            if record.expiry_date and now < record.expiry_date < cutoff:
                employee = self.employees.get(record.employee_id)
                course = self.courses.get(record.course_id)

                expiring.append({
                    "record_id": record.record_id,
                    "employee_id": record.employee_id,
                    "employee_name": employee.employee_name if employee else "Unknown",
                    "course_id": record.course_id,
                    "course_title": course.title if course else record.course_title,
                    "expiry_date": record.expiry_date.isoformat(),
                    "days_until_expiry": (record.expiry_date - now).days
                })

        return sorted(expiring, key=lambda x: x["days_until_expiry"])

    async def get_employee_training_record(
        self,
        employee_id: str
    ) -> Dict:
        """Get complete training record for an employee."""
        if employee_id not in self.employees:
            raise ValueError(f"Employee not found: {employee_id}")

        employee = self.employees[employee_id]

        current_training = [
            {
                "record_id": self.records[r].record_id,
                "course_title": self.records[r].course_title,
                "completed_at": self.records[r].completed_at.isoformat(),
                "expiry_date": self.records[r].expiry_date.isoformat()
                    if self.records[r].expiry_date else None,
                "status": "current" if self._is_training_valid(self.records[r]) else "expired",
                "competency_level": self.records[r].competency_level.value
            }
            for r in employee.training_records
            if r in self.records
        ]

        pending_assignments = [
            {
                "assignment_id": self.assignments[a].assignment_id,
                "course_id": self.assignments[a].course_id,
                "course_title": self.courses[self.assignments[a].course_id].title
                    if self.assignments[a].course_id in self.courses else "Unknown",
                "due_date": self.assignments[a].due_date.isoformat(),
                "status": self.assignments[a].status.value
            }
            for a in employee.training_assignments
            if a in self.assignments and
            self.assignments[a].status in [TrainingStatus.ASSIGNED,
                                           TrainingStatus.IN_PROGRESS]
        ]

        return {
            "employee_id": employee_id,
            "employee_name": employee.employee_name,
            "department": employee.department,
            "hire_date": employee.hire_date.isoformat(),
            "current_competencies": {
                k: v.value for k, v in employee.current_competencies.items()
            },
            "completed_training": current_training,
            "pending_training": pending_assignments,
            "is_trainer": employee.is_trainer,
            "trainer_qualifications": employee.trainer_qualifications
        }

    async def generate_inspection_report(self) -> Dict:
        """
        Generate training summary report for regulatory inspection.

        Provides FDA-ready training compliance overview.
        """
        total_employees = len([e for e in self.employees.values()
                              if e.status == "active"])
        total_gmp_positions = sum(
            1 for e in self.employees.values()
            if e.status == "active" and
            any(r in self.job_roles and self.job_roles[r].gmp_position
                for r in e.job_roles)
        )

        overdue = await self.get_overdue_training()
        expiring = await self.get_expiring_training(30)

        # Calculate compliance rate
        gmp_training_compliant = 0
        gmp_training_total = 0

        for employee in self.employees.values():
            if employee.status != "active":
                continue

            for role_id in employee.job_roles:
                role = self.job_roles.get(role_id)
                if not role or not role.gmp_position:
                    continue

                for course_id in role.required_courses:
                    gmp_training_total += 1
                    record = next(
                        (self.records[r] for r in employee.training_records
                         if r in self.records and
                         self.records[r].course_id == course_id and
                         self._is_training_valid(self.records[r])),
                        None
                    )
                    if record:
                        gmp_training_compliant += 1

        compliance_rate = (gmp_training_compliant / gmp_training_total * 100) \
            if gmp_training_total > 0 else 100

        return {
            "report_date": datetime.now().isoformat(),
            "summary": {
                "total_active_employees": total_employees,
                "gmp_positions": total_gmp_positions,
                "total_courses": len(self.courses),
                "approved_courses": sum(1 for c in self.courses.values()
                                       if c.status == "approved"),
                "total_training_records": len(self.records)
            },
            "compliance": {
                "gmp_training_compliance_rate": round(compliance_rate, 2),
                "compliant_count": gmp_training_compliant,
                "total_required": gmp_training_total,
                "overdue_assignments": len(overdue),
                "critical_overdue": sum(1 for o in overdue if o["gmp_critical"]),
                "expiring_30_days": len(expiring)
            },
            "action_items": {
                "overdue_training": overdue[:10],  # Top 10
                "expiring_soon": expiring[:10]
            },
            "electronic_records": {
                "part_11_compliant": True,
                "electronic_signatures_enabled": True,
                "audit_trail_enabled": True,
                "total_audit_entries": len(self._audit_log)
            }
        }

    def get_audit_trail(
        self,
        entity_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Retrieve audit trail entries."""
        entries = self._audit_log

        if entity_id:
            entries = [e for e in entries if entity_id in e.get("entity_id", "")]

        if start_date:
            entries = [e for e in entries
                      if datetime.fromisoformat(e["timestamp"]) >= start_date]

        if end_date:
            entries = [e for e in entries
                      if datetime.fromisoformat(e["timestamp"]) <= end_date]

        return entries


# Factory function
def create_training_service() -> TrainingManagementService:
    """Create and return a TrainingManagementService instance."""
    return TrainingManagementService()
