"""
LEGO Factory v3 - ISA-88 Recipe Management Service
===================================================
Complete recipe lifecycle management following ISA-88 standard.

Supports:
- Recipe CRUD with versioning
- Control recipe execution
- Parameter management and validation
- Procedure step management
- Approval workflows
- Batch tracking
"""

import uuid
import copy
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from sqlalchemy import select, update, delete, and_, or_, func, desc
from sqlalchemy.orm import Session

from config.database import get_db_session
from models.scada.recipes import (
    MasterRecipe, ControlRecipe, RecipeApproval, RecipeParameter,
    RecipeType, RecipeStatus, ApprovalStatus
)

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class RecipeError(Exception):
    """Base exception for recipe operations."""
    pass


class RecipeNotFoundError(RecipeError):
    """Recipe not found."""
    pass


class RecipeVersionError(RecipeError):
    """Version-related error."""
    pass


class RecipeValidationError(RecipeError):
    """Parameter validation error."""
    pass


class RecipeStateError(RecipeError):
    """Invalid state transition error."""
    pass


class RecipeApprovalError(RecipeError):
    """Approval workflow error."""
    pass


class RecipeExecutionError(RecipeError):
    """Execution-related error."""
    pass


class ControlRecipeNotFoundError(RecipeError):
    """Control recipe not found."""
    pass


# =============================================================================
# DATA CLASSES
# =============================================================================

class ExecutionStatus(Enum):
    """Control recipe execution status."""
    PENDING = 'pending'
    LOADED = 'loaded'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    ABORTED = 'aborted'
    FAILED = 'failed'


@dataclass
class ProcedureStep:
    """ISA-88 Procedure step definition."""
    step_number: int
    name: str
    description: str
    step_type: str  # operation, phase, action
    duration_seconds: Optional[float] = None
    gcode_content: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    prerequisites: List[int] = field(default_factory=list)
    quality_checks: List[Dict[str, Any]] = field(default_factory=list)
    safety_interlocks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VersionDiff:
    """Comparison between two recipe versions."""
    recipe_id: str
    version_from: str
    version_to: str
    changes: Dict[str, Any]
    added_fields: List[str]
    removed_fields: List[str]
    modified_fields: List[str]


@dataclass
class BatchRecord:
    """Batch execution record."""
    batch_id: str
    control_recipe_id: str
    master_recipe_id: str
    work_order_id: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    parts_produced: int
    parts_rejected: int
    actual_cycle_time: Optional[float]
    parameter_actuals: Dict[str, Any]
    quality_results: List[Dict[str, Any]]


# =============================================================================
# WEBSOCKET EVENT EMISSION
# =============================================================================

def _emit_recipe_event(event_type: str, data: Dict[str, Any]):
    """
    Emit recipe event to WebSocket clients.
    Gracefully handles case where SocketIO isn't initialized.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace, emit_to_room

        # Emit to /dashboard namespace for dashboard subscribers
        emit_to_namespace(event_type, data, namespace='/dashboard')

        # Also notify SCADA and MES users
        emit_to_room(event_type, data, room='scada', namespace='/')
        emit_to_room(event_type, data, room='mes', namespace='/')

        logger.debug(f"Emitted recipe event: {event_type}")
    except ImportError:
        logger.debug("WebSocket service not available, skipping recipe emit")
    except Exception as e:
        logger.warning(f"Failed to emit recipe event: {e}")


# =============================================================================
# RECIPE SERVICE
# =============================================================================

class RecipeService:
    """
    ISA-88 compliant Recipe Management Service.

    Provides complete recipe lifecycle management including:
    - Master recipe CRUD with versioning
    - Control recipe creation and execution
    - Parameter validation and substitution
    - Procedure step management
    - Approval workflows
    - Batch tracking
    """

    def __init__(self, session: Session):
        """
        Initialize the recipe service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self._current_step_cache: Dict[str, int] = {}  # control_recipe_id -> current_step

    # =========================================================================
    # RECIPE CRUD OPERATIONS
    # =========================================================================

    def create_recipe(
        self,
        name: str,
        description: Optional[str] = None,
        recipe_type: str = 'master',
        parameters: Optional[Dict[str, Any]] = None,
        procedure_steps: Optional[List[Dict[str, Any]]] = None,
        product_id: Optional[str] = None,
        machine_type: Optional[str] = None,
        gcode_content: Optional[str] = None,
        materials: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        quality_specs: Optional[Dict[str, Any]] = None,
        estimated_cycle_time_seconds: Optional[float] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new master recipe.

        Args:
            name: Recipe name
            description: Recipe description
            recipe_type: Type of recipe (general, site, master)
            parameters: Recipe parameters
            procedure_steps: List of procedure steps
            product_id: Associated product ID
            machine_type: Required machine type
            gcode_content: G-code content
            materials: Required materials list
            tools: Required tools list
            quality_specs: Quality specifications
            estimated_cycle_time_seconds: Estimated cycle time
            created_by: User creating the recipe

        Returns:
            Created recipe as dictionary

        Raises:
            RecipeValidationError: If validation fails
        """
        # Generate recipe_id
        recipe_id = f"RCP-{uuid.uuid4().hex[:8].upper()}"

        # Calculate G-code checksum if provided
        gcode_checksum = None
        if gcode_content:
            gcode_checksum = hashlib.sha256(gcode_content.encode()).hexdigest()

        # Build procedure data
        procedure_data = None
        if procedure_steps:
            procedure_data = self._validate_procedure_steps(procedure_steps)

        recipe = MasterRecipe(
            recipe_id=recipe_id,
            name=name,
            description=description,
            recipe_version='1.0.0',
            is_latest=True,
            recipe_type=RecipeType(recipe_type) if recipe_type else RecipeType.MASTER,
            status=RecipeStatus.DRAFT,
            product_id=product_id,
            machine_type=machine_type,
            gcode_content=gcode_content,
            gcode_checksum=gcode_checksum,
            parameters=parameters or {},
            materials=materials,
            tools=tools,
            quality_specs=quality_specs,
            estimated_cycle_time_seconds=estimated_cycle_time_seconds,
            created_by=created_by
        )

        # Store procedure steps in parameters if provided
        if procedure_data:
            recipe.parameters = recipe.parameters or {}
            recipe.parameters['procedure_steps'] = procedure_data

        self.session.add(recipe)
        self.session.flush()

        logger.info(f"Created recipe: {recipe_id} - {name}")

        # Emit WebSocket event
        recipe_dict = recipe.to_dict()
        _emit_recipe_event('recipe_created', {
            'recipe_id': recipe_id,
            'name': name,
            'recipe': recipe_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe_dict

    def get_recipe(
        self,
        recipe_id: str,
        version: Optional[str] = None,
        include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get a recipe by ID.

        Args:
            recipe_id: Recipe identifier
            version: Specific version (defaults to latest)
            include_deleted: Include soft-deleted recipes

        Returns:
            Recipe as dictionary

        Raises:
            RecipeNotFoundError: If recipe not found
        """
        query = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id
        )

        if not include_deleted:
            query = query.filter(MasterRecipe.is_deleted == False)

        if version:
            query = query.filter(MasterRecipe.recipe_version == version)
        else:
            query = query.filter(MasterRecipe.is_latest == True)

        recipe = query.first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}" +
                                     (f" version {version}" if version else ""))

        return recipe.to_dict()

    def update_recipe(
        self,
        recipe_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing recipe.

        Args:
            recipe_id: Recipe identifier
            updates: Dictionary of fields to update
            updated_by: User performing the update

        Returns:
            Updated recipe as dictionary

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeStateError: If recipe cannot be modified
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        # Check if recipe can be modified
        if recipe.status in [RecipeStatus.RELEASED, RecipeStatus.OBSOLETE]:
            raise RecipeStateError(
                f"Cannot modify recipe in {recipe.status.value} status. "
                "Create a new version instead."
            )

        # Protected fields that cannot be directly updated
        protected_fields = {'id', 'recipe_id', 'created_at', 'recipe_version'}

        for key, value in updates.items():
            if key in protected_fields:
                continue
            if hasattr(recipe, key):
                # Handle enum conversions
                if key == 'recipe_type' and isinstance(value, str):
                    value = RecipeType(value)
                elif key == 'status' and isinstance(value, str):
                    value = RecipeStatus(value)
                setattr(recipe, key, value)

        # Update G-code checksum if content changed
        if 'gcode_content' in updates and updates['gcode_content']:
            recipe.gcode_checksum = hashlib.sha256(
                updates['gcode_content'].encode()
            ).hexdigest()

        recipe.updated_at = datetime.utcnow()
        recipe.updated_by = updated_by

        self.session.flush()

        logger.info(f"Updated recipe: {recipe_id}")

        # Emit WebSocket event
        recipe_dict = recipe.to_dict()
        _emit_recipe_event('recipe_updated', {
            'recipe_id': recipe_id,
            'updates': list(updates.keys()),
            'recipe': recipe_dict,
            'updated_by': updated_by,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe_dict

    def delete_recipe(
        self,
        recipe_id: str,
        soft_delete: bool = True,
        deleted_by: Optional[str] = None
    ) -> bool:
        """
        Delete a recipe.

        Args:
            recipe_id: Recipe identifier
            soft_delete: If True, soft delete; if False, hard delete
            deleted_by: User performing the deletion

        Returns:
            True if deleted successfully

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeStateError: If recipe cannot be deleted
        """
        recipes = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id
        ).all()

        if not recipes:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        # Check for active control recipes
        active_controls = self.session.query(ControlRecipe).filter(
            ControlRecipe.master_recipe_id.in_([r.id for r in recipes]),
            ControlRecipe.status.in_(['pending', 'loaded', 'running', 'paused'])
        ).count()

        if active_controls > 0:
            raise RecipeStateError(
                f"Cannot delete recipe with {active_controls} active control recipes"
            )

        for recipe in recipes:
            if soft_delete:
                recipe.soft_delete(deleted_by)
            else:
                self.session.delete(recipe)

        self.session.flush()

        logger.info(f"Deleted recipe: {recipe_id} (soft={soft_delete})")

        # Emit WebSocket event
        _emit_recipe_event('recipe_deleted', {
            'recipe_id': recipe_id,
            'soft_delete': soft_delete,
            'deleted_by': deleted_by,
            'timestamp': datetime.utcnow().isoformat()
        })

        return True

    def list_recipes(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, int]] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List recipes with filtering and pagination.

        Args:
            filters: Filter criteria
                - recipe_type: Filter by type
                - status: Filter by status
                - search: Search in name/description
                - product_id: Filter by product
                - machine_type: Filter by machine type
                - latest_only: Only return latest versions
            pagination: Pagination settings
                - limit: Max results
                - offset: Starting offset

        Returns:
            Tuple of (list of recipes, total count)
        """
        filters = filters or {}
        pagination = pagination or {'limit': 100, 'offset': 0}

        query = self.session.query(MasterRecipe).filter(
            MasterRecipe.is_deleted == False
        )

        # Apply filters
        if filters.get('recipe_type'):
            query = query.filter(
                MasterRecipe.recipe_type == RecipeType(filters['recipe_type'])
            )

        if filters.get('status'):
            query = query.filter(
                MasterRecipe.status == RecipeStatus(filters['status'])
            )

        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    MasterRecipe.name.ilike(search_term),
                    MasterRecipe.description.ilike(search_term),
                    MasterRecipe.recipe_id.ilike(search_term)
                )
            )

        if filters.get('product_id'):
            query = query.filter(MasterRecipe.product_id == filters['product_id'])

        if filters.get('machine_type'):
            query = query.filter(MasterRecipe.machine_type == filters['machine_type'])

        if filters.get('latest_only', True):
            query = query.filter(MasterRecipe.is_latest == True)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        recipes = query.order_by(
            MasterRecipe.name,
            desc(MasterRecipe.recipe_version)
        ).offset(pagination.get('offset', 0)).limit(pagination.get('limit', 100)).all()

        return [r.to_dict() for r in recipes], total

    # =========================================================================
    # VERSION CONTROL
    # =========================================================================

    def create_version(
        self,
        recipe_id: str,
        changes: Dict[str, Any],
        author: str,
        version_type: str = 'minor'
    ) -> Dict[str, Any]:
        """
        Create a new version of a recipe.

        Args:
            recipe_id: Recipe identifier
            changes: Changes to apply
            author: Author of the new version
            version_type: 'major', 'minor', or 'patch'

        Returns:
            New version as dictionary

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeVersionError: If version creation fails
        """
        # Get current latest version
        current = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not current:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        # Calculate new version number
        current_version = current.recipe_version.split('.')
        major, minor, patch = int(current_version[0]), int(current_version[1]), int(current_version[2])

        if version_type == 'major':
            new_version = f"{major + 1}.0.0"
        elif version_type == 'minor':
            new_version = f"{major}.{minor + 1}.0"
        else:  # patch
            new_version = f"{major}.{minor}.{patch + 1}"

        # Mark current as not latest
        current.is_latest = False

        # Create new version as copy
        new_recipe = MasterRecipe(
            recipe_id=recipe_id,
            name=current.name,
            description=current.description,
            recipe_version=new_version,
            is_latest=True,
            recipe_type=current.recipe_type,
            status=RecipeStatus.DRAFT,  # New versions start as draft
            product_id=current.product_id,
            product_name=current.product_name,
            machine_type=current.machine_type,
            required_capabilities=current.required_capabilities,
            gcode_content=current.gcode_content,
            gcode_file_path=current.gcode_file_path,
            gcode_checksum=current.gcode_checksum,
            parameters=copy.deepcopy(current.parameters) if current.parameters else {},
            print_profile=copy.deepcopy(current.print_profile) if current.print_profile else None,
            materials=copy.deepcopy(current.materials) if current.materials else None,
            tools=copy.deepcopy(current.tools) if current.tools else None,
            quality_specs=copy.deepcopy(current.quality_specs) if current.quality_specs else None,
            estimated_cycle_time_seconds=current.estimated_cycle_time_seconds,
            estimated_setup_time_seconds=current.estimated_setup_time_seconds,
            created_by=author
        )

        # Apply changes
        for key, value in changes.items():
            if hasattr(new_recipe, key) and key not in {'id', 'recipe_id', 'recipe_version'}:
                setattr(new_recipe, key, value)

        # Recalculate checksum if G-code changed
        if new_recipe.gcode_content:
            new_recipe.gcode_checksum = hashlib.sha256(
                new_recipe.gcode_content.encode()
            ).hexdigest()

        self.session.add(new_recipe)
        self.session.flush()

        logger.info(f"Created new version: {recipe_id} v{new_version}")

        # Emit WebSocket event
        recipe_dict = new_recipe.to_dict()
        _emit_recipe_event('recipe_version_created', {
            'recipe_id': recipe_id,
            'new_version': new_version,
            'previous_version': current.recipe_version,
            'author': author,
            'recipe': recipe_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe_dict

    def get_version(
        self,
        recipe_id: str,
        version_number: str
    ) -> Dict[str, Any]:
        """
        Get a specific version of a recipe.

        Args:
            recipe_id: Recipe identifier
            version_number: Version string (e.g., "1.0.0")

        Returns:
            Recipe version as dictionary

        Raises:
            RecipeNotFoundError: If version not found
        """
        return self.get_recipe(recipe_id, version=version_number)

    def get_version_history(
        self,
        recipe_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a recipe.

        Args:
            recipe_id: Recipe identifier

        Returns:
            List of all versions with metadata
        """
        versions = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_deleted == False
        ).order_by(desc(MasterRecipe.recipe_version)).all()

        return [{
            'recipe_id': v.recipe_id,
            'version': v.recipe_version,
            'is_latest': v.is_latest,
            'status': v.status.value,
            'created_at': v.created_at.isoformat() if v.created_at else None,
            'created_by': v.created_by,
            'approved_by': v.approved_by,
            'approved_at': v.approved_at.isoformat() if v.approved_at else None,
        } for v in versions]

    def rollback_to_version(
        self,
        recipe_id: str,
        version_number: str,
        author: str
    ) -> Dict[str, Any]:
        """
        Rollback to a previous version by creating a new version.

        Args:
            recipe_id: Recipe identifier
            version_number: Version to rollback to
            author: Author performing the rollback

        Returns:
            New recipe version as dictionary

        Raises:
            RecipeNotFoundError: If version not found
        """
        # Get the target version
        target = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.recipe_version == version_number,
            MasterRecipe.is_deleted == False
        ).first()

        if not target:
            raise RecipeNotFoundError(
                f"Version {version_number} not found for recipe {recipe_id}"
            )

        # Get current latest
        current = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True
        ).first()

        if current:
            # Create changes dict from target version
            changes = {
                'name': target.name,
                'description': target.description,
                'gcode_content': target.gcode_content,
                'parameters': target.parameters,
                'materials': target.materials,
                'tools': target.tools,
                'quality_specs': target.quality_specs,
                'estimated_cycle_time_seconds': target.estimated_cycle_time_seconds,
            }

            # Create new version with target's content
            new_recipe = self.create_version(
                recipe_id=recipe_id,
                changes=changes,
                author=author,
                version_type='minor'
            )

            logger.info(f"Rolled back {recipe_id} to v{version_number}")

            # Emit WebSocket event
            _emit_recipe_event('recipe_rollback', {
                'recipe_id': recipe_id,
                'rolled_back_to': version_number,
                'new_version': new_recipe['recipe_version'],
                'author': author,
                'timestamp': datetime.utcnow().isoformat()
            })

            return new_recipe

        raise RecipeVersionError("No current version to rollback from")

    def compare_versions(
        self,
        recipe_id: str,
        v1: str,
        v2: str
    ) -> VersionDiff:
        """
        Compare two versions of a recipe.

        Args:
            recipe_id: Recipe identifier
            v1: First version
            v2: Second version

        Returns:
            VersionDiff object with comparison details

        Raises:
            RecipeNotFoundError: If either version not found
        """
        version1 = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.recipe_version == v1
        ).first()

        version2 = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.recipe_version == v2
        ).first()

        if not version1:
            raise RecipeNotFoundError(f"Version {v1} not found")
        if not version2:
            raise RecipeNotFoundError(f"Version {v2} not found")

        # Compare relevant fields
        compare_fields = [
            'name', 'description', 'gcode_content', 'parameters',
            'materials', 'tools', 'quality_specs', 'machine_type',
            'estimated_cycle_time_seconds', 'print_profile'
        ]

        changes = {}
        added = []
        removed = []
        modified = []

        for field in compare_fields:
            val1 = getattr(version1, field)
            val2 = getattr(version2, field)

            if val1 != val2:
                if val1 is None and val2 is not None:
                    added.append(field)
                elif val1 is not None and val2 is None:
                    removed.append(field)
                else:
                    modified.append(field)

                changes[field] = {
                    'from': val1,
                    'to': val2
                }

        return VersionDiff(
            recipe_id=recipe_id,
            version_from=v1,
            version_to=v2,
            changes=changes,
            added_fields=added,
            removed_fields=removed,
            modified_fields=modified
        )

    # =========================================================================
    # RECIPE EXECUTION (CONTROL RECIPES)
    # =========================================================================

    def create_control_recipe(
        self,
        master_recipe_id: str,
        work_order_id: Optional[str] = None,
        parameter_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a control recipe from a master recipe.

        Args:
            master_recipe_id: Master recipe identifier (recipe_id, not UUID)
            work_order_id: Associated work order ID
            parameter_overrides: Parameters to override

        Returns:
            Control recipe as dictionary

        Raises:
            RecipeNotFoundError: If master recipe not found
            RecipeStateError: If master recipe not approved/released
        """
        # Get the master recipe
        master = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == master_recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not master:
            raise RecipeNotFoundError(f"Master recipe not found: {master_recipe_id}")

        # Check status - must be approved or released for production
        if master.status not in [RecipeStatus.APPROVED, RecipeStatus.RELEASED]:
            raise RecipeStateError(
                f"Cannot create control recipe from {master.status.value} recipe. "
                "Recipe must be approved or released."
            )

        # Validate parameter overrides
        if parameter_overrides:
            self._validate_parameter_overrides(master, parameter_overrides)

        # Create control recipe
        control = ControlRecipe(
            master_recipe_id=master.id,
            work_order_id=uuid.UUID(work_order_id) if work_order_id else None,
            parameter_overrides=parameter_overrides,
            status='pending'
        )

        self.session.add(control)
        self.session.flush()

        logger.info(
            f"Created control recipe from {master_recipe_id} for work order {work_order_id}"
        )

        # Emit WebSocket event
        control_dict = control.to_dict()
        _emit_recipe_event('control_recipe_created', {
            'control_recipe_id': str(control.id),
            'master_recipe_id': master_recipe_id,
            'work_order_id': work_order_id,
            'control_recipe': control_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return control_dict

    def start_recipe_execution(
        self,
        control_recipe_id: str,
        machine_id: str
    ) -> Dict[str, Any]:
        """
        Start executing a control recipe on a machine.

        Args:
            control_recipe_id: Control recipe ID
            machine_id: Machine to execute on

        Returns:
            Updated control recipe

        Raises:
            ControlRecipeNotFoundError: If control recipe not found
            RecipeStateError: If recipe cannot be started
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        if control.status not in ['pending', 'loaded']:
            raise RecipeStateError(
                f"Cannot start recipe in {control.status} status"
            )

        control.machine_id = uuid.UUID(machine_id)
        control.status = 'running'
        control.started_at = datetime.utcnow()

        # Initialize step tracking
        self._current_step_cache[control_recipe_id] = 0

        self.session.flush()

        logger.info(f"Started recipe execution: {control_recipe_id} on machine {machine_id}")

        # Emit WebSocket event
        control_dict = control.to_dict()
        _emit_recipe_event('recipe_execution_started', {
            'control_recipe_id': control_recipe_id,
            'machine_id': machine_id,
            'started_at': control.started_at.isoformat(),
            'control_recipe': control_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return control_dict

    def advance_step(
        self,
        control_recipe_id: str
    ) -> Dict[str, Any]:
        """
        Advance to the next procedure step.

        Args:
            control_recipe_id: Control recipe ID

        Returns:
            Dictionary with current step info

        Raises:
            ControlRecipeNotFoundError: If control recipe not found
            RecipeStateError: If recipe not running
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        if control.status != 'running':
            raise RecipeStateError("Recipe must be running to advance steps")

        # Get procedure steps from master recipe
        master = control.master_recipe
        steps = master.parameters.get('procedure_steps', []) if master.parameters else []

        current_step = self._current_step_cache.get(control_recipe_id, 0)
        next_step = current_step + 1

        if next_step >= len(steps):
            # All steps complete
            return self.complete_execution(control_recipe_id)

        self._current_step_cache[control_recipe_id] = next_step

        step_info = {
            'control_recipe_id': control_recipe_id,
            'previous_step': current_step,
            'current_step': next_step,
            'total_steps': len(steps),
            'step_data': steps[next_step] if next_step < len(steps) else None
        }

        logger.info(f"Advanced to step {next_step} for {control_recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('recipe_step_advanced', {
            **step_info,
            'timestamp': datetime.utcnow().isoformat()
        })

        return step_info

    def pause_execution(
        self,
        control_recipe_id: str
    ) -> Dict[str, Any]:
        """
        Pause recipe execution.

        Args:
            control_recipe_id: Control recipe ID

        Returns:
            Updated control recipe

        Raises:
            ControlRecipeNotFoundError: If control recipe not found
            RecipeStateError: If recipe cannot be paused
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        if control.status != 'running':
            raise RecipeStateError("Can only pause running recipes")

        control.status = 'paused'
        self.session.flush()

        logger.info(f"Paused recipe execution: {control_recipe_id}")

        # Emit WebSocket event
        control_dict = control.to_dict()
        _emit_recipe_event('recipe_execution_paused', {
            'control_recipe_id': control_recipe_id,
            'control_recipe': control_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return control_dict

    def resume_execution(
        self,
        control_recipe_id: str
    ) -> Dict[str, Any]:
        """
        Resume paused recipe execution.

        Args:
            control_recipe_id: Control recipe ID

        Returns:
            Updated control recipe

        Raises:
            ControlRecipeNotFoundError: If control recipe not found
            RecipeStateError: If recipe cannot be resumed
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        if control.status != 'paused':
            raise RecipeStateError("Can only resume paused recipes")

        control.status = 'running'
        self.session.flush()

        logger.info(f"Resumed recipe execution: {control_recipe_id}")

        # Emit WebSocket event
        control_dict = control.to_dict()
        _emit_recipe_event('recipe_execution_resumed', {
            'control_recipe_id': control_recipe_id,
            'control_recipe': control_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return control_dict

    def abort_execution(
        self,
        control_recipe_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Abort recipe execution.

        Args:
            control_recipe_id: Control recipe ID
            reason: Reason for aborting

        Returns:
            Updated control recipe

        Raises:
            ControlRecipeNotFoundError: If control recipe not found
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        if control.status in ['completed', 'aborted']:
            raise RecipeStateError(f"Recipe already {control.status}")

        control.status = 'aborted'
        control.completed_at = datetime.utcnow()

        # Calculate actual cycle time
        if control.started_at:
            control.actual_cycle_time_seconds = (
                control.completed_at - control.started_at
            ).total_seconds()

        # Clear step cache
        self._current_step_cache.pop(control_recipe_id, None)

        self.session.flush()

        logger.warning(f"Aborted recipe execution: {control_recipe_id} - {reason}")

        # Emit WebSocket event
        control_dict = control.to_dict()
        _emit_recipe_event('recipe_execution_aborted', {
            'control_recipe_id': control_recipe_id,
            'reason': reason,
            'control_recipe': control_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return control_dict

    def complete_execution(
        self,
        control_recipe_id: str
    ) -> Dict[str, Any]:
        """
        Complete recipe execution successfully.

        Args:
            control_recipe_id: Control recipe ID

        Returns:
            Updated control recipe

        Raises:
            ControlRecipeNotFoundError: If control recipe not found
            RecipeStateError: If recipe cannot be completed
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        if control.status not in ['running', 'paused']:
            raise RecipeStateError(
                f"Cannot complete recipe in {control.status} status"
            )

        control.status = 'completed'
        control.completed_at = datetime.utcnow()

        # Calculate actual cycle time
        if control.started_at:
            control.actual_cycle_time_seconds = (
                control.completed_at - control.started_at
            ).total_seconds()

        # Clear step cache
        self._current_step_cache.pop(control_recipe_id, None)

        self.session.flush()

        logger.info(f"Completed recipe execution: {control_recipe_id}")

        # Emit WebSocket event
        control_dict = control.to_dict()
        _emit_recipe_event('recipe_execution_completed', {
            'control_recipe_id': control_recipe_id,
            'actual_cycle_time_seconds': control.actual_cycle_time_seconds,
            'parts_produced': control.parts_produced,
            'parts_rejected': control.parts_rejected,
            'control_recipe': control_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return control_dict

    # =========================================================================
    # PARAMETER MANAGEMENT
    # =========================================================================

    def validate_parameters(
        self,
        recipe_id: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate parameters against recipe parameter definitions.

        Args:
            recipe_id: Recipe identifier
            parameters: Parameters to validate

        Returns:
            Tuple of (is_valid, list of error messages)

        Raises:
            RecipeNotFoundError: If recipe not found
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        # Get parameter definitions
        param_defs = self.session.query(RecipeParameter).filter(
            RecipeParameter.recipe_id == recipe.id
        ).all()

        errors = []
        param_def_map = {p.name: p for p in param_defs}

        # Check required parameters
        for param_def in param_defs:
            if param_def.required and param_def.name not in parameters:
                errors.append(f"Required parameter missing: {param_def.name}")

        # Validate provided parameters
        for name, value in parameters.items():
            if name not in param_def_map:
                # Unknown parameter - could be warning or error depending on strictness
                continue

            param_def = param_def_map[name]

            # Type validation
            if param_def.data_type == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    errors.append(f"Parameter {name} must be a float")
                    continue
            elif param_def.data_type == 'int':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    errors.append(f"Parameter {name} must be an integer")
                    continue
            elif param_def.data_type == 'bool':
                if not isinstance(value, bool):
                    errors.append(f"Parameter {name} must be a boolean")
                    continue

            # Range validation for numeric types
            if param_def.data_type in ['float', 'int']:
                if param_def.min_value is not None and value < param_def.min_value:
                    errors.append(
                        f"Parameter {name} ({value}) below minimum ({param_def.min_value})"
                    )
                if param_def.max_value is not None and value > param_def.max_value:
                    errors.append(
                        f"Parameter {name} ({value}) above maximum ({param_def.max_value})"
                    )

        return len(errors) == 0, errors

    def substitute_parameters(
        self,
        recipe_id: str,
        substitutions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Substitute parameters in G-code content.

        Args:
            recipe_id: Recipe identifier
            substitutions: Parameter name -> value mapping

        Returns:
            Dictionary with substituted content

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeValidationError: If validation fails
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        # Validate substitutions
        is_valid, errors = self.validate_parameters(recipe_id, substitutions)
        if not is_valid:
            raise RecipeValidationError(f"Parameter validation failed: {errors}")

        # Substitute in G-code
        gcode = recipe.gcode_content or ""
        for name, value in substitutions.items():
            # Replace {{param_name}} style placeholders
            gcode = gcode.replace(f"{{{{{name}}}}}", str(value))
            # Also replace ${param_name} style
            gcode = gcode.replace(f"${{{name}}}", str(value))

        # Merge with existing parameters
        merged_params = dict(recipe.parameters or {})
        merged_params.update(substitutions)

        return {
            'recipe_id': recipe_id,
            'gcode_content': gcode,
            'parameters': merged_params,
            'substitutions_applied': list(substitutions.keys())
        }

    def get_parameter_schema(
        self,
        recipe_id: str
    ) -> Dict[str, Any]:
        """
        Get the parameter schema for a recipe.

        Args:
            recipe_id: Recipe identifier

        Returns:
            Parameter schema as dictionary

        Raises:
            RecipeNotFoundError: If recipe not found
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        # Get parameter definitions
        param_defs = self.session.query(RecipeParameter).filter(
            RecipeParameter.recipe_id == recipe.id
        ).all()

        schema = {
            'recipe_id': recipe_id,
            'parameters': {}
        }

        for param in param_defs:
            schema['parameters'][param.name] = {
                'description': param.description,
                'type': param.data_type,
                'default': param.default_value,
                'min': param.min_value,
                'max': param.max_value,
                'units': param.units,
                'required': param.required
            }

        return schema

    # =========================================================================
    # PROCEDURE STEPS
    # =========================================================================

    def add_step(
        self,
        recipe_id: str,
        step_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a procedure step to a recipe.

        Args:
            recipe_id: Recipe identifier
            step_data: Step definition

        Returns:
            Updated recipe with new step

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeStateError: If recipe cannot be modified
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status in [RecipeStatus.RELEASED, RecipeStatus.OBSOLETE]:
            raise RecipeStateError("Cannot modify released or obsolete recipe")

        # Get or initialize procedure steps
        params = recipe.parameters or {}
        steps = params.get('procedure_steps', [])

        # Auto-assign step number if not provided
        if 'step_number' not in step_data:
            step_data['step_number'] = len(steps) + 1

        # Validate step data
        validated_step = self._validate_procedure_step(step_data)

        steps.append(validated_step)
        params['procedure_steps'] = steps
        recipe.parameters = params
        recipe.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Added step {validated_step['step_number']} to recipe {recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('recipe_step_added', {
            'recipe_id': recipe_id,
            'step': validated_step,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe.to_dict()

    def update_step(
        self,
        recipe_id: str,
        step_number: int,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a procedure step.

        Args:
            recipe_id: Recipe identifier
            step_number: Step number to update
            updates: Fields to update

        Returns:
            Updated recipe

        Raises:
            RecipeNotFoundError: If recipe or step not found
            RecipeStateError: If recipe cannot be modified
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status in [RecipeStatus.RELEASED, RecipeStatus.OBSOLETE]:
            raise RecipeStateError("Cannot modify released or obsolete recipe")

        params = recipe.parameters or {}
        steps = params.get('procedure_steps', [])

        # Find the step
        step_index = None
        for i, step in enumerate(steps):
            if step.get('step_number') == step_number:
                step_index = i
                break

        if step_index is None:
            raise RecipeNotFoundError(f"Step {step_number} not found")

        # Update the step
        for key, value in updates.items():
            if key != 'step_number':  # Don't allow changing step number this way
                steps[step_index][key] = value

        params['procedure_steps'] = steps
        recipe.parameters = params
        recipe.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Updated step {step_number} in recipe {recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('recipe_step_updated', {
            'recipe_id': recipe_id,
            'step_number': step_number,
            'updates': list(updates.keys()),
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe.to_dict()

    def delete_step(
        self,
        recipe_id: str,
        step_number: int
    ) -> Dict[str, Any]:
        """
        Delete a procedure step.

        Args:
            recipe_id: Recipe identifier
            step_number: Step number to delete

        Returns:
            Updated recipe

        Raises:
            RecipeNotFoundError: If recipe or step not found
            RecipeStateError: If recipe cannot be modified
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status in [RecipeStatus.RELEASED, RecipeStatus.OBSOLETE]:
            raise RecipeStateError("Cannot modify released or obsolete recipe")

        params = recipe.parameters or {}
        steps = params.get('procedure_steps', [])

        # Find and remove the step
        original_len = len(steps)
        steps = [s for s in steps if s.get('step_number') != step_number]

        if len(steps) == original_len:
            raise RecipeNotFoundError(f"Step {step_number} not found")

        # Renumber remaining steps
        for i, step in enumerate(steps):
            step['step_number'] = i + 1

        params['procedure_steps'] = steps
        recipe.parameters = params
        recipe.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Deleted step {step_number} from recipe {recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('recipe_step_deleted', {
            'recipe_id': recipe_id,
            'step_number': step_number,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe.to_dict()

    def reorder_steps(
        self,
        recipe_id: str,
        new_order: List[int]
    ) -> Dict[str, Any]:
        """
        Reorder procedure steps.

        Args:
            recipe_id: Recipe identifier
            new_order: List of step numbers in new order

        Returns:
            Updated recipe

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeValidationError: If new order is invalid
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status in [RecipeStatus.RELEASED, RecipeStatus.OBSOLETE]:
            raise RecipeStateError("Cannot modify released or obsolete recipe")

        params = recipe.parameters or {}
        steps = params.get('procedure_steps', [])

        # Validate new order
        existing_numbers = {s.get('step_number') for s in steps}
        if set(new_order) != existing_numbers:
            raise RecipeValidationError(
                "New order must contain exactly the existing step numbers"
            )

        # Create mapping from old step number to step data
        step_map = {s.get('step_number'): s for s in steps}

        # Reorder and renumber
        reordered_steps = []
        for i, old_number in enumerate(new_order):
            step = step_map[old_number]
            step['step_number'] = i + 1
            reordered_steps.append(step)

        params['procedure_steps'] = reordered_steps
        recipe.parameters = params
        recipe.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Reordered steps in recipe {recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('recipe_steps_reordered', {
            'recipe_id': recipe_id,
            'new_order': new_order,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe.to_dict()

    # =========================================================================
    # RECIPE APPROVAL WORKFLOW
    # =========================================================================

    def submit_for_approval(
        self,
        recipe_id: str,
        submitted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit a recipe for approval.

        Args:
            recipe_id: Recipe identifier
            submitted_by: User submitting for approval

        Returns:
            Updated recipe

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeStateError: If recipe cannot be submitted
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status != RecipeStatus.DRAFT:
            raise RecipeStateError(
                f"Can only submit draft recipes for approval. "
                f"Current status: {recipe.status.value}"
            )

        # Validate recipe has minimum required data
        if not recipe.gcode_content and not recipe.parameters:
            raise RecipeValidationError(
                "Recipe must have G-code content or parameters before approval"
            )

        recipe.status = RecipeStatus.PENDING_APPROVAL
        recipe.updated_at = datetime.utcnow()
        recipe.updated_by = submitted_by

        self.session.flush()

        logger.info(f"Recipe {recipe_id} submitted for approval")

        # Emit WebSocket event
        recipe_dict = recipe.to_dict()
        _emit_recipe_event('recipe_submitted_for_approval', {
            'recipe_id': recipe_id,
            'submitted_by': submitted_by,
            'recipe': recipe_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe_dict

    def approve_recipe(
        self,
        recipe_id: str,
        approver_id: str,
        approval_role: str = 'engineering',
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve a recipe.

        Args:
            recipe_id: Recipe identifier
            approver_id: ID of the approving user
            approval_role: Role of the approver
            comments: Approval comments

        Returns:
            Updated recipe

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeApprovalError: If approval fails
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status != RecipeStatus.PENDING_APPROVAL:
            raise RecipeApprovalError(
                f"Recipe must be pending approval. Current status: {recipe.status.value}"
            )

        # Create approval record
        approval = RecipeApproval(
            recipe_id=recipe.id,
            approver=approver_id,
            approval_role=approval_role,
            status=ApprovalStatus.APPROVED,
            comments=comments,
            decided_at=datetime.utcnow()
        )

        self.session.add(approval)

        # Update recipe status
        recipe.status = RecipeStatus.APPROVED
        recipe.approved_by = approver_id
        recipe.approved_at = datetime.utcnow()
        recipe.approval_comments = comments
        recipe.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Recipe {recipe_id} approved by {approver_id}")

        # Emit WebSocket event
        recipe_dict = recipe.to_dict()
        _emit_recipe_event('recipe_approved', {
            'recipe_id': recipe_id,
            'approver_id': approver_id,
            'approval_role': approval_role,
            'comments': comments,
            'recipe': recipe_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe_dict

    def reject_recipe(
        self,
        recipe_id: str,
        rejector_id: str,
        reason: str,
        rejection_role: str = 'engineering'
    ) -> Dict[str, Any]:
        """
        Reject a recipe.

        Args:
            recipe_id: Recipe identifier
            rejector_id: ID of the rejecting user
            reason: Reason for rejection
            rejection_role: Role of the rejector

        Returns:
            Updated recipe

        Raises:
            RecipeNotFoundError: If recipe not found
            RecipeApprovalError: If rejection fails
        """
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id,
            MasterRecipe.is_latest == True,
            MasterRecipe.is_deleted == False
        ).first()

        if not recipe:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        if recipe.status != RecipeStatus.PENDING_APPROVAL:
            raise RecipeApprovalError(
                f"Recipe must be pending approval. Current status: {recipe.status.value}"
            )

        # Create rejection record
        approval = RecipeApproval(
            recipe_id=recipe.id,
            approver=rejector_id,
            approval_role=rejection_role,
            status=ApprovalStatus.REJECTED,
            comments=reason,
            decided_at=datetime.utcnow()
        )

        self.session.add(approval)

        # Update recipe status back to draft (or rejected)
        recipe.status = RecipeStatus.REJECTED
        recipe.approval_comments = reason
        recipe.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Recipe {recipe_id} rejected by {rejector_id}: {reason}")

        # Emit WebSocket event
        recipe_dict = recipe.to_dict()
        _emit_recipe_event('recipe_rejected', {
            'recipe_id': recipe_id,
            'rejector_id': rejector_id,
            'rejection_role': rejection_role,
            'reason': reason,
            'recipe': recipe_dict,
            'timestamp': datetime.utcnow().isoformat()
        })

        return recipe_dict

    # =========================================================================
    # BATCH TRACKING
    # =========================================================================

    def record_batch_start(
        self,
        control_recipe_id: str,
        batch_id: str
    ) -> Dict[str, Any]:
        """
        Record the start of a batch.

        Args:
            control_recipe_id: Control recipe ID
            batch_id: Unique batch identifier

        Returns:
            Batch record as dictionary
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        # Store batch info in control recipe or separate batch tracking
        # For now, we'll use a simple approach with parameters
        if not hasattr(control, 'parameter_overrides') or not control.parameter_overrides:
            control.parameter_overrides = {}

        control.parameter_overrides['batch_id'] = batch_id
        control.parameter_overrides['batch_started_at'] = datetime.utcnow().isoformat()

        self.session.flush()

        batch_record = {
            'batch_id': batch_id,
            'control_recipe_id': control_recipe_id,
            'master_recipe_id': str(control.master_recipe_id),
            'work_order_id': str(control.work_order_id) if control.work_order_id else None,
            'started_at': control.parameter_overrides['batch_started_at'],
            'status': 'in_progress'
        }

        logger.info(f"Batch {batch_id} started for control recipe {control_recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('batch_started', {
            **batch_record,
            'timestamp': datetime.utcnow().isoformat()
        })

        return batch_record

    def record_batch_complete(
        self,
        control_recipe_id: str,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record batch completion with results.

        Args:
            control_recipe_id: Control recipe ID
            results: Batch results including parts produced, quality data, etc.

        Returns:
            Complete batch record
        """
        control = self.session.query(ControlRecipe).filter(
            ControlRecipe.id == uuid.UUID(control_recipe_id)
        ).first()

        if not control:
            raise ControlRecipeNotFoundError(
                f"Control recipe not found: {control_recipe_id}"
            )

        # Update control recipe with results
        control.parts_produced = results.get('parts_produced', 0)
        control.parts_rejected = results.get('parts_rejected', 0)

        if control.parameter_overrides:
            control.parameter_overrides['batch_completed_at'] = datetime.utcnow().isoformat()
            control.parameter_overrides['batch_results'] = results

        self.session.flush()

        batch_id = control.parameter_overrides.get('batch_id') if control.parameter_overrides else None

        batch_record = {
            'batch_id': batch_id,
            'control_recipe_id': control_recipe_id,
            'master_recipe_id': str(control.master_recipe_id),
            'work_order_id': str(control.work_order_id) if control.work_order_id else None,
            'completed_at': datetime.utcnow().isoformat(),
            'status': 'completed',
            'parts_produced': control.parts_produced,
            'parts_rejected': control.parts_rejected,
            'results': results
        }

        logger.info(f"Batch {batch_id} completed for control recipe {control_recipe_id}")

        # Emit WebSocket event
        _emit_recipe_event('batch_completed', {
            **batch_record,
            'timestamp': datetime.utcnow().isoformat()
        })

        return batch_record

    def get_batch_history(
        self,
        recipe_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get batch history for a recipe.

        Args:
            recipe_id: Master recipe identifier
            limit: Maximum number of records to return

        Returns:
            List of batch records
        """
        # Get all versions of the master recipe
        recipes = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id
        ).all()

        if not recipes:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_id}")

        recipe_ids = [r.id for r in recipes]

        # Get control recipes with batch info
        controls = self.session.query(ControlRecipe).filter(
            ControlRecipe.master_recipe_id.in_(recipe_ids)
        ).order_by(desc(ControlRecipe.created_at)).limit(limit).all()

        batches = []
        for control in controls:
            batch_info = {
                'control_recipe_id': str(control.id),
                'master_recipe_id': str(control.master_recipe_id),
                'work_order_id': str(control.work_order_id) if control.work_order_id else None,
                'status': control.status,
                'started_at': control.started_at.isoformat() if control.started_at else None,
                'completed_at': control.completed_at.isoformat() if control.completed_at else None,
                'parts_produced': control.parts_produced,
                'parts_rejected': control.parts_rejected,
                'actual_cycle_time_seconds': control.actual_cycle_time_seconds,
            }

            if control.parameter_overrides:
                batch_info['batch_id'] = control.parameter_overrides.get('batch_id')
                batch_info['batch_results'] = control.parameter_overrides.get('batch_results')

            batches.append(batch_info)

        return batches

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _validate_procedure_steps(
        self,
        steps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate and normalize procedure steps."""
        validated = []
        for i, step in enumerate(steps):
            validated.append(self._validate_procedure_step(step, i + 1))
        return validated

    def _validate_procedure_step(
        self,
        step: Dict[str, Any],
        default_number: int = 1
    ) -> Dict[str, Any]:
        """Validate and normalize a single procedure step."""
        return {
            'step_number': step.get('step_number', default_number),
            'name': step.get('name', f'Step {default_number}'),
            'description': step.get('description', ''),
            'step_type': step.get('step_type', 'operation'),
            'duration_seconds': step.get('duration_seconds'),
            'gcode_content': step.get('gcode_content'),
            'parameters': step.get('parameters', {}),
            'prerequisites': step.get('prerequisites', []),
            'quality_checks': step.get('quality_checks', []),
            'safety_interlocks': step.get('safety_interlocks', [])
        }

    def _validate_parameter_overrides(
        self,
        master_recipe: MasterRecipe,
        overrides: Dict[str, Any]
    ) -> None:
        """Validate parameter overrides against master recipe parameters."""
        if not master_recipe.parameters:
            return

        master_params = master_recipe.parameters

        for key, value in overrides.items():
            # Check if parameter exists in master
            if key not in master_params:
                logger.warning(f"Parameter override '{key}' not in master recipe")


# =============================================================================
# SERVICE FACTORY
# =============================================================================

def get_recipe_service(session: Session = None) -> RecipeService:
    """
    Get recipe service instance.

    Args:
        session: Optional SQLAlchemy session. If not provided,
                 creates a new session.

    Returns:
        RecipeService instance
    """
    if session:
        return RecipeService(session)

    with get_db_session() as session:
        return RecipeService(session)
