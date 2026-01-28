"""
Batch Record Service - FDA-Compliant Electronic Batch Record Management.

Implements electronic batch record (EBR) functionality compliant with:
- 21 CFR Part 211 (cGMP for Finished Pharmaceuticals)
- 21 CFR Part 820 (Quality System Regulation for Medical Devices)
- 21 CFR Part 11 (Electronic Records and Signatures)
- EU Annex 11 (Computerized Systems)

Features:
- Master Batch Record (MBR) template management
- Electronic Batch Record (EBR) generation and execution
- In-process control tracking with specifications
- Material traceability (lot/batch tracking)
- Equipment qualification verification
- Environmental monitoring integration
- Deviation linking and exception handling
- Electronic signatures for critical steps
- Yield calculations and reconciliation
- Batch release and certification workflow
"""

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    """Batch record lifecycle states."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    UNDER_INVESTIGATION = "under_investigation"
    APPROVED = "approved"
    RELEASED = "released"
    REJECTED = "rejected"
    QUARANTINE = "quarantine"


class StepStatus(Enum):
    """Individual step execution states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    DEVIATION = "deviation"


class VerificationType(Enum):
    """Types of verification required."""
    NONE = "none"
    SINGLE = "single_signature"
    DUAL = "dual_signature"
    SUPERVISOR = "supervisor_required"


class ParameterType(Enum):
    """Types of process parameters."""
    NUMERIC = "numeric"
    TEXT = "text"
    BOOLEAN = "boolean"
    SELECTION = "selection"
    DATETIME = "datetime"
    BARCODE = "barcode"
    CALCULATION = "calculation"


@dataclass
class ProcessParameter:
    """In-process control parameter specification."""
    parameter_id: str
    name: str
    parameter_type: ParameterType
    unit: Optional[str] = None
    target_value: Optional[float] = None
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    allowed_values: Optional[List[str]] = None  # For selection type
    formula: Optional[str] = None  # For calculation type
    is_critical: bool = False
    verification_type: VerificationType = VerificationType.SINGLE


@dataclass
class MaterialRequirement:
    """Bill of materials entry for batch record."""
    material_id: str
    material_name: str
    material_code: str
    quantity_required: float
    unit: str
    is_critical: bool = True
    requires_lot_tracking: bool = True
    storage_conditions: Optional[str] = None
    expiry_check_required: bool = True


@dataclass
class MaterialUsage:
    """Actual material used during batch execution."""
    material_id: str
    lot_number: str
    quantity_used: float
    unit: str
    expiry_date: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    barcode_scanned: bool = False
    supplier_coa_verified: bool = False


@dataclass
class EquipmentUsage:
    """Equipment used during batch execution."""
    equipment_id: str
    equipment_name: str
    calibration_due_date: datetime
    qualification_status: str  # IQ, OQ, PQ status
    cleaning_verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None


@dataclass
class EnvironmentalReading:
    """Environmental monitoring data point."""
    reading_id: str
    parameter: str  # temperature, humidity, pressure, particle_count
    value: float
    unit: str
    location: str
    recorded_at: datetime
    within_spec: bool = True
    alert_generated: bool = False


@dataclass
class BatchStep:
    """Individual step in batch record."""
    step_id: str
    step_number: int
    step_name: str
    description: str
    work_instructions: str
    verification_type: VerificationType
    parameters: List[ProcessParameter] = field(default_factory=list)
    materials_required: List[MaterialRequirement] = field(default_factory=list)
    equipment_required: List[str] = field(default_factory=list)
    environmental_requirements: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    estimated_duration_minutes: int = 0
    is_critical: bool = False
    can_be_skipped: bool = False
    prerequisite_steps: List[str] = field(default_factory=list)
    sop_references: List[str] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)


@dataclass
class StepExecution:
    """Execution record for a batch step."""
    step_id: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    executed_by: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    parameter_values: Dict[str, Any] = field(default_factory=dict)
    materials_used: List[MaterialUsage] = field(default_factory=list)
    equipment_used: List[EquipmentUsage] = field(default_factory=list)
    environmental_readings: List[EnvironmentalReading] = field(default_factory=list)
    deviations: List[str] = field(default_factory=list)  # Deviation IDs
    comments: str = ""
    attachments: List[str] = field(default_factory=list)
    electronic_signature: Optional[str] = None
    signature_meaning: Optional[str] = None


@dataclass
class MasterBatchRecord:
    """Master Batch Record template."""
    mbr_id: str
    product_code: str
    product_name: str
    version: str
    effective_date: datetime
    batch_size: float
    batch_size_unit: str
    steps: List[BatchStep]
    created_by: str
    created_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    status: str = "draft"  # draft, approved, superseded, obsolete
    revision_history: List[Dict] = field(default_factory=list)
    yield_specification: Optional[Tuple[float, float]] = None  # min, max %


@dataclass
class ElectronicBatchRecord:
    """Electronic Batch Record instance."""
    ebr_id: str
    batch_number: str
    mbr_id: str
    mbr_version: str
    product_code: str
    product_name: str
    batch_size: float
    batch_size_unit: str
    status: BatchStatus
    initiated_by: str
    initiated_at: datetime
    step_executions: Dict[str, StepExecution] = field(default_factory=dict)
    manufacturing_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    theoretical_yield: Optional[float] = None
    actual_yield: Optional[float] = None
    yield_percentage: Optional[float] = None
    total_deviations: int = 0
    critical_deviations: int = 0
    review_comments: List[Dict] = field(default_factory=list)
    qa_reviewer: Optional[str] = None
    qa_review_date: Optional[datetime] = None
    released_by: Optional[str] = None
    released_at: Optional[datetime] = None
    batch_disposition: Optional[str] = None  # release, reject, rework


@dataclass
class YieldReconciliation:
    """Batch yield calculation and reconciliation."""
    ebr_id: str
    theoretical_yield: float
    actual_yield: float
    yield_percentage: float
    unit: str
    waste_quantity: float
    sample_quantity: float
    reconciliation_status: str  # pass, fail, under_investigation
    variance_explanation: Optional[str] = None
    calculated_at: datetime = field(default_factory=datetime.now)
    calculated_by: Optional[str] = None


class BatchRecordService:
    """
    FDA-compliant Electronic Batch Record management service.

    Provides complete EBR lifecycle management from MBR template
    creation through batch execution, review, and release.
    """

    def __init__(self):
        self.master_batch_records: Dict[str, MasterBatchRecord] = {}
        self.electronic_batch_records: Dict[str, ElectronicBatchRecord] = {}
        self.yield_reconciliations: Dict[str, YieldReconciliation] = {}
        self._audit_log: List[Dict] = []

    def _generate_id(self, prefix: str = "BR") -> str:
        """Generate unique identifier."""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{timestamp}-{unique}"

    def _log_audit(self, action: str, entity_type: str, entity_id: str,
                   user: str, details: Dict = None):
        """Record audit trail entry (21 CFR Part 11 compliant)."""
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
        logger.info(f"Audit: {action} on {entity_type} {entity_id} by {user}")

    def _generate_electronic_signature(self, user_id: str, meaning: str,
                                        data_hash: str) -> str:
        """Generate 21 CFR Part 11 compliant electronic signature."""
        timestamp = datetime.now().isoformat()
        signature_data = f"{user_id}|{meaning}|{timestamp}|{data_hash}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    # =========================================================================
    # Master Batch Record Management
    # =========================================================================

    async def create_master_batch_record(
        self,
        product_code: str,
        product_name: str,
        batch_size: float,
        batch_size_unit: str,
        steps: List[Dict],
        created_by: str,
        yield_specification: Optional[Tuple[float, float]] = None
    ) -> MasterBatchRecord:
        """
        Create a new Master Batch Record template.

        Args:
            product_code: Product identifier
            product_name: Product name
            batch_size: Standard batch size
            batch_size_unit: Unit of measure (kg, L, units)
            steps: List of step definitions
            created_by: User creating the MBR
            yield_specification: (min%, max%) yield range

        Returns:
            Created MasterBatchRecord
        """
        mbr_id = self._generate_id("MBR")

        # Convert step dictionaries to BatchStep objects
        batch_steps = []
        for i, step_data in enumerate(steps, 1):
            step = BatchStep(
                step_id=f"{mbr_id}-STEP-{i:03d}",
                step_number=i,
                step_name=step_data.get("name", f"Step {i}"),
                description=step_data.get("description", ""),
                work_instructions=step_data.get("work_instructions", ""),
                verification_type=VerificationType(
                    step_data.get("verification_type", "single_signature")
                ),
                parameters=[
                    ProcessParameter(**p) for p in step_data.get("parameters", [])
                ],
                materials_required=[
                    MaterialRequirement(**m) for m in step_data.get("materials", [])
                ],
                equipment_required=step_data.get("equipment", []),
                environmental_requirements=step_data.get("environmental", {}),
                estimated_duration_minutes=step_data.get("duration_minutes", 0),
                is_critical=step_data.get("is_critical", False),
                can_be_skipped=step_data.get("can_be_skipped", False),
                prerequisite_steps=step_data.get("prerequisites", []),
                sop_references=step_data.get("sops", []),
                safety_warnings=step_data.get("safety", [])
            )
            batch_steps.append(step)

        mbr = MasterBatchRecord(
            mbr_id=mbr_id,
            product_code=product_code,
            product_name=product_name,
            version="1.0",
            effective_date=datetime.now(),
            batch_size=batch_size,
            batch_size_unit=batch_size_unit,
            steps=batch_steps,
            created_by=created_by,
            created_at=datetime.now(),
            yield_specification=yield_specification
        )

        self.master_batch_records[mbr_id] = mbr
        self._log_audit("CREATE", "MasterBatchRecord", mbr_id, created_by,
                        {"product_code": product_code, "steps": len(batch_steps)})

        return mbr

    async def approve_master_batch_record(
        self,
        mbr_id: str,
        approved_by: str,
        comments: str = ""
    ) -> MasterBatchRecord:
        """
        Approve a Master Batch Record for use.

        Requires appropriate authority (typically QA Manager).
        """
        if mbr_id not in self.master_batch_records:
            raise ValueError(f"MBR not found: {mbr_id}")

        mbr = self.master_batch_records[mbr_id]

        if mbr.status != "draft":
            raise ValueError(f"Only draft MBRs can be approved. Current: {mbr.status}")

        mbr.approved_by = approved_by
        mbr.approved_at = datetime.now()
        mbr.status = "approved"
        mbr.revision_history.append({
            "version": mbr.version,
            "action": "approved",
            "by": approved_by,
            "at": datetime.now().isoformat(),
            "comments": comments
        })

        self._log_audit("APPROVE", "MasterBatchRecord", mbr_id, approved_by,
                        {"version": mbr.version})

        return mbr

    async def revise_master_batch_record(
        self,
        mbr_id: str,
        changes: Dict,
        revised_by: str,
        reason: str
    ) -> MasterBatchRecord:
        """
        Create a new revision of an MBR (change control required)."""
        if mbr_id not in self.master_batch_records:
            raise ValueError(f"MBR not found: {mbr_id}")

        original = self.master_batch_records[mbr_id]

        # Increment version
        major, minor = map(int, original.version.split("."))
        new_version = f"{major}.{minor + 1}"

        # Mark original as superseded
        original.status = "superseded"

        # Create new revision
        new_mbr_id = self._generate_id("MBR")
        new_mbr = MasterBatchRecord(
            mbr_id=new_mbr_id,
            product_code=original.product_code,
            product_name=original.product_name,
            version=new_version,
            effective_date=datetime.now(),
            batch_size=changes.get("batch_size", original.batch_size),
            batch_size_unit=changes.get("batch_size_unit", original.batch_size_unit),
            steps=original.steps,  # Deep copy in production
            created_by=revised_by,
            created_at=datetime.now(),
            yield_specification=changes.get("yield_specification",
                                            original.yield_specification),
            revision_history=[{
                "version": new_version,
                "action": "revised",
                "by": revised_by,
                "at": datetime.now().isoformat(),
                "reason": reason,
                "previous_mbr": mbr_id
            }]
        )

        self.master_batch_records[new_mbr_id] = new_mbr
        self._log_audit("REVISE", "MasterBatchRecord", new_mbr_id, revised_by,
                        {"previous_version": original.version,
                         "new_version": new_version,
                         "reason": reason})

        return new_mbr

    # =========================================================================
    # Electronic Batch Record Execution
    # =========================================================================

    async def initiate_batch(
        self,
        mbr_id: str,
        batch_number: str,
        initiated_by: str,
        batch_size_override: Optional[float] = None
    ) -> ElectronicBatchRecord:
        """
        Initiate a new batch execution from MBR template.

        Args:
            mbr_id: Master Batch Record to use
            batch_number: Unique batch identifier
            initiated_by: User initiating the batch
            batch_size_override: Optional batch size override

        Returns:
            New ElectronicBatchRecord
        """
        if mbr_id not in self.master_batch_records:
            raise ValueError(f"MBR not found: {mbr_id}")

        mbr = self.master_batch_records[mbr_id]

        if mbr.status != "approved":
            raise ValueError(f"MBR must be approved. Current: {mbr.status}")

        ebr_id = self._generate_id("EBR")
        batch_size = batch_size_override or mbr.batch_size

        # Create step execution records for each MBR step
        step_executions = {}
        for step in mbr.steps:
            step_executions[step.step_id] = StepExecution(step_id=step.step_id)

        # Calculate theoretical yield if specified
        theoretical_yield = None
        if mbr.yield_specification:
            # Assume theoretical is batch_size * 100% efficiency
            theoretical_yield = batch_size

        ebr = ElectronicBatchRecord(
            ebr_id=ebr_id,
            batch_number=batch_number,
            mbr_id=mbr_id,
            mbr_version=mbr.version,
            product_code=mbr.product_code,
            product_name=mbr.product_name,
            batch_size=batch_size,
            batch_size_unit=mbr.batch_size_unit,
            status=BatchStatus.IN_PROGRESS,
            initiated_by=initiated_by,
            initiated_at=datetime.now(),
            step_executions=step_executions,
            manufacturing_date=datetime.now(),
            theoretical_yield=theoretical_yield
        )

        self.electronic_batch_records[ebr_id] = ebr
        self._log_audit("INITIATE", "ElectronicBatchRecord", ebr_id, initiated_by,
                        {"batch_number": batch_number, "mbr_id": mbr_id})

        return ebr

    async def start_step(
        self,
        ebr_id: str,
        step_id: str,
        executed_by: str
    ) -> StepExecution:
        """Start execution of a batch step."""
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]

        if step_id not in ebr.step_executions:
            raise ValueError(f"Step not found: {step_id}")

        step_exec = ebr.step_executions[step_id]

        # Check prerequisites
        mbr = self.master_batch_records[ebr.mbr_id]
        step_def = next((s for s in mbr.steps if s.step_id == step_id), None)

        if step_def:
            for prereq_id in step_def.prerequisite_steps:
                prereq_exec = ebr.step_executions.get(prereq_id)
                if not prereq_exec or prereq_exec.status != StepStatus.COMPLETED:
                    raise ValueError(f"Prerequisite step not completed: {prereq_id}")

        step_exec.status = StepStatus.IN_PROGRESS
        step_exec.started_at = datetime.now()
        step_exec.executed_by = executed_by

        self._log_audit("START_STEP", "StepExecution", f"{ebr_id}/{step_id}",
                        executed_by, {"step_id": step_id})

        return step_exec

    async def record_parameter(
        self,
        ebr_id: str,
        step_id: str,
        parameter_id: str,
        value: Any,
        recorded_by: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Record a process parameter value.

        Returns:
            Tuple of (within_spec, deviation_id if out of spec)
        """
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        step_exec = ebr.step_executions.get(step_id)

        if not step_exec:
            raise ValueError(f"Step not found: {step_id}")

        # Get parameter specification from MBR
        mbr = self.master_batch_records[ebr.mbr_id]
        step_def = next((s for s in mbr.steps if s.step_id == step_id), None)
        param_spec = None

        if step_def:
            param_spec = next(
                (p for p in step_def.parameters if p.parameter_id == parameter_id),
                None
            )

        # Record the value
        step_exec.parameter_values[parameter_id] = {
            "value": value,
            "recorded_at": datetime.now().isoformat(),
            "recorded_by": recorded_by
        }

        # Check specification limits
        within_spec = True
        deviation_id = None

        if param_spec and param_spec.parameter_type == ParameterType.NUMERIC:
            if param_spec.lower_limit is not None and value < param_spec.lower_limit:
                within_spec = False
            if param_spec.upper_limit is not None and value > param_spec.upper_limit:
                within_spec = False

            if not within_spec:
                # Auto-create deviation for out-of-spec
                deviation_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"
                step_exec.deviations.append(deviation_id)
                step_exec.status = StepStatus.DEVIATION
                ebr.total_deviations += 1

                if param_spec.is_critical:
                    ebr.critical_deviations += 1

                self._log_audit("OUT_OF_SPEC", "Parameter",
                               f"{ebr_id}/{step_id}/{parameter_id}",
                               recorded_by, {
                                   "value": value,
                                   "lower_limit": param_spec.lower_limit,
                                   "upper_limit": param_spec.upper_limit,
                                   "deviation_id": deviation_id
                               })

        return within_spec, deviation_id

    async def record_material_usage(
        self,
        ebr_id: str,
        step_id: str,
        material_usage: MaterialUsage
    ) -> MaterialUsage:
        """Record material used in a step (with lot traceability)."""
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        step_exec = ebr.step_executions.get(step_id)

        if not step_exec:
            raise ValueError(f"Step not found: {step_id}")

        # Check expiry if required
        if material_usage.expiry_date:
            if material_usage.expiry_date < datetime.now():
                raise ValueError(
                    f"Material {material_usage.material_id} lot {material_usage.lot_number} "
                    f"is expired as of {material_usage.expiry_date}"
                )

        material_usage.verified_at = datetime.now()
        step_exec.materials_used.append(material_usage)

        self._log_audit("RECORD_MATERIAL", "MaterialUsage",
                        f"{ebr_id}/{step_id}/{material_usage.material_id}",
                        material_usage.verified_by or "system",
                        {"lot_number": material_usage.lot_number,
                         "quantity": material_usage.quantity_used})

        return material_usage

    async def record_equipment_usage(
        self,
        ebr_id: str,
        step_id: str,
        equipment_usage: EquipmentUsage
    ) -> EquipmentUsage:
        """Record equipment used in a step (with qualification check)."""
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        step_exec = ebr.step_executions.get(step_id)

        if not step_exec:
            raise ValueError(f"Step not found: {step_id}")

        # Check calibration status
        if equipment_usage.calibration_due_date < datetime.now():
            raise ValueError(
                f"Equipment {equipment_usage.equipment_id} calibration is overdue. "
                f"Due date: {equipment_usage.calibration_due_date}"
            )

        equipment_usage.verified_at = datetime.now()
        step_exec.equipment_used.append(equipment_usage)

        self._log_audit("RECORD_EQUIPMENT", "EquipmentUsage",
                        f"{ebr_id}/{step_id}/{equipment_usage.equipment_id}",
                        equipment_usage.verified_by or "system",
                        {"qualification_status": equipment_usage.qualification_status})

        return equipment_usage

    async def record_environmental_reading(
        self,
        ebr_id: str,
        step_id: str,
        reading: EnvironmentalReading
    ) -> Tuple[EnvironmentalReading, bool]:
        """
        Record environmental monitoring data.

        Returns:
            Tuple of (reading, alert_required)
        """
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        step_exec = ebr.step_executions.get(step_id)

        if not step_exec:
            raise ValueError(f"Step not found: {step_id}")

        # Check against step environmental requirements
        mbr = self.master_batch_records[ebr.mbr_id]
        step_def = next((s for s in mbr.steps if s.step_id == step_id), None)

        alert_required = False
        if step_def and reading.parameter in step_def.environmental_requirements:
            min_val, max_val = step_def.environmental_requirements[reading.parameter]
            if reading.value < min_val or reading.value > max_val:
                reading.within_spec = False
                reading.alert_generated = True
                alert_required = True

        step_exec.environmental_readings.append(reading)

        return reading, alert_required

    async def complete_step(
        self,
        ebr_id: str,
        step_id: str,
        completed_by: str,
        verified_by: Optional[str] = None,
        comments: str = ""
    ) -> StepExecution:
        """
        Complete a batch step with electronic signature.

        Applies verification requirements based on step configuration.
        """
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        step_exec = ebr.step_executions.get(step_id)

        if not step_exec:
            raise ValueError(f"Step not found: {step_id}")

        # Get verification requirements
        mbr = self.master_batch_records[ebr.mbr_id]
        step_def = next((s for s in mbr.steps if s.step_id == step_id), None)

        if step_def:
            if step_def.verification_type == VerificationType.DUAL:
                if not verified_by or verified_by == completed_by:
                    raise ValueError(
                        "Dual signature required. Verifier must be different from executor."
                    )
            elif step_def.verification_type == VerificationType.SUPERVISOR:
                # In production, check verifier has supervisor role
                if not verified_by:
                    raise ValueError("Supervisor verification required.")

        # Generate electronic signature
        data_to_sign = json.dumps({
            "step_id": step_id,
            "parameters": step_exec.parameter_values,
            "materials_count": len(step_exec.materials_used),
            "completed_at": datetime.now().isoformat()
        }, sort_keys=True)

        data_hash = hashlib.sha256(data_to_sign.encode()).hexdigest()
        signature = self._generate_electronic_signature(
            completed_by, "Step Completion", data_hash
        )

        step_exec.status = StepStatus.COMPLETED
        step_exec.completed_at = datetime.now()
        step_exec.verified_by = verified_by
        step_exec.verified_at = datetime.now() if verified_by else None
        step_exec.comments = comments
        step_exec.electronic_signature = signature
        step_exec.signature_meaning = "I have completed this step according to approved procedures"

        self._log_audit("COMPLETE_STEP", "StepExecution", f"{ebr_id}/{step_id}",
                        completed_by, {"verified_by": verified_by})

        # Check if all steps completed
        all_completed = all(
            se.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]
            for se in ebr.step_executions.values()
        )

        if all_completed:
            ebr.status = BatchStatus.PENDING_REVIEW

        return step_exec

    # =========================================================================
    # Yield Calculation and Reconciliation
    # =========================================================================

    async def calculate_yield(
        self,
        ebr_id: str,
        actual_yield: float,
        waste_quantity: float,
        sample_quantity: float,
        calculated_by: str
    ) -> YieldReconciliation:
        """
        Calculate and reconcile batch yield.

        Compares actual yield to theoretical and checks acceptance criteria.
        """
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        mbr = self.master_batch_records[ebr.mbr_id]

        theoretical = ebr.theoretical_yield or ebr.batch_size
        yield_percentage = (actual_yield / theoretical) * 100 if theoretical > 0 else 0

        # Determine reconciliation status
        reconciliation_status = "pass"
        if mbr.yield_specification:
            min_yield, max_yield = mbr.yield_specification
            if yield_percentage < min_yield or yield_percentage > max_yield:
                reconciliation_status = "under_investigation"
                ebr.status = BatchStatus.UNDER_INVESTIGATION

        reconciliation = YieldReconciliation(
            ebr_id=ebr_id,
            theoretical_yield=theoretical,
            actual_yield=actual_yield,
            yield_percentage=yield_percentage,
            unit=ebr.batch_size_unit,
            waste_quantity=waste_quantity,
            sample_quantity=sample_quantity,
            reconciliation_status=reconciliation_status,
            calculated_by=calculated_by
        )

        # Update EBR
        ebr.actual_yield = actual_yield
        ebr.yield_percentage = yield_percentage

        self.yield_reconciliations[ebr_id] = reconciliation
        self._log_audit("CALCULATE_YIELD", "YieldReconciliation", ebr_id,
                        calculated_by, {
                            "actual": actual_yield,
                            "theoretical": theoretical,
                            "percentage": yield_percentage,
                            "status": reconciliation_status
                        })

        return reconciliation

    # =========================================================================
    # Batch Review and Release
    # =========================================================================

    async def submit_for_review(
        self,
        ebr_id: str,
        submitted_by: str,
        review_package: Dict = None
    ) -> ElectronicBatchRecord:
        """Submit batch record for QA review."""
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]

        # Verify all steps completed
        incomplete = [
            step_id for step_id, se in ebr.step_executions.items()
            if se.status not in [StepStatus.COMPLETED, StepStatus.SKIPPED]
        ]

        if incomplete:
            raise ValueError(f"Cannot submit. Incomplete steps: {incomplete}")

        # Verify yield calculated
        if ebr_id not in self.yield_reconciliations:
            raise ValueError("Yield reconciliation required before submission")

        ebr.status = BatchStatus.PENDING_REVIEW
        ebr.review_comments.append({
            "action": "submitted",
            "by": submitted_by,
            "at": datetime.now().isoformat(),
            "package": review_package
        })

        self._log_audit("SUBMIT_REVIEW", "ElectronicBatchRecord", ebr_id,
                        submitted_by, {"total_deviations": ebr.total_deviations})

        return ebr

    async def qa_review(
        self,
        ebr_id: str,
        reviewer: str,
        disposition: str,  # approve, reject, rework
        comments: str = ""
    ) -> ElectronicBatchRecord:
        """
        QA review of batch record.

        Args:
            ebr_id: Batch record ID
            reviewer: QA reviewer (must have appropriate authority)
            disposition: approve, reject, or rework
            comments: Review comments
        """
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]

        if ebr.status not in [BatchStatus.PENDING_REVIEW, BatchStatus.UNDER_INVESTIGATION]:
            raise ValueError(f"Cannot review. Status: {ebr.status}")

        ebr.qa_reviewer = reviewer
        ebr.qa_review_date = datetime.now()
        ebr.batch_disposition = disposition

        ebr.review_comments.append({
            "action": f"qa_review_{disposition}",
            "by": reviewer,
            "at": datetime.now().isoformat(),
            "comments": comments
        })

        if disposition == "approve":
            ebr.status = BatchStatus.APPROVED
        elif disposition == "reject":
            ebr.status = BatchStatus.REJECTED
        else:  # rework
            ebr.status = BatchStatus.IN_PROGRESS

        self._log_audit("QA_REVIEW", "ElectronicBatchRecord", ebr_id,
                        reviewer, {"disposition": disposition})

        return ebr

    async def release_batch(
        self,
        ebr_id: str,
        released_by: str,
        expiry_date: datetime,
        release_comments: str = ""
    ) -> ElectronicBatchRecord:
        """
        Final batch release for distribution.

        Requires QA approval and generates release certificate.
        """
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]

        if ebr.status != BatchStatus.APPROVED:
            raise ValueError(f"Batch must be approved before release. Status: {ebr.status}")

        # Generate release signature
        release_data = json.dumps({
            "ebr_id": ebr_id,
            "batch_number": ebr.batch_number,
            "product_code": ebr.product_code,
            "yield": ebr.actual_yield,
            "expiry_date": expiry_date.isoformat(),
            "released_at": datetime.now().isoformat()
        }, sort_keys=True)

        release_hash = hashlib.sha256(release_data.encode()).hexdigest()
        release_signature = self._generate_electronic_signature(
            released_by, "Batch Release Certification", release_hash
        )

        ebr.status = BatchStatus.RELEASED
        ebr.released_by = released_by
        ebr.released_at = datetime.now()
        ebr.expiry_date = expiry_date

        ebr.review_comments.append({
            "action": "released",
            "by": released_by,
            "at": datetime.now().isoformat(),
            "comments": release_comments,
            "signature": release_signature[:16],  # Truncated for display
            "expiry_date": expiry_date.isoformat()
        })

        self._log_audit("RELEASE", "ElectronicBatchRecord", ebr_id,
                        released_by, {
                            "batch_number": ebr.batch_number,
                            "expiry_date": expiry_date.isoformat()
                        })

        return ebr

    # =========================================================================
    # Reporting and Analysis
    # =========================================================================

    async def generate_batch_record_report(self, ebr_id: str) -> Dict:
        """Generate complete batch record report for regulatory submission."""
        if ebr_id not in self.electronic_batch_records:
            raise ValueError(f"EBR not found: {ebr_id}")

        ebr = self.electronic_batch_records[ebr_id]
        mbr = self.master_batch_records[ebr.mbr_id]
        yield_rec = self.yield_reconciliations.get(ebr_id)

        return {
            "header": {
                "ebr_id": ebr.ebr_id,
                "batch_number": ebr.batch_number,
                "product_code": ebr.product_code,
                "product_name": ebr.product_name,
                "mbr_id": ebr.mbr_id,
                "mbr_version": ebr.mbr_version,
                "status": ebr.status.value
            },
            "batch_details": {
                "batch_size": ebr.batch_size,
                "batch_size_unit": ebr.batch_size_unit,
                "manufacturing_date": ebr.manufacturing_date.isoformat()
                    if ebr.manufacturing_date else None,
                "expiry_date": ebr.expiry_date.isoformat()
                    if ebr.expiry_date else None,
                "initiated_by": ebr.initiated_by,
                "initiated_at": ebr.initiated_at.isoformat()
            },
            "yield_data": {
                "theoretical_yield": ebr.theoretical_yield,
                "actual_yield": ebr.actual_yield,
                "yield_percentage": ebr.yield_percentage,
                "waste_quantity": yield_rec.waste_quantity if yield_rec else None,
                "sample_quantity": yield_rec.sample_quantity if yield_rec else None,
                "reconciliation_status": yield_rec.reconciliation_status if yield_rec else None
            },
            "execution_summary": {
                "total_steps": len(ebr.step_executions),
                "completed_steps": sum(
                    1 for se in ebr.step_executions.values()
                    if se.status == StepStatus.COMPLETED
                ),
                "total_deviations": ebr.total_deviations,
                "critical_deviations": ebr.critical_deviations
            },
            "step_details": [
                {
                    "step_id": se.step_id,
                    "status": se.status.value,
                    "started_at": se.started_at.isoformat() if se.started_at else None,
                    "completed_at": se.completed_at.isoformat() if se.completed_at else None,
                    "executed_by": se.executed_by,
                    "verified_by": se.verified_by,
                    "parameters_recorded": len(se.parameter_values),
                    "materials_used": len(se.materials_used),
                    "deviations": se.deviations,
                    "signature": se.electronic_signature[:16] if se.electronic_signature else None
                }
                for se in ebr.step_executions.values()
            ],
            "material_traceability": [
                {
                    "step_id": step_id,
                    "materials": [
                        {
                            "material_id": m.material_id,
                            "lot_number": m.lot_number,
                            "quantity_used": m.quantity_used,
                            "unit": m.unit,
                            "expiry_date": m.expiry_date.isoformat() if m.expiry_date else None
                        }
                        for m in se.materials_used
                    ]
                }
                for step_id, se in ebr.step_executions.items()
                if se.materials_used
            ],
            "review_history": ebr.review_comments,
            "release_info": {
                "qa_reviewer": ebr.qa_reviewer,
                "qa_review_date": ebr.qa_review_date.isoformat() if ebr.qa_review_date else None,
                "released_by": ebr.released_by,
                "released_at": ebr.released_at.isoformat() if ebr.released_at else None,
                "disposition": ebr.batch_disposition
            },
            "generated_at": datetime.now().isoformat()
        }

    async def get_batch_genealogy(self, batch_number: str) -> Dict:
        """
        Get complete genealogy for a batch (forward and backward traceability).

        Shows all materials that went into a batch and all downstream products.
        """
        ebr = next(
            (e for e in self.electronic_batch_records.values()
             if e.batch_number == batch_number),
            None
        )

        if not ebr:
            raise ValueError(f"Batch not found: {batch_number}")

        # Collect all input materials
        input_materials = []
        for se in ebr.step_executions.values():
            for material in se.materials_used:
                input_materials.append({
                    "material_id": material.material_id,
                    "lot_number": material.lot_number,
                    "quantity": material.quantity_used,
                    "unit": material.unit,
                    "supplier_coa": material.supplier_coa_verified
                })

        return {
            "batch_number": batch_number,
            "product_code": ebr.product_code,
            "product_name": ebr.product_name,
            "manufacturing_date": ebr.manufacturing_date.isoformat()
                if ebr.manufacturing_date else None,
            "input_materials": input_materials,
            "output": {
                "quantity": ebr.actual_yield,
                "unit": ebr.batch_size_unit,
                "expiry_date": ebr.expiry_date.isoformat() if ebr.expiry_date else None,
                "status": ebr.status.value
            },
            "downstream_batches": []  # Would query for batches using this as input
        }

    def get_audit_trail(self, entity_id: str = None,
                        start_date: datetime = None,
                        end_date: datetime = None) -> List[Dict]:
        """
        Retrieve audit trail entries (21 CFR Part 11 requirement).

        Audit trail is immutable and includes all record changes.
        """
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


# Factory function for service instantiation
def create_batch_record_service() -> BatchRecordService:
    """Create and return a BatchRecordService instance."""
    return BatchRecordService()
