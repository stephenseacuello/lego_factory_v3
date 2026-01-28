"""
LEGO Factory v3 - SCADA Models
==============================
"""

from models.scada.tags import (
    Tag,
    TagValue,
    TagGroup,
    TagDataType,
    TagCategory,
    TagQuality,
)

from models.scada.alarms import (
    AlarmDefinition,
    AlarmEvent,
    AlarmShelveLog,
    AlarmGroup,
    AlarmPriority,
    AlarmClass,
    AlarmType,
    AlarmState,
)

from models.scada.machines import (
    Machine,
    MachineEvent,
    MachineType,
    ControllerType,
    MachineState,
    ConnectionType,
)

from models.scada.recipes import (
    MasterRecipe,
    ControlRecipe,
    RecipeApproval,
    RecipeParameter,
    RecipeType,
    RecipeStatus,
    ApprovalStatus,
)

__all__ = [
    # Tags
    'Tag',
    'TagValue',
    'TagGroup',
    'TagDataType',
    'TagCategory',
    'TagQuality',
    # Alarms
    'AlarmDefinition',
    'AlarmEvent',
    'AlarmShelveLog',
    'AlarmGroup',
    'AlarmPriority',
    'AlarmClass',
    'AlarmType',
    'AlarmState',
    # Machines
    'Machine',
    'MachineEvent',
    'MachineType',
    'ControllerType',
    'MachineState',
    'ConnectionType',
    # Recipes
    'MasterRecipe',
    'ControlRecipe',
    'RecipeApproval',
    'RecipeParameter',
    'RecipeType',
    'RecipeStatus',
    'ApprovalStatus',
]
