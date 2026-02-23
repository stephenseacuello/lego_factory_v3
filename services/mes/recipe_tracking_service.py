"""
Recipe Version Control & Tracking Service
==========================================
Manages recipe versions, approval workflows, production locks,
and effectiveness tracking for manufacturing processes.

Partial DB-backed: transactional data (lot links, audit trail,
effectiveness) persisted via SQLAlchemy; recipe definitions/versions/
approvals kept in memory.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
import copy
import json
import difflib


class RecipeStatus(str, Enum):
    """Recipe lifecycle status."""
    DRAFT = 'draft'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    ACTIVE = 'active'
    SUPERSEDED = 'superseded'
    OBSOLETE = 'obsolete'
    REJECTED = 'rejected'


class ApprovalAction(str, Enum):
    """Approval workflow actions."""
    SUBMIT = 'submit'
    APPROVE = 'approve'
    REJECT = 'reject'
    REVISE = 'revise'
    ACTIVATE = 'activate'
    DEACTIVATE = 'deactivate'


class LockStatus(str, Enum):
    """Recipe lock status during production."""
    UNLOCKED = 'unlocked'
    LOCKED = 'locked'
    LOCKED_FOR_EDIT = 'locked_for_edit'


@dataclass
class RecipeParameter:
    """Individual recipe parameter."""
    param_id: str
    name: str
    value: Any
    unit: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_critical: bool = False
    description: str = ''


@dataclass
class RecipeVersion:
    """A specific version of a recipe."""
    version_id: str
    recipe_id: str
    version_number: int
    status: RecipeStatus
    parameters: Dict[str, RecipeParameter]
    created_by: str
    created_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    superseded_date: Optional[datetime] = None
    change_description: str = ''
    change_reason: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version_id': self.version_id,
            'recipe_id': self.recipe_id,
            'version_number': self.version_number,
            'status': self.status.value,
            'parameters': {
                k: {
                    'name': v.name,
                    'value': v.value,
                    'unit': v.unit,
                    'is_critical': v.is_critical,
                }
                for k, v in self.parameters.items()
            },
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'change_description': self.change_description,
        }


@dataclass
class Recipe:
    """Master recipe record."""
    recipe_id: str
    name: str
    product_id: str
    machine_type: str
    description: str
    current_version: Optional[int] = None
    versions: Dict[int, RecipeVersion] = field(default_factory=dict)
    lock_status: LockStatus = LockStatus.UNLOCKED
    locked_by_job_id: Optional[str] = None
    locked_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuditEntryLocal:
    """Recipe audit trail entry (local dataclass, not DB model)."""
    audit_id: str
    recipe_id: str
    version_number: int
    action: str
    actor: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    lot_id: Optional[str] = None
    job_id: Optional[str] = None


@dataclass
class RecipeEffectiveness:
    """Recipe effectiveness metrics."""
    recipe_id: str
    version_number: int
    lots_produced: int
    total_quantity: int
    good_quantity: int
    reject_quantity: int
    yield_pct: float
    avg_cycle_time: float
    quality_score: float
    period_start: datetime
    period_end: datetime


@dataclass
class ApprovalRequest:
    """Recipe approval request."""
    request_id: str
    recipe_id: str
    version_number: int
    requested_by: str
    requested_at: datetime
    status: str  # 'pending', 'approved', 'rejected'
    approvers: List[str]
    approved_by: List[str] = field(default_factory=list)
    rejected_by: Optional[str] = None
    rejection_reason: str = ''
    comments: List[Dict[str, Any]] = field(default_factory=list)


class RecipeTrackingService:
    """
    Service for recipe version control and tracking.

    Features:
    - Full version history with diff comparison
    - Recipe lock during production run
    - Approval workflow for recipe changes
    - Audit trail linking recipe version to each produced lot
    - Recipe effectiveness tracking (quality yield by version)

    Storage strategy:
    - In-memory: recipe definitions, versions, approvals (config/workflow)
    - DB-backed: lot-recipe links (RecipeRun), audit trail (RecipeAuditEntry),
      effectiveness data (RecipeRun effectiveness columns)
    """

    def __init__(self, session=None):
        self.session = session
        self._recipes: Dict[str, Recipe] = {}
        self._approval_requests: Dict[str, ApprovalRequest] = {}
        self._required_approvers: List[str] = ['quality_manager', 'process_engineer']

    # =========================================================================
    # Recipe Management
    # =========================================================================

    def create_recipe(self, name: str, product_id: str, machine_type: str,
                      description: str, parameters: List[Dict[str, Any]],
                      created_by: str) -> Recipe:
        """Create a new recipe with initial version."""
        recipe_id = f"RCP-{uuid.uuid4().hex[:8].upper()}"

        # Create parameters
        params = {}
        for p in parameters:
            param = RecipeParameter(
                param_id=f"{recipe_id}-P{len(params)+1:03d}",
                name=p['name'],
                value=p['value'],
                unit=p.get('unit', ''),
                min_value=p.get('min_value'),
                max_value=p.get('max_value'),
                is_critical=p.get('is_critical', False),
                description=p.get('description', ''),
            )
            params[param.param_id] = param

        # Create initial version
        version = RecipeVersion(
            version_id=f"{recipe_id}-V001",
            recipe_id=recipe_id,
            version_number=1,
            status=RecipeStatus.DRAFT,
            parameters=params,
            created_by=created_by,
            created_at=datetime.utcnow(),
            change_description='Initial recipe creation',
        )

        recipe = Recipe(
            recipe_id=recipe_id,
            name=name,
            product_id=product_id,
            machine_type=machine_type,
            description=description,
            current_version=None,  # Not active until approved
            versions={1: version},
        )

        self._recipes[recipe_id] = recipe
        self._add_audit_entry(recipe_id, 1, 'created', created_by, {'action': 'recipe_created'})

        return recipe

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Get a recipe by ID."""
        return self._recipes.get(recipe_id)

    def get_active_version(self, recipe_id: str) -> Optional[RecipeVersion]:
        """Get the currently active version of a recipe."""
        recipe = self._recipes.get(recipe_id)
        if not recipe or not recipe.current_version:
            return None
        return recipe.versions.get(recipe.current_version)

    def create_new_version(self, recipe_id: str, parameter_changes: Dict[str, Any],
                           change_description: str, change_reason: str,
                           created_by: str) -> Optional[RecipeVersion]:
        """Create a new version of an existing recipe."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return None

        # Get latest version
        latest_version_num = max(recipe.versions.keys())
        latest_version = recipe.versions[latest_version_num]

        # Copy parameters and apply changes
        new_params = copy.deepcopy(latest_version.parameters)
        for param_id, new_value in parameter_changes.items():
            if param_id in new_params:
                new_params[param_id].value = new_value

        new_version_num = latest_version_num + 1
        new_version = RecipeVersion(
            version_id=f"{recipe_id}-V{new_version_num:03d}",
            recipe_id=recipe_id,
            version_number=new_version_num,
            status=RecipeStatus.DRAFT,
            parameters=new_params,
            created_by=created_by,
            created_at=datetime.utcnow(),
            change_description=change_description,
            change_reason=change_reason,
        )

        recipe.versions[new_version_num] = new_version
        recipe.updated_at = datetime.utcnow()

        self._add_audit_entry(
            recipe_id, new_version_num, 'version_created', created_by,
            {'changes': parameter_changes, 'reason': change_reason}
        )

        return new_version

    # =========================================================================
    # Version Comparison
    # =========================================================================

    def compare_versions(self, recipe_id: str, version_a: int,
                         version_b: int) -> Dict[str, Any]:
        """Compare two recipe versions and show differences."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        v_a = recipe.versions.get(version_a)
        v_b = recipe.versions.get(version_b)

        if not v_a or not v_b:
            return {'error': 'Version not found'}

        differences = []
        all_params = set(v_a.parameters.keys()) | set(v_b.parameters.keys())

        for param_id in all_params:
            param_a = v_a.parameters.get(param_id)
            param_b = v_b.parameters.get(param_id)

            if param_a and not param_b:
                differences.append({
                    'param_id': param_id,
                    'name': param_a.name,
                    'change_type': 'removed',
                    'old_value': param_a.value,
                    'new_value': None,
                })
            elif param_b and not param_a:
                differences.append({
                    'param_id': param_id,
                    'name': param_b.name,
                    'change_type': 'added',
                    'old_value': None,
                    'new_value': param_b.value,
                })
            elif param_a.value != param_b.value:
                differences.append({
                    'param_id': param_id,
                    'name': param_a.name,
                    'change_type': 'modified',
                    'old_value': param_a.value,
                    'new_value': param_b.value,
                    'is_critical': param_a.is_critical or param_b.is_critical,
                })

        return {
            'recipe_id': recipe_id,
            'version_a': version_a,
            'version_b': version_b,
            'differences': differences,
            'total_changes': len(differences),
            'critical_changes': len([d for d in differences if d.get('is_critical')]),
        }

    def get_version_history(self, recipe_id: str) -> List[Dict[str, Any]]:
        """Get full version history for a recipe."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return []

        history = []
        for version_num in sorted(recipe.versions.keys()):
            version = recipe.versions[version_num]
            history.append({
                'version_number': version_num,
                'version_id': version.version_id,
                'status': version.status.value,
                'created_by': version.created_by,
                'created_at': version.created_at.isoformat(),
                'approved_by': version.approved_by,
                'approved_at': version.approved_at.isoformat() if version.approved_at else None,
                'change_description': version.change_description,
                'is_current': recipe.current_version == version_num,
            })

        return history

    # =========================================================================
    # Approval Workflow
    # =========================================================================

    def submit_for_approval(self, recipe_id: str, version_number: int,
                            submitted_by: str, approvers: List[str] = None) -> Dict[str, Any]:
        """Submit a recipe version for approval."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        version = recipe.versions.get(version_number)
        if not version:
            return {'error': 'Version not found'}

        if version.status != RecipeStatus.DRAFT:
            return {'error': f'Cannot submit version in status {version.status.value}'}

        approvers = approvers or self._required_approvers

        request = ApprovalRequest(
            request_id=f"APR-{uuid.uuid4().hex[:8].upper()}",
            recipe_id=recipe_id,
            version_number=version_number,
            requested_by=submitted_by,
            requested_at=datetime.utcnow(),
            status='pending',
            approvers=approvers,
        )

        version.status = RecipeStatus.PENDING_APPROVAL
        self._approval_requests[request.request_id] = request

        self._add_audit_entry(
            recipe_id, version_number, 'submitted_for_approval', submitted_by,
            {'approvers': approvers}
        )

        return {
            'status': 'submitted',
            'request_id': request.request_id,
            'approvers_required': approvers,
        }

    def approve_version(self, request_id: str, approver: str,
                        comments: str = '') -> Dict[str, Any]:
        """Approve a recipe version."""
        request = self._approval_requests.get(request_id)
        if not request:
            return {'error': 'Approval request not found'}

        if request.status != 'pending':
            return {'error': f'Request already {request.status}'}

        if approver not in request.approvers:
            return {'error': 'Not an authorized approver'}

        if approver in request.approved_by:
            return {'error': 'Already approved by this user'}

        request.approved_by.append(approver)
        if comments:
            request.comments.append({
                'user': approver,
                'action': 'approved',
                'comment': comments,
                'timestamp': datetime.utcnow().isoformat(),
            })

        recipe = self._recipes.get(request.recipe_id)
        version = recipe.versions.get(request.version_number)

        # Check if all required approvals received
        if set(request.approved_by) >= set(request.approvers):
            request.status = 'approved'
            version.status = RecipeStatus.APPROVED
            version.approved_by = ', '.join(request.approved_by)
            version.approved_at = datetime.utcnow()

            self._add_audit_entry(
                request.recipe_id, request.version_number, 'approved', approver,
                {'all_approvers': request.approved_by}
            )

            return {
                'status': 'fully_approved',
                'approved_by': request.approved_by,
                'version_status': version.status.value,
            }

        return {
            'status': 'partially_approved',
            'approved_by': request.approved_by,
            'remaining_approvers': [a for a in request.approvers if a not in request.approved_by],
        }

    def reject_version(self, request_id: str, rejector: str,
                       reason: str) -> Dict[str, Any]:
        """Reject a recipe version."""
        request = self._approval_requests.get(request_id)
        if not request:
            return {'error': 'Approval request not found'}

        if request.status != 'pending':
            return {'error': f'Request already {request.status}'}

        request.status = 'rejected'
        request.rejected_by = rejector
        request.rejection_reason = reason

        recipe = self._recipes.get(request.recipe_id)
        version = recipe.versions.get(request.version_number)
        version.status = RecipeStatus.REJECTED

        self._add_audit_entry(
            request.recipe_id, request.version_number, 'rejected', rejector,
            {'reason': reason}
        )

        return {
            'status': 'rejected',
            'rejected_by': rejector,
            'reason': reason,
        }

    def activate_version(self, recipe_id: str, version_number: int,
                         activated_by: str) -> Dict[str, Any]:
        """Activate an approved recipe version for production use."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        version = recipe.versions.get(version_number)
        if not version:
            return {'error': 'Version not found'}

        if version.status != RecipeStatus.APPROVED:
            return {'error': f'Cannot activate version in status {version.status.value}'}

        if recipe.lock_status == LockStatus.LOCKED:
            return {'error': 'Recipe is locked for production, cannot change active version'}

        # Supersede current active version
        if recipe.current_version:
            old_version = recipe.versions[recipe.current_version]
            old_version.status = RecipeStatus.SUPERSEDED
            old_version.superseded_date = datetime.utcnow()

        # Activate new version
        version.status = RecipeStatus.ACTIVE
        version.effective_date = datetime.utcnow()
        recipe.current_version = version_number
        recipe.updated_at = datetime.utcnow()

        self._add_audit_entry(
            recipe_id, version_number, 'activated', activated_by,
            {'previous_version': recipe.current_version}
        )

        return {
            'status': 'activated',
            'recipe_id': recipe_id,
            'version_number': version_number,
            'effective_date': version.effective_date.isoformat(),
        }

    # =========================================================================
    # Production Lock
    # =========================================================================

    def lock_for_production(self, recipe_id: str, job_id: str) -> Dict[str, Any]:
        """Lock a recipe for a production run."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        if recipe.lock_status == LockStatus.LOCKED:
            return {
                'error': 'Recipe already locked',
                'locked_by_job': recipe.locked_by_job_id,
            }

        if not recipe.current_version:
            return {'error': 'No active version available'}

        recipe.lock_status = LockStatus.LOCKED
        recipe.locked_by_job_id = job_id
        recipe.locked_at = datetime.utcnow()

        self._add_audit_entry(
            recipe_id, recipe.current_version, 'locked', 'system',
            {'job_id': job_id}
        )

        return {
            'status': 'locked',
            'recipe_id': recipe_id,
            'version_number': recipe.current_version,
            'job_id': job_id,
            'locked_at': recipe.locked_at.isoformat(),
        }

    def unlock_recipe(self, recipe_id: str, job_id: str) -> Dict[str, Any]:
        """Unlock a recipe after production run completes."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        if recipe.lock_status != LockStatus.LOCKED:
            return {'error': 'Recipe is not locked'}

        if recipe.locked_by_job_id != job_id:
            return {
                'error': 'Recipe locked by different job',
                'locked_by': recipe.locked_by_job_id,
            }

        recipe.lock_status = LockStatus.UNLOCKED
        recipe.locked_by_job_id = None
        recipe.locked_at = None

        self._add_audit_entry(
            recipe_id, recipe.current_version, 'unlocked', 'system',
            {'job_id': job_id}
        )

        return {
            'status': 'unlocked',
            'recipe_id': recipe_id,
        }

    def get_locked_recipes(self) -> List[Dict[str, Any]]:
        """Get all currently locked recipes."""
        locked = []
        for recipe in self._recipes.values():
            if recipe.lock_status == LockStatus.LOCKED:
                locked.append({
                    'recipe_id': recipe.recipe_id,
                    'name': recipe.name,
                    'version': recipe.current_version,
                    'locked_by_job': recipe.locked_by_job_id,
                    'locked_at': recipe.locked_at.isoformat() if recipe.locked_at else None,
                })
        return locked

    # =========================================================================
    # Lot Linkage & Audit Trail (DB-backed)
    # =========================================================================

    def link_lot_to_recipe(self, lot_id: str, recipe_id: str,
                           job_id: str, quantity: int) -> Dict[str, Any]:
        """Link a production lot to the recipe version used."""
        from models.mes.recipe_run import RecipeRun as RecipeRunModel

        recipe = self._recipes.get(recipe_id)
        if not recipe or not recipe.current_version:
            return {'error': 'Recipe or active version not found'}

        version = recipe.versions[recipe.current_version]

        run = RecipeRunModel(
            lot_id=lot_id,
            recipe_id=recipe_id,
            version_number=recipe.current_version,
            version_id=version.version_id,
            job_id=job_id,
            quantity=quantity,
            parameters_snapshot={
                k: {'name': v.name, 'value': v.value, 'unit': v.unit}
                for k, v in version.parameters.items()
            },
        )
        self.session.add(run)
        self.session.flush()

        self._add_audit_entry(
            recipe_id, recipe.current_version, 'lot_linked', 'system',
            {'lot_id': lot_id, 'job_id': job_id, 'quantity': quantity},
            lot_id=lot_id, job_id=job_id
        )

        return run.to_dict()

    def get_lot_recipe_info(self, lot_id: str) -> Optional[Dict[str, Any]]:
        """Get recipe information for a specific lot."""
        from models.mes.recipe_run import RecipeRun as RecipeRunModel

        run = self.session.query(RecipeRunModel).filter(
            RecipeRunModel.lot_id == lot_id
        ).first()
        return run.to_dict() if run else None

    def get_lots_by_recipe_version(self, recipe_id: str,
                                    version_number: int) -> List[Dict[str, Any]]:
        """Get all lots produced with a specific recipe version."""
        from models.mes.recipe_run import RecipeRun as RecipeRunModel

        runs = self.session.query(RecipeRunModel).filter(
            RecipeRunModel.recipe_id == recipe_id,
            RecipeRunModel.version_number == version_number,
        ).all()
        return [r.to_dict() for r in runs]

    def get_audit_trail(self, recipe_id: str = None,
                        start_date: datetime = None,
                        end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get audit trail entries."""
        from models.mes.recipe_run import RecipeAuditEntry as AuditEntryModel

        query = self.session.query(AuditEntryModel)
        if recipe_id:
            query = query.filter(AuditEntryModel.recipe_id == recipe_id)
        if start_date:
            query = query.filter(AuditEntryModel.created_at >= start_date)
        if end_date:
            query = query.filter(AuditEntryModel.created_at <= end_date)
        entries = query.order_by(AuditEntryModel.created_at.desc()).all()
        return [e.to_dict() for e in entries]

    def _add_audit_entry(self, recipe_id: str, version_number: int,
                         action: str, actor: str, details: Dict[str, Any],
                         lot_id: str = None, job_id: str = None):
        """Add an entry to the audit trail (persisted to DB)."""
        from models.mes.recipe_run import RecipeAuditEntry as AuditEntryModel

        entry = AuditEntryModel(
            recipe_id=recipe_id,
            version_number=version_number,
            action=action,
            actor=actor,
            details=details,
            lot_id=lot_id,
            job_id=job_id,
        )
        self.session.add(entry)
        self.session.flush()

    # =========================================================================
    # Recipe Effectiveness Tracking (DB-backed)
    # =========================================================================

    def record_production_result(self, lot_id: str, good_quantity: int,
                                  reject_quantity: int, cycle_time: float,
                                  quality_score: float):
        """Record production result for effectiveness tracking."""
        from models.mes.recipe_run import RecipeRun as RecipeRunModel

        run = self.session.query(RecipeRunModel).filter(
            RecipeRunModel.lot_id == lot_id
        ).first()
        if not run:
            return {'error': 'Lot not linked to recipe'}

        run.good_quantity = good_quantity
        run.reject_quantity = reject_quantity
        run.cycle_time = cycle_time
        run.quality_score = quality_score
        self.session.flush()

        return {
            'status': 'recorded',
            'key': f"{run.recipe_id}:{run.version_number}",
        }

    def get_recipe_effectiveness(self, recipe_id: str,
                                  version_number: int = None,
                                  days: int = 30) -> RecipeEffectiveness:
        """Calculate recipe effectiveness metrics."""
        from models.mes.recipe_run import RecipeRun as RecipeRunModel

        if version_number:
            versions = [version_number]
        else:
            recipe = self._recipes.get(recipe_id)
            versions = list(recipe.versions.keys()) if recipe else []

        cutoff = datetime.utcnow() - timedelta(days=days)

        for ver in versions:
            query = self.session.query(RecipeRunModel).filter(
                RecipeRunModel.recipe_id == recipe_id,
                RecipeRunModel.version_number == ver,
                RecipeRunModel.good_quantity.isnot(None),
                RecipeRunModel.created_at >= cutoff,
            )
            runs = query.all()

            if not runs:
                continue

            total_good = sum(r.good_quantity for r in runs)
            total_reject = sum(r.reject_quantity or 0 for r in runs)
            total_qty = total_good + total_reject

            return RecipeEffectiveness(
                recipe_id=recipe_id,
                version_number=ver,
                lots_produced=len(runs),
                total_quantity=total_qty,
                good_quantity=total_good,
                reject_quantity=total_reject,
                yield_pct=round(total_good / total_qty * 100, 2) if total_qty > 0 else 0,
                avg_cycle_time=round(
                    sum(r.cycle_time for r in runs if r.cycle_time is not None) / len(runs), 2
                ) if runs else 0,
                quality_score=round(
                    sum(r.quality_score for r in runs if r.quality_score is not None) / len(runs), 2
                ) if runs else 0,
                period_start=cutoff,
                period_end=datetime.utcnow(),
            )

        return RecipeEffectiveness(
            recipe_id=recipe_id,
            version_number=version_number or 0,
            lots_produced=0,
            total_quantity=0,
            good_quantity=0,
            reject_quantity=0,
            yield_pct=0,
            avg_cycle_time=0,
            quality_score=0,
            period_start=cutoff,
            period_end=datetime.utcnow(),
        )

    def compare_version_effectiveness(self, recipe_id: str,
                                       days: int = 30) -> Dict[str, Any]:
        """Compare effectiveness across recipe versions."""
        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        comparisons = []
        for version_num in recipe.versions:
            eff = self.get_recipe_effectiveness(recipe_id, version_num, days)
            if eff.lots_produced > 0:
                comparisons.append({
                    'version_number': version_num,
                    'status': recipe.versions[version_num].status.value,
                    'lots_produced': eff.lots_produced,
                    'yield_pct': eff.yield_pct,
                    'avg_cycle_time': eff.avg_cycle_time,
                    'quality_score': eff.quality_score,
                })

        best_yield = max(comparisons, key=lambda x: x['yield_pct']) if comparisons else None

        return {
            'recipe_id': recipe_id,
            'period_days': days,
            'versions_analyzed': len(comparisons),
            'comparisons': comparisons,
            'best_yield_version': best_yield['version_number'] if best_yield else None,
            'current_version': recipe.current_version,
        }

    # =========================================================================
    # Recipe Search & Reports
    # =========================================================================

    def search_recipes(self, product_id: str = None, machine_type: str = None,
                       status: str = None) -> List[Dict[str, Any]]:
        """Search recipes by criteria."""
        results = []
        for recipe in self._recipes.values():
            if product_id and recipe.product_id != product_id:
                continue
            if machine_type and recipe.machine_type != machine_type:
                continue

            active_version = None
            if recipe.current_version:
                active_version = recipe.versions[recipe.current_version]
                if status and active_version.status.value != status:
                    continue

            results.append({
                'recipe_id': recipe.recipe_id,
                'name': recipe.name,
                'product_id': recipe.product_id,
                'machine_type': recipe.machine_type,
                'current_version': recipe.current_version,
                'total_versions': len(recipe.versions),
                'lock_status': recipe.lock_status.value,
                'status': active_version.status.value if active_version else 'no_active_version',
            })

        return results

    def get_recipe_summary(self, recipe_id: str) -> Dict[str, Any]:
        """Get comprehensive recipe summary."""
        from models.mes.recipe_run import RecipeAuditEntry as AuditEntryModel

        recipe = self._recipes.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        active_version = self.get_active_version(recipe_id)
        effectiveness = self.get_recipe_effectiveness(recipe_id)

        # Query audit trail count and last entry from DB
        audit_count = self.session.query(AuditEntryModel).filter(
            AuditEntryModel.recipe_id == recipe_id
        ).count()

        last_entry = self.session.query(AuditEntryModel).filter(
            AuditEntryModel.recipe_id == recipe_id
        ).order_by(AuditEntryModel.created_at.desc()).first()

        return {
            'recipe': {
                'recipe_id': recipe.recipe_id,
                'name': recipe.name,
                'product_id': recipe.product_id,
                'machine_type': recipe.machine_type,
                'description': recipe.description,
            },
            'versioning': {
                'total_versions': len(recipe.versions),
                'current_version': recipe.current_version,
                'active_version_status': active_version.status.value if active_version else None,
            },
            'lock_status': {
                'status': recipe.lock_status.value,
                'locked_by_job': recipe.locked_by_job_id,
                'locked_at': recipe.locked_at.isoformat() if recipe.locked_at else None,
            },
            'effectiveness': {
                'lots_produced': effectiveness.lots_produced,
                'yield_pct': effectiveness.yield_pct,
                'quality_score': effectiveness.quality_score,
            },
            'audit_summary': {
                'total_entries': audit_count,
                'last_change': last_entry.created_at.isoformat() if last_entry else None,
            },
        }
