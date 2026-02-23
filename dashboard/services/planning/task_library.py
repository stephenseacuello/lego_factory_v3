"""
Task Library - Reusable task templates for manufacturing.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import logging

from .htn_planner import Task, TaskType, Method, Condition

logger = logging.getLogger(__name__)


class TaskCategory(Enum):
    """Categories of manufacturing tasks."""
    PRINTING = "printing"
    QUALITY = "quality"
    MATERIAL = "material"
    MAINTENANCE = "maintenance"
    SCHEDULING = "scheduling"
    POST_PROCESSING = "post_processing"


@dataclass
class TaskTemplate:
    """
    Reusable task template with parameterization.

    Templates can be instantiated with specific parameters
    to create executable tasks.
    """
    name: str
    category: TaskCategory
    task_type: TaskType
    description: str
    required_params: Set[str]
    optional_params: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    agent_type: Optional[str] = None
    estimated_duration: float = 0.0
    requires_equipment: List[str] = field(default_factory=list)
    skill_level: int = 1  # 1-5

    def instantiate(self, params: Dict[str, Any]) -> Task:
        """Create a concrete task from template."""
        # Validate required params
        missing = self.required_params - set(params.keys())
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        # Merge with optional defaults
        full_params = {**self.optional_params, **params}

        # Parse conditions
        preconditions = [
            self._parse_condition(c, full_params) for c in self.preconditions
        ]
        effects = [
            self._parse_condition(c, full_params) for c in self.effects
        ]

        return Task(
            name=self.name,
            task_type=self.task_type,
            parameters=full_params,
            preconditions=preconditions,
            effects=effects,
            agent_type=self.agent_type,
            duration_estimate=self.estimated_duration
        )

    def _parse_condition(self, condition_str: str, params: Dict[str, Any]) -> Condition:
        """Parse condition string like 'not printer_ready(printer_id)'."""
        negated = condition_str.startswith('not ')
        if negated:
            condition_str = condition_str[4:]

        # Parse predicate(args)
        if '(' in condition_str:
            pred = condition_str[:condition_str.index('(')]
            args_str = condition_str[condition_str.index('(')+1:-1]
            args = tuple(
                str(params.get(a.strip(), a.strip()))
                for a in args_str.split(',')
            )
        else:
            pred = condition_str
            args = ()

        return Condition(predicate=pred, args=args, negated=negated)


class TaskLibrary:
    """
    Library of manufacturing task templates.

    Provides:
    - Standard manufacturing operations
    - LEGO-specific quality tasks
    - Equipment maintenance tasks
    - Material handling tasks
    """

    def __init__(self):
        self._templates: Dict[str, TaskTemplate] = {}
        self._by_category: Dict[TaskCategory, List[str]] = {
            cat: [] for cat in TaskCategory
        }
        self._load_standard_templates()

    def _load_standard_templates(self) -> None:
        """Load standard manufacturing task templates."""

        # Printing tasks
        self.register(TaskTemplate(
            name="fdm_print",
            category=TaskCategory.PRINTING,
            task_type=TaskType.COMPOUND,
            description="Execute FDM 3D print job",
            required_params={'printer_id', 'gcode_path', 'material'},
            optional_params={'layer_height': 0.2, 'infill': 20},
            preconditions=['printer_ready(printer_id)', 'material_loaded(printer_id)'],
            effects=['print_complete(job_id)'],
            agent_type='printing',
            estimated_duration=3600,
            requires_equipment=['fdm_printer']
        ))

        self.register(TaskTemplate(
            name="sla_print",
            category=TaskCategory.PRINTING,
            task_type=TaskType.COMPOUND,
            description="Execute SLA resin print job",
            required_params={'printer_id', 'slice_path', 'resin_type'},
            optional_params={'layer_height': 0.05, 'exposure_time': 8},
            preconditions=['printer_ready(printer_id)', 'resin_tank_filled(printer_id)'],
            effects=['print_complete(job_id)'],
            agent_type='printing',
            estimated_duration=7200,
            requires_equipment=['sla_printer']
        ))

        # Quality tasks
        self.register(TaskTemplate(
            name="visual_inspection",
            category=TaskCategory.QUALITY,
            task_type=TaskType.PRIMITIVE,
            description="Visual quality inspection",
            required_params={'part_id'},
            optional_params={'use_camera': True},
            preconditions=['part_available(part_id)'],
            effects=['visual_inspected(part_id)'],
            agent_type='quality',
            estimated_duration=60,
            skill_level=2
        ))

        self.register(TaskTemplate(
            name="dimensional_measurement",
            category=TaskCategory.QUALITY,
            task_type=TaskType.PRIMITIVE,
            description="Measure part dimensions",
            required_params={'part_id', 'measurement_points'},
            preconditions=['part_available(part_id)'],
            effects=['dimensions_measured(part_id)'],
            agent_type='quality',
            estimated_duration=180,
            requires_equipment=['caliper', 'cmm'],
            skill_level=3
        ))

        self.register(TaskTemplate(
            name="clutch_power_test",
            category=TaskCategory.QUALITY,
            task_type=TaskType.PRIMITIVE,
            description="Test LEGO clutch power",
            required_params={'part_id'},
            optional_params={'reference_brick': 'official_lego'},
            preconditions=['part_available(part_id)', 'reference_available(reference_brick)'],
            effects=['clutch_tested(part_id)'],
            agent_type='quality',
            estimated_duration=120,
            requires_equipment=['force_gauge'],
            skill_level=2
        ))

        self.register(TaskTemplate(
            name="color_verification",
            category=TaskCategory.QUALITY,
            task_type=TaskType.PRIMITIVE,
            description="Verify color accuracy",
            required_params={'part_id', 'target_color'},
            preconditions=['part_available(part_id)'],
            effects=['color_verified(part_id)'],
            agent_type='quality',
            estimated_duration=30,
            requires_equipment=['spectrophotometer'],
            skill_level=2
        ))

        # Material handling
        self.register(TaskTemplate(
            name="load_filament",
            category=TaskCategory.MATERIAL,
            task_type=TaskType.PRIMITIVE,
            description="Load filament into printer",
            required_params={'printer_id', 'material_spool'},
            preconditions=['nozzle_heated(printer_id)', 'spool_available(material_spool)'],
            effects=['material_loaded(printer_id)'],
            agent_type='material',
            estimated_duration=120,
            skill_level=1
        ))

        self.register(TaskTemplate(
            name="unload_filament",
            category=TaskCategory.MATERIAL,
            task_type=TaskType.PRIMITIVE,
            description="Unload filament from printer",
            required_params={'printer_id'},
            preconditions=['nozzle_heated(printer_id)', 'material_loaded(printer_id)'],
            effects=['not material_loaded(printer_id)'],
            agent_type='material',
            estimated_duration=60,
            skill_level=1
        ))

        self.register(TaskTemplate(
            name="dry_material",
            category=TaskCategory.MATERIAL,
            task_type=TaskType.PRIMITIVE,
            description="Dry hygroscopic material",
            required_params={'material_spool', 'temperature', 'duration'},
            preconditions=['dryer_available(dryer_id)'],
            effects=['material_dried(material_spool)'],
            agent_type='material',
            estimated_duration=14400,  # 4 hours
            requires_equipment=['filament_dryer'],
            skill_level=1
        ))

        # Maintenance tasks
        self.register(TaskTemplate(
            name="clean_nozzle",
            category=TaskCategory.MAINTENANCE,
            task_type=TaskType.PRIMITIVE,
            description="Clean printer nozzle",
            required_params={'printer_id'},
            optional_params={'method': 'cold_pull'},
            preconditions=['not print_in_progress(printer_id)'],
            effects=['nozzle_clean(printer_id)'],
            agent_type='maintenance',
            estimated_duration=600,
            skill_level=2
        ))

        self.register(TaskTemplate(
            name="level_bed",
            category=TaskCategory.MAINTENANCE,
            task_type=TaskType.PRIMITIVE,
            description="Level print bed",
            required_params={'printer_id'},
            optional_params={'method': 'auto'},
            preconditions=['not print_in_progress(printer_id)'],
            effects=['bed_leveled(printer_id)'],
            agent_type='maintenance',
            estimated_duration=300,
            skill_level=2
        ))

        self.register(TaskTemplate(
            name="replace_nozzle",
            category=TaskCategory.MAINTENANCE,
            task_type=TaskType.PRIMITIVE,
            description="Replace worn nozzle",
            required_params={'printer_id', 'new_nozzle'},
            preconditions=['not print_in_progress(printer_id)', 'nozzle_available(new_nozzle)'],
            effects=['nozzle_new(printer_id)'],
            agent_type='maintenance',
            estimated_duration=900,
            skill_level=3
        ))

        # Post-processing
        self.register(TaskTemplate(
            name="remove_supports",
            category=TaskCategory.POST_PROCESSING,
            task_type=TaskType.PRIMITIVE,
            description="Remove support structures",
            required_params={'part_id'},
            optional_params={'method': 'manual'},
            preconditions=['print_complete(part_id)'],
            effects=['supports_removed(part_id)'],
            agent_type='post_processing',
            estimated_duration=300,
            skill_level=2
        ))

        self.register(TaskTemplate(
            name="sand_surface",
            category=TaskCategory.POST_PROCESSING,
            task_type=TaskType.PRIMITIVE,
            description="Sand part surface",
            required_params={'part_id', 'grit_sequence'},
            preconditions=['supports_removed(part_id)'],
            effects=['surface_smoothed(part_id)'],
            agent_type='post_processing',
            estimated_duration=600,
            skill_level=2
        ))

    def register(self, template: TaskTemplate) -> None:
        """Register a task template."""
        self._templates[template.name] = template
        self._by_category[template.category].append(template.name)
        logger.debug(f"Registered task template: {template.name}")

    def get(self, name: str) -> Optional[TaskTemplate]:
        """Get template by name."""
        return self._templates.get(name)

    def get_by_category(self, category: TaskCategory) -> List[TaskTemplate]:
        """Get all templates in a category."""
        return [
            self._templates[name]
            for name in self._by_category[category]
        ]

    def search(self,
               query: str = "",
               category: Optional[TaskCategory] = None,
               agent_type: Optional[str] = None,
               max_duration: Optional[float] = None) -> List[TaskTemplate]:
        """Search templates with filters."""
        results = list(self._templates.values())

        if category:
            results = [t for t in results if t.category == category]

        if agent_type:
            results = [t for t in results if t.agent_type == agent_type]

        if max_duration:
            results = [t for t in results if t.estimated_duration <= max_duration]

        if query:
            query = query.lower()
            results = [
                t for t in results
                if query in t.name.lower() or query in t.description.lower()
            ]

        return results

    def list_all(self) -> List[str]:
        """List all template names."""
        return list(self._templates.keys())
