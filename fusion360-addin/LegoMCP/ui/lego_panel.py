"""
LEGO MCP Fusion 360 UI Panel

Provides a user interface panel in Fusion 360 for creating LEGO bricks.
Accessible from the toolbar with a dedicated LEGO panel.
"""

import adsk.core
import adsk.fusion
import traceback
from typing import Dict, Any, Optional, List


# Global variables for handlers
_app = None
_ui = None
_handlers = []


# ============================================================================
# HANDLER CLASSES
# ============================================================================

class BrickCreatedEventHandler(adsk.core.CommandEventHandler):
    """Handler for when a brick is created."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            # Get inputs
            inputs = args.command.commandInputs
            
            # Get dimensions
            width = inputs.itemById('brickWidth').value
            depth = inputs.itemById('brickDepth').value
            height_type = inputs.itemById('brickHeightType').selectedItem.name
            
            # Calculate height in plates
            height_plates = 3  # Default brick
            if height_type == 'Plate':
                height_plates = 1
            elif height_type == 'Tile':
                height_plates = 1
            elif height_type == 'Double Brick':
                height_plates = 6
            
            # Get brick type
            brick_type = inputs.itemById('brickType').selectedItem.name.lower()
            
            # Get features
            hollow = inputs.itemById('hollowInterior').value
            add_studs = inputs.itemById('addStuds').value
            
            # Create the brick using our modeler
            from .brick_modeler import LegoModeler
            
            app = adsk.core.Application.get()
            modeler = LegoModeler(app)
            
            result = modeler.create_brick(
                studs_x=int(width),
                studs_y=int(depth),
                height_plates=height_plates,
                brick_type=brick_type
            )
            
            if result:
                _ui.messageBox(f"Created {int(width)}x{int(depth)} {brick_type}!")
            else:
                _ui.messageBox("Failed to create brick")
                
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BrickCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handler for when the brick creation command is created."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            cmd.isExecutedWhenPreEmpted = False
            
            # Get command inputs
            inputs = cmd.commandInputs
            
            # ============ Dimensions Group ============
            dim_group = inputs.addGroupCommandInput('dimensionsGroup', 'Dimensions')
            dim_group.isExpanded = True
            dim_inputs = dim_group.children
            
            # Width (studs)
            width_input = dim_inputs.addIntegerSliderCommandInput(
                'brickWidth', 'Width (studs)', 1, 16, False
            )
            width_input.valueOne = 2
            
            # Depth (studs)
            depth_input = dim_inputs.addIntegerSliderCommandInput(
                'brickDepth', 'Depth (studs)', 1, 16, False
            )
            depth_input.valueOne = 4
            
            # Height type
            height_dropdown = dim_inputs.addDropDownCommandInput(
                'brickHeightType', 'Height',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            height_dropdown.listItems.add('Plate (1/3 height)', False)
            height_dropdown.listItems.add('Brick (standard)', True)
            height_dropdown.listItems.add('Double Brick', False)
            height_dropdown.listItems.add('Tile (flat)', False)
            
            # ============ Type Group ============
            type_group = inputs.addGroupCommandInput('typeGroup', 'Brick Type')
            type_group.isExpanded = True
            type_inputs = type_group.children
            
            # Brick type
            type_dropdown = type_inputs.addDropDownCommandInput(
                'brickType', 'Type',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            type_dropdown.listItems.add('Standard', True)
            type_dropdown.listItems.add('Plate', False)
            type_dropdown.listItems.add('Tile', False)
            type_dropdown.listItems.add('Slope 45°', False)
            type_dropdown.listItems.add('Slope 33°', False)
            type_dropdown.listItems.add('Slope 65°', False)
            type_dropdown.listItems.add('Technic', False)
            type_dropdown.listItems.add('Round', False)
            
            # ============ Features Group ============
            feat_group = inputs.addGroupCommandInput('featuresGroup', 'Features')
            feat_group.isExpanded = True
            feat_inputs = feat_group.children
            
            # Hollow interior
            feat_inputs.addBoolValueInput('hollowInterior', 'Hollow Interior', True, '', True)
            
            # Add studs
            feat_inputs.addBoolValueInput('addStuds', 'Add Studs', True, '', True)
            
            # Add tubes
            feat_inputs.addBoolValueInput('addTubes', 'Add Bottom Tubes', True, '', True)
            
            # ============ Technic Group ============
            tech_group = inputs.addGroupCommandInput('technicGroup', 'Technic Features')
            tech_group.isExpanded = False
            tech_inputs = tech_group.children
            
            # Technic holes
            tech_inputs.addBoolValueInput('technicHoles', 'Add Technic Holes', True, '', False)
            
            # Hole axis
            hole_axis = tech_inputs.addDropDownCommandInput(
                'holeAxis', 'Hole Axis',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            hole_axis.listItems.add('X (through width)', True)
            hole_axis.listItems.add('Y (through depth)', False)
            
            # Hole type
            hole_type = tech_inputs.addDropDownCommandInput(
                'holeType', 'Hole Type',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            hole_type.listItems.add('Pin (round)', True)
            hole_type.listItems.add('Axle (cross)', False)
            
            # ============ Slope Group ============
            slope_group = inputs.addGroupCommandInput('slopeGroup', 'Slope Settings')
            slope_group.isExpanded = False
            slope_inputs = slope_group.children
            
            # Slope direction
            slope_dir = slope_inputs.addDropDownCommandInput(
                'slopeDirection', 'Direction',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            slope_dir.listItems.add('Front', True)
            slope_dir.listItems.add('Back', False)
            slope_dir.listItems.add('Left', False)
            slope_dir.listItems.add('Right', False)
            
            # ============ Export Options ============
            export_group = inputs.addGroupCommandInput('exportGroup', 'Export')
            export_group.isExpanded = False
            export_inputs = export_group.children
            
            # Auto-export STL
            export_inputs.addBoolValueInput('autoExportSTL', 'Auto-export STL', True, '', False)
            
            # Export path (would need folder selector)
            export_inputs.addStringValueInput('exportPath', 'Export Path', '/output/stl/')
            
            # Connect handlers
            on_execute = BrickCreatedEventHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)
            
            on_input_changed = BrickInputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            _handlers.append(on_input_changed)
            
            on_preview = BrickPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)
            
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BrickInputChangedHandler(adsk.core.InputChangedEventHandler):
    """Handler for when inputs change."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.InputChangedEventArgs):
        try:
            inputs = args.inputs
            changed_input = args.input
            
            # Show/hide groups based on brick type
            if changed_input.id == 'brickType':
                brick_type = changed_input.selectedItem.name.lower()
                
                # Show Technic group for Technic bricks
                tech_group = inputs.itemById('technicGroup')
                if tech_group:
                    tech_group.isVisible = 'technic' in brick_type
                
                # Show slope group for slope bricks
                slope_group = inputs.itemById('slopeGroup')
                if slope_group:
                    slope_group.isVisible = 'slope' in brick_type
                    
        except:
            pass


class BrickPreviewHandler(adsk.core.CommandEventHandler):
    """Handler for preview."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.CommandEventArgs):
        # Preview not implemented - would show brick before creation
        pass


class CatalogCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handler for brick catalog command."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            
            # Search box
            inputs.addStringValueInput('searchBox', 'Search', '')
            
            # Category filter
            cat_dropdown = inputs.addDropDownCommandInput(
                'categoryFilter', 'Category',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            cat_dropdown.listItems.add('All', True)
            cat_dropdown.listItems.add('Bricks', False)
            cat_dropdown.listItems.add('Plates', False)
            cat_dropdown.listItems.add('Tiles', False)
            cat_dropdown.listItems.add('Slopes', False)
            cat_dropdown.listItems.add('Technic', False)
            cat_dropdown.listItems.add('Modified', False)
            cat_dropdown.listItems.add('Round', False)
            
            # Results table (as a selection list)
            results = inputs.addSelectionInput(
                'brickResults', 'Select Brick',
                'Select a brick to create'
            )
            
            # Info text
            inputs.addTextBoxCommandInput(
                'brickInfo', 'Info',
                'Search or select a category to browse bricks.',
                4, True
            )
            
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class ExportCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handler for export command."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            
            # Component selection
            comp_select = inputs.addSelectionInput(
                'componentSelect', 'Component',
                'Select the brick to export'
            )
            comp_select.addSelectionFilter('Occurrences')
            
            # Export format
            format_dropdown = inputs.addDropDownCommandInput(
                'exportFormat', 'Format',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            format_dropdown.listItems.add('STL', True)
            format_dropdown.listItems.add('STEP', False)
            format_dropdown.listItems.add('3MF', False)
            format_dropdown.listItems.add('OBJ', False)
            format_dropdown.listItems.add('F3D (Fusion Archive)', False)
            
            # STL quality
            quality_dropdown = inputs.addDropDownCommandInput(
                'stlQuality', 'STL Quality',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            quality_dropdown.listItems.add('Low (fast)', False)
            quality_dropdown.listItems.add('Medium', True)
            quality_dropdown.listItems.add('High', False)
            quality_dropdown.listItems.add('Ultra', False)
            
            # Output path
            inputs.addStringValueInput(
                'outputPath', 'Output Path',
                '/output/stl/brick.stl'
            )
            
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class PreviewCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handler for preview image command."""
    
    def __init__(self):
        super().__init__()
    
    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            
            # Component selection
            comp_select = inputs.addSelectionInput(
                'componentSelect', 'Component',
                'Select the brick'
            )
            comp_select.addSelectionFilter('Occurrences')
            
            # View angle
            view_dropdown = inputs.addDropDownCommandInput(
                'viewAngle', 'View',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            view_dropdown.listItems.add('Isometric', True)
            view_dropdown.listItems.add('Front', False)
            view_dropdown.listItems.add('Top', False)
            view_dropdown.listItems.add('Right', False)
            view_dropdown.listItems.add('All Views', False)
            
            # Image size
            size_dropdown = inputs.addDropDownCommandInput(
                'imageSize', 'Size',
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            size_dropdown.listItems.add('Thumbnail (256x256)', False)
            size_dropdown.listItems.add('Small (640x480)', False)
            size_dropdown.listItems.add('Medium (800x600)', True)
            size_dropdown.listItems.add('Large (1920x1080)', False)
            
            # Output path
            inputs.addStringValueInput(
                'outputPath', 'Output Path',
                '/output/preview.png'
            )
            
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# ============================================================================
# PANEL CREATION
# ============================================================================

def create_lego_panel():
    """
    Create the LEGO MCP panel in Fusion 360.
    
    This adds:
    - A LEGO tab in the toolbar
    - Create Brick command
    - Browse Catalog command  
    - Export command
    - Preview command
    """
    global _app, _ui
    
    _app = adsk.core.Application.get()
    _ui = _app.userInterface
    
    try:
        # Get the DESIGN workspace
        design_ws = _ui.workspaces.itemById('FusionSolidEnvironment')
        if not design_ws:
            return False
        
        # Get toolbar panels
        toolbar_panels = design_ws.toolbarPanels
        
        # Check if our panel already exists
        lego_panel = toolbar_panels.itemById('LegoMCPPanel')
        if lego_panel:
            lego_panel.deleteMe()
        
        # Create new panel
        lego_panel = toolbar_panels.add('LegoMCPPanel', 'LEGO', 'SelectPanel', False)
        
        # ============ Create Brick Command ============
        create_cmd_def = _ui.commandDefinitions.itemById('LegoCreateBrick')
        if create_cmd_def:
            create_cmd_def.deleteMe()
        
        create_cmd_def = _ui.commandDefinitions.addButtonDefinition(
            'LegoCreateBrick',
            'Create Brick',
            'Create a new LEGO brick',
            './resources/create_brick'  # Icon folder
        )
        
        # Add handler
        on_create_created = BrickCommandCreatedHandler()
        create_cmd_def.commandCreated.add(on_create_created)
        _handlers.append(on_create_created)
        
        # Add to panel
        lego_panel.controls.addCommand(create_cmd_def)
        
        # ============ Catalog Command ============
        catalog_cmd_def = _ui.commandDefinitions.itemById('LegoCatalog')
        if catalog_cmd_def:
            catalog_cmd_def.deleteMe()
        
        catalog_cmd_def = _ui.commandDefinitions.addButtonDefinition(
            'LegoCatalog',
            'Brick Catalog',
            'Browse the LEGO brick catalog',
            './resources/catalog'
        )
        
        on_catalog_created = CatalogCommandCreatedHandler()
        catalog_cmd_def.commandCreated.add(on_catalog_created)
        _handlers.append(on_catalog_created)
        
        lego_panel.controls.addCommand(catalog_cmd_def)
        
        # ============ Export Command ============
        export_cmd_def = _ui.commandDefinitions.itemById('LegoExport')
        if export_cmd_def:
            export_cmd_def.deleteMe()
        
        export_cmd_def = _ui.commandDefinitions.addButtonDefinition(
            'LegoExport',
            'Export',
            'Export brick to STL/STEP/3MF',
            './resources/export'
        )
        
        on_export_created = ExportCommandCreatedHandler()
        export_cmd_def.commandCreated.add(on_export_created)
        _handlers.append(on_export_created)
        
        lego_panel.controls.addCommand(export_cmd_def)
        
        # ============ Preview Command ============
        preview_cmd_def = _ui.commandDefinitions.itemById('LegoPreview')
        if preview_cmd_def:
            preview_cmd_def.deleteMe()
        
        preview_cmd_def = _ui.commandDefinitions.addButtonDefinition(
            'LegoPreview',
            'Preview',
            'Generate preview images',
            './resources/preview'
        )
        
        on_preview_created = PreviewCommandCreatedHandler()
        preview_cmd_def.commandCreated.add(on_preview_created)
        _handlers.append(on_preview_created)
        
        lego_panel.controls.addCommand(preview_cmd_def)
        
        # Add separator
        lego_panel.controls.addSeparator()
        
        # ============ Settings/Help ============
        # Could add settings and help commands here
        
        return True
        
    except:
        if _ui:
            _ui.messageBox('Failed to create LEGO panel:\n{}'.format(traceback.format_exc()))
        return False


def destroy_lego_panel():
    """Remove the LEGO panel from Fusion 360."""
    try:
        # Get design workspace
        design_ws = _ui.workspaces.itemById('FusionSolidEnvironment')
        if design_ws:
            # Remove panel
            panel = design_ws.toolbarPanels.itemById('LegoMCPPanel')
            if panel:
                panel.deleteMe()
        
        # Remove command definitions
        for cmd_id in ['LegoCreateBrick', 'LegoCatalog', 'LegoExport', 'LegoPreview']:
            cmd_def = _ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                cmd_def.deleteMe()
        
        return True
        
    except:
        return False


# ============================================================================
# ENTRY POINTS
# ============================================================================

def run(context):
    """Called when add-in is started."""
    global _app, _ui
    
    _app = adsk.core.Application.get()
    _ui = _app.userInterface
    
    create_lego_panel()


def stop(context):
    """Called when add-in is stopped."""
    destroy_lego_panel()
    
    # Clear handlers
    _handlers.clear()
