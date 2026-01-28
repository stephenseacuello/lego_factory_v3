"""
CAMProcessor - CNC Milling toolpath generation for Fusion 360

This module sets up CAM operations and generates G-code for CNC milling
of LEGO bricks. Uses Fusion 360's built-in CAM capabilities.
"""

import adsk.core
import adsk.fusion
import adsk.cam
import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class ToolConfig:
    """CNC tool configuration."""
    tool_id: str
    number: int
    type: str  # "flat_endmill", "ball_endmill", "drill", etc.
    diameter_mm: float
    flute_length_mm: float
    overall_length_mm: float
    flutes: int = 2
    corner_radius_mm: float = 0.0
    
    
@dataclass 
class MaterialConfig:
    """Material-specific cutting parameters."""
    name: str
    rpm: int
    feed_mm_min: float
    plunge_mm_min: float
    doc_mm: float  # Depth of cut
    woc_percent: float  # Width of cut (stepover %)


class ToolLibrary:
    """Manages CNC tool definitions from JSON library."""
    
    def __init__(self, library_path: str = None):
        self.tools: Dict[str, Dict] = {}
        self.materials: Dict[str, MaterialConfig] = {}
        self.toolpaths: Dict[str, Dict] = {}
        
        if library_path and os.path.exists(library_path):
            self._load_library(library_path)
        else:
            self._load_defaults()
    
    def _load_library(self, path: str):
        """Load tool library from JSON file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Load tools
            for tool in data.get('tools', []):
                self.tools[tool['id']] = tool
            
            # Load materials
            for mat_id, mat_data in data.get('material_properties', {}).items():
                # Get feeds/speeds from first tool as defaults
                feeds = {}
                if self.tools:
                    first_tool = list(self.tools.values())[0]
                    feeds = first_tool.get('feeds_speeds', {}).get(mat_id, {})
                
                self.materials[mat_id] = MaterialConfig(
                    name=mat_data.get('name', mat_id),
                    rpm=feeds.get('rpm', 10000),
                    feed_mm_min=feeds.get('feed_mm_min', 1000),
                    plunge_mm_min=feeds.get('plunge_mm_min', 400),
                    doc_mm=feeds.get('doc_mm', 1.0),
                    woc_percent=feeds.get('woc_percent', 40)
                )
            
            # Load recommended toolpaths
            self.toolpaths = data.get('recommended_toolpaths', {})
            
        except Exception as e:
            print(f"Error loading tool library: {e}")
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default tool configurations."""
        self.tools = {
            "flat_3mm": {
                "id": "flat_3mm",
                "number": 2,
                "type": "flat_endmill",
                "geometry": {"diameter": 3.0, "flute_length": 12.0, "overall_length": 50.0},
                "cutting": {"flutes": 2},
                "feeds_speeds": {
                    "abs": {"rpm": 18000, "feed_mm_min": 1500, "plunge_mm_min": 500, "doc_mm": 1.0, "woc_percent": 40}
                }
            },
            "flat_1mm": {
                "id": "flat_1mm",
                "number": 4,
                "type": "flat_endmill",
                "geometry": {"diameter": 1.0, "flute_length": 4.0, "overall_length": 38.0},
                "cutting": {"flutes": 2},
                "feeds_speeds": {
                    "abs": {"rpm": 24000, "feed_mm_min": 600, "plunge_mm_min": 200, "doc_mm": 0.3, "woc_percent": 30}
                }
            }
        }
        
        self.materials = {
            "abs": MaterialConfig("ABS Plastic", 18000, 1500, 500, 1.0, 40),
            "delrin": MaterialConfig("Delrin/Acetal", 15000, 1200, 400, 1.5, 40),
            "hdpe": MaterialConfig("HDPE", 12000, 1000, 350, 1.5, 45),
            "aluminum": MaterialConfig("Aluminum 6061", 10000, 600, 200, 0.5, 30),
        }
    
    def get_tool(self, tool_id: str) -> Optional[Dict]:
        """Get tool configuration by ID."""
        return self.tools.get(tool_id)
    
    def get_tool_feeds(self, tool_id: str, material: str) -> Dict:
        """Get feeds and speeds for a tool/material combination."""
        tool = self.tools.get(tool_id)
        if tool:
            return tool.get('feeds_speeds', {}).get(material, {})
        return {}
    
    def get_material(self, material_id: str) -> Optional[MaterialConfig]:
        """Get material configuration."""
        return self.materials.get(material_id)


# Post processor mappings - platform-aware paths
POST_PROCESSORS = {
    "generic_3axis": {
        "name": "Generic Fanuc",
        "extension": ".nc",
        "search_terms": ["fanuc", "generic"]
    },
    "haas_mini": {
        "name": "Haas",
        "extension": ".nc",
        "search_terms": ["haas"]
    },
    "tormach": {
        "name": "Tormach",
        "extension": ".nc",
        "search_terms": ["tormach", "pathpilot"]
    },
    "shapeoko": {
        "name": "GRBL",
        "extension": ".nc",
        "search_terms": ["grbl", "carbide", "shapeoko"]
    },
    "grbl": {
        "name": "GRBL",
        "extension": ".nc",
        "search_terms": ["grbl"]
    },
    "linuxcnc": {
        "name": "LinuxCNC",
        "extension": ".ngc",
        "search_terms": ["linuxcnc", "emc"]
    },
    "mach3": {
        "name": "Mach3",
        "extension": ".nc",
        "search_terms": ["mach3", "mach4"]
    },
    "bantam": {
        "name": "Bantam Tools (TinyG)",
        "extension": ".nc",
        "search_terms": ["grbl", "tinyg", "bantam"],
        "controller": "TinyG",
        "notes": "Bantam Desktop CNC uses TinyG controller, GRBL-compatible"
    }
}


# =============================================================================
# ALUMINUM LEGO CONSTANTS
# =============================================================================

# Bantam Desktop CNC specifications (must match standalone workflow)
BANTAM_SPECS = {
    "name": "Bantam Tools Desktop CNC",
    "controller": "TinyG",
    "work_envelope": {"x": 140, "y": 114, "z": 60},  # mm
    "spindle_rpm_min": 2000,
    "spindle_rpm_max": 10000,
    "spindle_power_watts": 150,
    "max_feed_rate": 2540,  # mm/min
    "max_rapid_rate": 2540,  # mm/min
    "resolution": 0.001,  # mm
    "tool_holder": "ER11",
    "max_tool_diameter": 6.35,  # 1/4" = 6.35mm
}

# LEGO brick standard dimensions (mm)
LEGO_DIMS = {
    "stud_diameter": 4.8,
    "stud_height": 1.7,
    "pitch": 8.0,  # Stud-to-stud center distance
    "plate_height": 3.2,
    "brick_height": 9.6,  # 3 plates
    "wall_thickness": 1.5,
    "tube_od": 6.51,  # Outer diameter of bottom tubes
    "tube_id": 4.8,   # Inner diameter (matches stud)
    "tolerance": 0.05,  # Target tolerance
}

# Aluminum 6061-T6 cutting parameters optimized for Bantam
ALUMINUM_PARAMS = {
    "material": "6061-T6",
    "sfm": 300,  # Surface feet per minute (conservative for desktop CNC)
    "chip_load_2mm": 0.025,  # mm/tooth for 2mm endmill
    "chip_load_3mm": 0.035,  # mm/tooth for 3mm endmill
    "doc_roughing": 0.5,     # Depth of cut - roughing (mm)
    "doc_finishing": 0.15,   # Depth of cut - finishing (mm)
    "woc_roughing": 0.4,     # Width of cut as % of tool diameter
    "woc_finishing": 0.1,
    "stock_to_leave": 0.2,   # mm left for finishing pass
    "plunge_rate_factor": 0.3,  # Plunge at 30% of feed rate
}

# Optimized 2-tool strategy for aluminum LEGO
ALUMINUM_TOOLS = {
    "T1_roughing": {
        "id": "flat_3mm_aluminum",
        "number": 1,
        "type": "flat_endmill",
        "diameter_mm": 3.0,
        "flute_length_mm": 12.0,
        "overall_length_mm": 50.0,
        "flutes": 2,
        "description": "3mm Flat Endmill - Facing & Roughing",
        "operations": ["facing", "adaptive_roughing", "pocket_roughing"]
    },
    "T2_finishing": {
        "id": "flat_2mm_aluminum",
        "number": 2,
        "type": "flat_endmill",
        "diameter_mm": 2.0,
        "flute_length_mm": 8.0,
        "overall_length_mm": 38.0,
        "flutes": 2,
        "description": "2mm Flat Endmill - Finishing & Detail",
        "operations": ["contour_finishing", "stud_finishing", "tube_milling"]
    }
}


class CAMProcessor:
    """
    Generates CNC milling toolpaths for LEGO bricks.
    
    Uses Fusion 360's CAM module to create professional-quality
    toolpaths with adaptive clearing, contour finishing, etc.
    """
    
    def __init__(self, app: adsk.core.Application, tool_library_path: str = None):
        self.app = app
        
        # Load tool library
        if tool_library_path is None:
            # Try to find tool library relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tool_library_path = os.path.join(current_dir, '..', 'resources', 'tool_library.json')
        
        self.tool_library = ToolLibrary(tool_library_path)
        
    @property
    def cam(self) -> Optional[adsk.cam.CAM]:
        """Get CAM product, create if needed."""
        try:
            doc = self.app.activeDocument
            if not doc:
                raise Exception("No active document. Please create or open a design first.")

            products = doc.products
            if not products:
                raise Exception("No products in document.")

            # Try to get existing CAM
            cam = adsk.cam.CAM.cast(products.itemByProductType('CAMProductType'))
            if not cam:
                # Create CAM product - switch to CAM workspace first
                ui = self.app.userInterface
                ws = ui.workspaces.itemById('CAMEnvironment')
                if ws and not ws.isActive:
                    ws.activate()

                # Now try to get/create CAM
                cam = adsk.cam.CAM.cast(products.itemByProductType('CAMProductType'))
                if not cam:
                    cam = adsk.cam.CAM.cast(products.add('CAMProductType'))

            return cam
        except Exception as e:
            raise Exception(f"Cannot access CAM workspace: {str(e)}")
    
    def _cm(self, mm: float) -> float:
        """Convert mm to cm."""
        return mm / 10.0
    
    def setup_milling(
        self,
        component_name: str,
        material: str = "abs",
        stock_offset_mm: float = 1.0
    ) -> adsk.cam.Setup:
        """
        Create a milling setup for a component.
        
        Args:
            component_name: Name of component to machine
            material: Material type (abs, delrin, aluminum, etc.)
            stock_offset_mm: Extra stock around part
            
        Returns:
            CAM Setup object
        """
        cam = self.cam
        if not cam:
            raise Exception("Could not access CAM workspace")
        
        # Find the component/body to machine
        design = adsk.fusion.Design.cast(self.app.activeProduct)
        target_comp = None
        for occ in design.rootComponent.occurrences:
            if occ.component.name == component_name:
                target_comp = occ.component
                break
        
        if not target_comp:
            raise Exception(f"Component not found: {component_name}")
        
        # Create setup
        setups = cam.setups
        setup_input = setups.createInput(adsk.cam.OperationTypes.MillingOperation)
        
        # Configure setup
        setup = setups.add(setup_input)
        setup.name = f"Mill_{component_name}"
        
        # Set models to machine
        models = adsk.core.ObjectCollection.create()
        for body in target_comp.bRepBodies:
            models.add(body)
        setup.models = models
        
        # Configure stock
        setup.stockMode = adsk.cam.SetupStockMode.RelativeBoxStock
        setup.stockOffsetMode = adsk.cam.StockOffsetModes.Simple
        setup.stockSideOffset = adsk.core.ValueInput.createByReal(self._cm(stock_offset_mm))
        setup.stockTopOffset = adsk.core.ValueInput.createByReal(self._cm(stock_offset_mm))
        setup.stockBottomOffset = adsk.core.ValueInput.createByReal(0)  # No bottom offset
        
        # Set WCS origin to bottom-left-front of stock
        setup.wcsOriginMode = adsk.cam.WCSOriginModes.StockBoxPoint
        
        return setup
    
    def add_adaptive_clearing(
        self,
        setup: adsk.cam.Setup,
        tool_id: str = "flat_3mm",
        material: str = "abs",
        leave_stock_mm: float = 0.2
    ) -> adsk.cam.Operation:
        """
        Add adaptive clearing (roughing) operation.
        
        Adaptive clearing is Fusion 360's HSM-style roughing strategy
        that maintains constant tool engagement for faster, smoother cuts.
        """
        cam = self.cam
        
        # Get tool and material from library
        tool_data = self.tool_library.get_tool(tool_id)
        feeds = self.tool_library.get_tool_feeds(tool_id, material)
        
        if not tool_data:
            raise ValueError(f"Tool not found: {tool_id}")
        
        # Extract parameters
        tool_diameter = tool_data.get('geometry', {}).get('diameter', 3.0)
        rpm = feeds.get('rpm', 18000)
        feed = feeds.get('feed_mm_min', 1500)
        plunge = feeds.get('plunge_mm_min', 500)
        doc = feeds.get('doc_mm', 1.0)
        woc_percent = feeds.get('woc_percent', 40)
        
        # Get adaptive clearing template from library
        template_lib = cam.templateLibrary
        templates = template_lib.templates
        
        # Find adaptive clearing template
        adaptive_template = None
        for template in templates:
            if 'adaptive' in template.name.lower():
                adaptive_template = template
                break
        
        if not adaptive_template:
            # Fall back to URL-based template
            template_url = 'systempreferences://Strategies/Milling/Adaptive%20Clearing'
        else:
            template_url = adaptive_template.url
        
        # Create operation
        operations = setup.operations
        op_input = operations.createInput(template_url)
        
        op = operations.add(op_input)
        op.name = f"Adaptive Roughing ({tool_id})"
        
        # Configure parameters
        params = op.parameters
        
        # Set tool parameters
        self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter))
        
        # Set feeds and speeds
        self._set_param_safe(params, "spindleSpeed", rpm)
        self._set_param_safe(params, "feedrate", feed / 60.0)  # Convert to mm/s
        self._set_param_safe(params, "plungeRate", plunge / 60.0)
        
        # Set cutting parameters
        self._set_param_safe(params, "maximumStepdown", self._cm(doc))
        self._set_param_safe(params, "optimalLoad", self._cm(tool_diameter * woc_percent / 100))
        self._set_param_safe(params, "stockToLeave", self._cm(leave_stock_mm))
        
        return op
    
    def _set_param_safe(self, params, name: str, value):
        """Safely set a parameter value."""
        try:
            param = params.itemByName(name)
            if param:
                if isinstance(value, (int, float)):
                    param.value = adsk.core.ValueInput.createByReal(float(value))
                else:
                    param.value = value
        except:
            pass  # Parameter may not exist for all operation types
    
    def add_contour_finishing(
        self,
        setup: adsk.cam.Setup,
        tool_id: str = "flat_1mm",
        material: str = "abs"
    ) -> adsk.cam.Operation:
        """
        Add contour (2D) finishing operation for walls.
        """
        cam = self.cam

        # Get tool and material from library
        tool_data = self.tool_library.get_tool(tool_id)
        feeds = self.tool_library.get_tool_feeds(tool_id, material)
        mat = self.tool_library.get_material(material)

        # Default values if not in library
        if not tool_data:
            tool_diameter = 1.0
        else:
            tool_diameter = tool_data.get('geometry', {}).get('diameter', 1.0)

        rpm = feeds.get('rpm', mat.rpm if mat else 24000)
        feed = feeds.get('feed_mm_min', mat.feed_mm_min if mat else 600)
        doc = feeds.get('doc_mm', mat.doc_mm if mat else 0.3)

        # Find contour template
        template_lib = cam.templateLibrary
        templates = template_lib.templates

        contour_template = None
        for template in templates:
            if 'contour' in template.name.lower() and '2d' in template.name.lower():
                contour_template = template
                break

        if contour_template:
            template_url = contour_template.url
        else:
            template_url = 'systempreferences://Strategies/Milling/2D%20Contour'

        operations = setup.operations
        op_input = operations.createInput(template_url)

        op = operations.add(op_input)
        op.name = f"Contour Finishing ({tool_id})"

        # Configure parameters safely
        params = op.parameters

        self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter))
        self._set_param_safe(params, "spindleSpeed", rpm)
        self._set_param_safe(params, "feedrate", feed * 0.6 / 60.0)  # Slower for finishing
        self._set_param_safe(params, "maximumStepdown", self._cm(doc * 2))
        self._set_param_safe(params, "stockToLeave", 0)  # No stock to leave (final pass)

        return op
    
    def add_parallel_finishing(
        self,
        setup: adsk.cam.Setup,
        tool_id: str = "flat_1mm",
        material: str = "abs",
        stepover_mm: float = 0.3
    ) -> adsk.cam.Operation:
        """
        Add parallel (raster) finishing for top surfaces.
        """
        cam = self.cam

        # Get tool and material from library
        tool_data = self.tool_library.get_tool(tool_id)
        feeds = self.tool_library.get_tool_feeds(tool_id, material)
        mat = self.tool_library.get_material(material)

        # Default values if not in library
        if not tool_data:
            tool_diameter = 1.0
        else:
            tool_diameter = tool_data.get('geometry', {}).get('diameter', 1.0)

        rpm = feeds.get('rpm', mat.rpm if mat else 24000)
        feed = feeds.get('feed_mm_min', mat.feed_mm_min if mat else 600)

        # Find parallel template
        template_lib = cam.templateLibrary
        templates = template_lib.templates

        parallel_template = None
        for template in templates:
            if 'parallel' in template.name.lower():
                parallel_template = template
                break

        if parallel_template:
            template_url = parallel_template.url
        else:
            template_url = 'systempreferences://Strategies/Milling/Parallel'

        operations = setup.operations
        op_input = operations.createInput(template_url)

        op = operations.add(op_input)
        op.name = f"Parallel Finishing ({tool_id})"

        # Configure parameters safely
        params = op.parameters

        self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter))
        self._set_param_safe(params, "spindleSpeed", rpm)
        self._set_param_safe(params, "feedrate", feed * 0.5 / 60.0)  # Slower for finishing
        self._set_param_safe(params, "stepover", self._cm(stepover_mm))

        return op
    
    def add_drilling(
        self,
        setup: adsk.cam.Setup,
        positions: List[tuple],
        depth_mm: float,
        tool_id: str = "drill_4.8mm",
        material: str = "abs",
        peck: bool = True
    ) -> Optional[adsk.cam.Operation]:
        """
        Add drilling operation for specific positions.
        
        Useful for stud holes if milling from bottom, or for
        creating locating holes.
        
        Args:
            setup: CAM setup
            positions: List of (x, y) tuples in mm
            depth_mm: Drilling depth
            tool_id: Drill tool ID from library
            material: Material for feeds/speeds
            peck: Use peck drilling (recommended for deeper holes)
            
        Returns:
            Drilling operation or None if failed
        """
        if not positions:
            return None
            
        cam = self.cam
        
        # Get tool info
        tool_data = self.tool_library.get_tool(tool_id)
        feeds = self.tool_library.get_tool_feeds(tool_id, material)
        
        # Default drill parameters if not in library
        if not tool_data:
            tool_diameter = 4.8  # LEGO stud diameter
            rpm = 8000
            feed = 400
            peck_depth = 2.0
        else:
            tool_diameter = tool_data.get('geometry', {}).get('diameter', 4.8)
            rpm = feeds.get('rpm', 8000)
            feed = feeds.get('feed_mm_min', 400)
            peck_depth = feeds.get('peck_depth_mm', 2.0)
        
        try:
            # Find drilling template
            template_lib = cam.templateLibrary
            templates = template_lib.templates
            
            drill_template = None
            template_name = "Peck Drilling" if peck else "Drilling"
            
            for template in templates:
                if template_name.lower() in template.name.lower():
                    drill_template = template
                    break
            
            if drill_template:
                template_url = drill_template.url
            else:
                template_url = 'systempreferences://Strategies/Drilling/Peck%20Drilling'
            
            # Create operation
            operations = setup.operations
            op_input = operations.createInput(template_url)
            
            op = operations.add(op_input)
            op.name = f"Drilling ({tool_id})"
            
            # Configure parameters
            params = op.parameters
            
            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter))
            self._set_param_safe(params, "spindleSpeed", rpm)
            self._set_param_safe(params, "feedrate", feed / 60.0)
            self._set_param_safe(params, "depth", self._cm(depth_mm))
            
            if peck:
                self._set_param_safe(params, "peckDepth", self._cm(peck_depth))
            
            # Note: Hole positions would need to be selected via geometry
            # In practice, this requires selecting circular edges or points
            # which depends on the specific model geometry
            
            return op
            
        except Exception as e:
            print(f"Error creating drilling operation: {e}")
            return None
    
    def _configure_tool_by_id(self, operation: adsk.cam.Operation, tool_id: str):
        """Configure tool for an operation using tool library."""
        tool_data = self.tool_library.get_tool(tool_id)
        if not tool_data:
            return

        try:
            op_params = operation.parameters
            geom = tool_data.get('geometry', {})

            # Tool diameter
            diameter = geom.get('diameter', 3.0)
            self._set_param_safe(op_params, "tool_diameter", self._cm(diameter))

            # Flute length
            flute_length = geom.get('flute_length', 12.0)
            self._set_param_safe(op_params, "tool_fluteLength", self._cm(flute_length))
        except:
            pass  # Tool configuration varies by operation type
    
    def generate_toolpaths(self, setup: adsk.cam.Setup) -> bool:
        """
        Generate all toolpaths in a setup.
        
        Returns:
            True if successful
        """
        cam = self.cam
        
        # Generate toolpath for all operations
        future = cam.generateToolpath(setup)
        
        # Wait for generation to complete
        while not future.isGenerationCompleted:
            adsk.doEvents()
            
        return future.isGenerationCompleted
    
    def export_gcode(
        self,
        setup: adsk.cam.Setup,
        output_path: str,
        machine: str = "grbl"
    ) -> Dict[str, Any]:
        """
        Export G-code using appropriate post processor.
        
        Args:
            setup: CAM setup with generated toolpaths
            output_path: Full path for output G-code file
            machine: Target machine type
            
        Returns:
            Dict with path, estimated time, operations, tools
        """
        cam = self.cam
        
        # Get post processor info
        post_info = POST_PROCESSORS.get(machine, POST_PROCESSORS["grbl"])
        search_terms = post_info.get("search_terms", ["grbl"])
        extension = post_info.get("extension", ".nc")
        
        # Ensure output has correct extension
        if not output_path.endswith(extension):
            base = os.path.splitext(output_path)[0]
            output_path = base + extension
        
        # Find post processor in library
        post_library = cam.postLibrary
        posts = post_library.posts
        
        post_url = None
        for post in posts:
            post_name_lower = post.name.lower()
            for term in search_terms:
                if term in post_name_lower:
                    post_url = post.url
                    break
            if post_url:
                break
        
        # Fall back to system post if not found
        if not post_url:
            # Try system preferences path
            post_url = f"systempreferences://Posts/{search_terms[0]}.cps"
        
        # Create post process input
        try:
            post_input = adsk.cam.PostProcessInput.create(
                output_path,
                post_url,
                setup,
                f"LEGO Brick - {machine}"
            )
            post_input.isOpenInEditor = False
            
            # Post process
            cam.postProcess(post_input)
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Post processing failed: {str(e)}",
                "path": output_path
            }
        
        # Gather statistics from operations
        operations = []
        tools_used = []
        total_time_sec = 0
        
        for op in setup.operations:
            operations.append(op.name)
            
            # Try to get operation statistics
            try:
                if hasattr(op, 'machiningTime'):
                    total_time_sec += op.machiningTime
            except:
                pass
        
        # If no time calculated, estimate based on operations
        if total_time_sec == 0:
            total_time_sec = len(operations) * 300  # 5 min per operation estimate
        
        return {
            "success": True,
            "path": output_path,
            "machine": machine,
            "post_processor": post_info.get("name", machine),
            "operations": operations,
            "tools": tools_used if tools_used else ["flat_3mm", "flat_1mm"],
            "estimated_time_min": total_time_sec / 60.0
        }
    
    def create_standard_brick_toolpath(
        self,
        component_name: str,
        material: str = "abs",
        machine: str = "grbl",
        output_path: str = None
    ) -> Dict[str, Any]:
        """
        Create complete milling toolpath for a standard LEGO brick.
        
        This is a convenience method that sets up a recommended
        toolpath strategy for LEGO bricks:
        1. Adaptive clearing (roughing) with 3mm endmill
        2. Contour finishing (walls) with 1mm endmill
        3. Parallel finishing (top) with 1mm endmill
        
        Args:
            component_name: Brick component to machine
            material: Stock material
            machine: Target CNC machine
            output_path: G-code output path
            
        Returns:
            Result dict with G-code path and stats
        """
        # Create setup
        setup = self.setup_milling(component_name, material)
        
        # Add operations
        self.add_adaptive_clearing(setup, "flat_3mm", material)
        self.add_contour_finishing(setup, "flat_1mm", material)
        self.add_parallel_finishing(setup, "flat_1mm", material)
        
        # Generate toolpaths
        success = self.generate_toolpaths(setup)
        if not success:
            raise Exception("Toolpath generation failed")
        
        # Export G-code
        if not output_path:
            default_output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", "gcode", "milling")
            os.makedirs(default_output_dir, exist_ok=True)
            output_path = os.path.join(default_output_dir, f"{component_name}.nc")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        return self.export_gcode(setup, output_path, machine)

    # =========================================================================
    # LASER ENGRAVING SUPPORT
    # =========================================================================

    def create_laser_engrave_toolpath(
        self,
        component_name: str,
        preset: str = "abs_engrave_medium",
        mode: str = "raster",
        output_path: str = None,
        machine: str = "laser_grbl"
    ) -> Dict[str, Any]:
        """
        Create laser engraving toolpath for LEGO bricks.

        Supports engraving text, logos, serial numbers, and QR codes
        on LEGO brick surfaces.

        Args:
            component_name: Name of component with engrave features
            preset: Laser preset from laser_presets.json
            mode: 'raster' for filled areas, 'vector' for outlines
            output_path: Output path for G-code
            machine: Target laser machine (laser_grbl, laser_co2)

        Returns:
            Dict with path, settings, and estimated time
        """
        # Load laser presets
        current_dir = os.path.dirname(os.path.abspath(__file__))
        presets_path = os.path.join(current_dir, '..', 'resources', 'laser_presets.json')

        try:
            with open(presets_path, 'r') as f:
                presets_data = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Failed to load laser presets: {e}"}

        # Get preset settings
        preset_settings = presets_data.get('presets', {}).get(preset)
        if not preset_settings:
            available = list(presets_data.get('presets', {}).keys())
            return {
                "success": False,
                "error": f"Unknown preset: {preset}. Available: {available}"
            }

        # Get machine config
        machines_path = os.path.join(current_dir, '..', 'resources', 'machines.json')
        machine_config = None
        try:
            with open(machines_path, 'r') as f:
                machines_data = json.load(f)
            for m in machines_data.get('machines', []):
                if m['id'] == machine:
                    machine_config = m
                    break
        except:
            pass

        # Build laser G-code settings
        power_percent = preset_settings.get('power_percent', 20)
        speed_mm_min = preset_settings.get('speed_mm_min', 800)
        passes = preset_settings.get('passes', 1)
        air_assist = preset_settings.get('air_assist', True)

        # Determine output path
        if not output_path:
            default_output_dir = os.path.join(
                os.path.expanduser("~"),
                "Documents", "LegoMCP", "exports", "gcode", "laser"
            )
            os.makedirs(default_output_dir, exist_ok=True)
            output_path = os.path.join(default_output_dir, f"{component_name}_laser.nc")

        # Generate laser G-code header
        gcode_lines = [
            "; LEGO MCP Laser Engrave G-code",
            f"; Component: {component_name}",
            f"; Preset: {preset} ({preset_settings.get('name', preset)})",
            f"; Mode: {mode}",
            f"; Power: {power_percent}%",
            f"; Speed: {speed_mm_min} mm/min",
            f"; Passes: {passes}",
            "",
            "; Safety warnings:",
        ]

        # Add safety notes from presets
        for note in presets_data.get('safety_notes', []):
            gcode_lines.append(f"; - {note}")

        gcode_lines.extend([
            "",
            "; Machine setup",
            "G21 ; mm mode",
            "G90 ; absolute positioning",
            "M5 ; laser off",
            "",
        ])

        if air_assist:
            gcode_lines.append("M8 ; air assist on")

        gcode_lines.extend([
            "",
            f"; Power setting: S{int(power_percent * 10)} (0-1000 scale)",
            f"S{int(power_percent * 10)}",
            "",
            "; Homing",
            "G28 ; home all axes",
            "",
            "; Move to work origin",
            "G0 X0 Y0 F3000",
            "",
            f"; Begin engrave at {speed_mm_min} mm/min",
            f"G1 F{speed_mm_min}",
            "",
            "; TODO: Actual engrave paths would be generated from",
            "; the component's sketch/face geometry by Fusion 360 CAM",
            "; This is a template - real toolpaths require CAM setup",
            "",
            "; End of operation",
            "M5 ; laser off",
        ])

        if air_assist:
            gcode_lines.append("M9 ; air assist off")

        gcode_lines.extend([
            "G0 X0 Y0 ; return to origin",
            "M2 ; program end",
            ""
        ])

        # Write G-code file
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            with open(output_path, 'w') as f:
                f.write('\n'.join(gcode_lines))
        except Exception as e:
            return {"success": False, "error": f"Failed to write G-code: {e}"}

        # Estimate time based on passes and typical engrave area
        estimated_time_min = passes * 2.0  # ~2 min per pass estimate

        return {
            "success": True,
            "path": output_path,
            "component": component_name,
            "preset": preset,
            "preset_name": preset_settings.get('name', preset),
            "mode": mode,
            "machine": machine,
            "settings": {
                "power_percent": power_percent,
                "speed_mm_min": speed_mm_min,
                "passes": passes,
                "air_assist": air_assist
            },
            "material_notes": presets_data.get('material_compatibility', {}).get(
                preset_settings.get('material', 'abs'), {}
            ),
            "estimated_time_min": estimated_time_min,
            "safety_notes": presets_data.get('safety_notes', [])
        }

    def get_laser_presets(self, material: str = None) -> Dict[str, Any]:
        """
        Get available laser engraving presets.

        Args:
            material: Filter by material (abs, pla, etc.)

        Returns:
            Dict with presets and material compatibility info
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        presets_path = os.path.join(current_dir, '..', 'resources', 'laser_presets.json')

        try:
            with open(presets_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            return {"error": f"Failed to load presets: {e}"}

        presets = data.get('presets', {})

        # Filter by material if specified
        if material:
            presets = {
                k: v for k, v in presets.items()
                if v.get('material', '').lower() == material.lower()
            }

        return {
            "presets": presets,
            "applications": data.get('lego_applications', {}),
            "material_compatibility": data.get('material_compatibility', {}),
            "safety_notes": data.get('safety_notes', [])
        }

    # =========================================================================
    # ALUMINUM LEGO MILLING - BANTAM DESKTOP CNC
    # =========================================================================

    def calculate_aluminum_feeds_speeds(
        self,
        tool_diameter_mm: float,
        flutes: int = 2
    ) -> Dict[str, float]:
        """
        Calculate feeds and speeds for aluminum 6061-T6 on Bantam Desktop CNC.

        Uses SFM-based calculation with conservative parameters for desktop CNC.

        Args:
            tool_diameter_mm: Tool diameter in mm
            flutes: Number of flutes (default 2)

        Returns:
            Dict with rpm, feed_rate, plunge_rate, chip_load
        """
        import math

        sfm = ALUMINUM_PARAMS["sfm"]

        # RPM = SFM × 12 / (π × Diameter_inches)
        tool_diameter_inch = tool_diameter_mm / 25.4
        rpm = int((sfm * 12) / (math.pi * tool_diameter_inch))

        # Clamp to Bantam's spindle range
        rpm = max(BANTAM_SPECS["spindle_rpm_min"], min(rpm, BANTAM_SPECS["spindle_rpm_max"]))

        # Chip load based on tool size
        if tool_diameter_mm <= 2.0:
            chip_load = ALUMINUM_PARAMS["chip_load_2mm"]
        elif tool_diameter_mm <= 3.0:
            chip_load = ALUMINUM_PARAMS["chip_load_3mm"]
        else:
            chip_load = 0.050  # Larger tools

        # Feed rate = RPM × Flutes × Chip load
        feed_rate = rpm * flutes * chip_load

        # Clamp feed rate to Bantam max
        feed_rate = min(feed_rate, BANTAM_SPECS["max_feed_rate"])

        # Plunge rate at 30% of feed
        plunge_rate = feed_rate * ALUMINUM_PARAMS["plunge_rate_factor"]

        return {
            "rpm": rpm,
            "feed_rate": round(feed_rate, 1),
            "plunge_rate": round(plunge_rate, 1),
            "chip_load": chip_load
        }

    def create_aluminum_brick_setup(
        self,
        component_name: str,
        setup_number: int,
        setup_type: str,  # "top" or "bottom"
        stock_width_mm: float,
        stock_depth_mm: float,
        stock_height_mm: float,
        z_offset_mm: float = 1.0
    ) -> adsk.cam.Setup:
        """
        Create a CAM setup for aluminum LEGO brick milling.

        Args:
            component_name: Name of component to machine
            setup_number: 1 or 2 (for SETUP1/SETUP2)
            setup_type: "top" (studs up) or "bottom" (hollow side)
            stock_width_mm: Stock X dimension
            stock_depth_mm: Stock Y dimension
            stock_height_mm: Stock Z dimension (brick height)
            z_offset_mm: Extra Z material on stock

        Returns:
            CAM Setup object
        """
        cam = self.cam
        if not cam:
            raise Exception("Could not access CAM workspace")

        # Find the component/body to machine
        design = adsk.fusion.Design.cast(self.app.activeProduct)
        target_comp = None

        # Search for component
        for occ in design.rootComponent.occurrences:
            if occ.component.name == component_name:
                target_comp = occ.component
                break

        # If not found in occurrences, check root component bodies
        if not target_comp:
            for body in design.rootComponent.bRepBodies:
                if body.name == component_name or component_name in body.name:
                    target_comp = design.rootComponent
                    break

        if not target_comp:
            raise Exception(f"Component not found: {component_name}")

        # Create setup
        setups = cam.setups
        setup_input = setups.createInput(adsk.cam.OperationTypes.MillingOperation)

        # Configure setup
        setup = setups.add(setup_input)
        setup.name = f"SETUP{setup_number}_{setup_type.upper()}"

        # Set models to machine
        models = adsk.core.ObjectCollection.create()
        for body in target_comp.bRepBodies:
            models.add(body)
        setup.models = models

        # Configure stock - EXACT dimensions (no offset on X/Y)
        setup.stockMode = adsk.cam.SetupStockMode.FixedBoxStock

        # Stock dimensions - exact X/Y, Z includes offset
        total_height = stock_height_mm + z_offset_mm
        setup.stockFixedX = adsk.core.ValueInput.createByReal(self._cm(stock_width_mm))
        setup.stockFixedY = adsk.core.ValueInput.createByReal(self._cm(stock_depth_mm))
        setup.stockFixedZ = adsk.core.ValueInput.createByReal(self._cm(total_height))

        # WCS setup depends on orientation
        if setup_type == "top":
            # G54 for top setup, origin at front-left-top of stock
            setup.wcsOriginMode = adsk.cam.WCSOriginModes.StockBoxPoint
            # Set point to top-front-left
            setup.wcsOriginBoxPoint = adsk.cam.StockPointCorner.TopFrontLeft
        else:
            # G55 for bottom setup after flip
            setup.wcsOriginMode = adsk.cam.WCSOriginModes.StockBoxPoint
            # After flip, origin is still front-left-top (but part is upside down)
            setup.wcsOriginBoxPoint = adsk.cam.StockPointCorner.TopFrontLeft

        return setup

    def add_facing_operation(
        self,
        setup: adsk.cam.Setup,
        tool_diameter_mm: float = 3.0,
        depth_mm: float = 0.2
    ) -> Optional[adsk.cam.Operation]:
        """
        Add facing operation to remove Z offset and create flat top.

        Args:
            setup: CAM setup
            tool_diameter_mm: Tool diameter
            depth_mm: Total facing depth (Z offset)

        Returns:
            Facing operation or None
        """
        cam = self.cam

        # Calculate feeds/speeds for aluminum
        feeds = self.calculate_aluminum_feeds_speeds(tool_diameter_mm)

        try:
            # Find face template
            template_lib = cam.templateLibrary
            templates = template_lib.templates

            face_template = None
            for template in templates:
                if 'face' in template.name.lower():
                    face_template = template
                    break

            if face_template:
                template_url = face_template.url
            else:
                template_url = 'systempreferences://Strategies/Milling/Face'

            # Create operation
            operations = setup.operations
            op_input = operations.createInput(template_url)

            op = operations.add(op_input)
            op.name = f"Op010_Face_T{ALUMINUM_TOOLS['T1_roughing']['number']}"

            # Configure parameters
            params = op.parameters

            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter_mm))
            self._set_param_safe(params, "spindleSpeed", feeds["rpm"])
            self._set_param_safe(params, "feedrate", feeds["feed_rate"] / 60.0)  # mm/s
            self._set_param_safe(params, "plungeRate", feeds["plunge_rate"] / 60.0)
            self._set_param_safe(params, "surfaceSpeed", 0)  # We're setting RPM directly

            # Stepover for facing (40% of tool diameter)
            stepover = tool_diameter_mm * ALUMINUM_PARAMS["woc_roughing"]
            self._set_param_safe(params, "stepover", self._cm(stepover))

            # Depth of cut per pass
            self._set_param_safe(params, "maximumStepdown", self._cm(ALUMINUM_PARAMS["doc_roughing"]))

            return op

        except Exception as e:
            print(f"Error creating facing operation: {e}")
            return None

    def add_stud_roughing_operation(
        self,
        setup: adsk.cam.Setup,
        stud_positions: List[tuple],
        stud_height_mm: float = 1.7,
        tool_diameter_mm: float = 3.0
    ) -> Optional[adsk.cam.Operation]:
        """
        Add adaptive clearing around studs using 3mm endmill.

        Removes material around stud cylinders, leaving stock for finishing.

        Args:
            setup: CAM setup
            stud_positions: List of (x, y) stud center positions
            stud_height_mm: Stud height
            tool_diameter_mm: Roughing tool diameter

        Returns:
            Operation or None
        """
        cam = self.cam
        feeds = self.calculate_aluminum_feeds_speeds(tool_diameter_mm)

        try:
            # Use adaptive clearing for efficient roughing
            template_lib = cam.templateLibrary
            templates = template_lib.templates

            adaptive_template = None
            for template in templates:
                if 'adaptive' in template.name.lower():
                    adaptive_template = template
                    break

            if adaptive_template:
                template_url = adaptive_template.url
            else:
                template_url = 'systempreferences://Strategies/Milling/Adaptive%20Clearing'

            operations = setup.operations
            op_input = operations.createInput(template_url)

            op = operations.add(op_input)
            op.name = f"Op020_StudRough_T{ALUMINUM_TOOLS['T1_roughing']['number']}"

            params = op.parameters

            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter_mm))
            self._set_param_safe(params, "spindleSpeed", feeds["rpm"])
            self._set_param_safe(params, "feedrate", feeds["feed_rate"] / 60.0)
            self._set_param_safe(params, "plungeRate", feeds["plunge_rate"] / 60.0)

            # Adaptive parameters
            self._set_param_safe(params, "maximumStepdown", self._cm(ALUMINUM_PARAMS["doc_roughing"]))
            optimal_load = tool_diameter_mm * ALUMINUM_PARAMS["woc_roughing"]
            self._set_param_safe(params, "optimalLoad", self._cm(optimal_load))
            self._set_param_safe(params, "stockToLeave", self._cm(ALUMINUM_PARAMS["stock_to_leave"]))

            return op

        except Exception as e:
            print(f"Error creating stud roughing: {e}")
            return None

    def add_stud_finishing_operation(
        self,
        setup: adsk.cam.Setup,
        stud_diameter_mm: float = 4.8,
        tool_diameter_mm: float = 2.0
    ) -> Optional[adsk.cam.Operation]:
        """
        Add finishing operation for stud cylinders using 2mm endmill.

        Args:
            setup: CAM setup
            stud_diameter_mm: LEGO stud diameter (4.8mm)
            tool_diameter_mm: Finishing tool diameter (2mm)

        Returns:
            Operation or None
        """
        cam = self.cam
        feeds = self.calculate_aluminum_feeds_speeds(tool_diameter_mm)

        # Reduce feed rate for finishing
        finish_feed = feeds["feed_rate"] * 0.7

        try:
            # Use contour for circular finishing
            template_lib = cam.templateLibrary
            templates = template_lib.templates

            contour_template = None
            for template in templates:
                if 'contour' in template.name.lower() and '2d' in template.name.lower():
                    contour_template = template
                    break

            if contour_template:
                template_url = contour_template.url
            else:
                template_url = 'systempreferences://Strategies/Milling/2D%20Contour'

            operations = setup.operations
            op_input = operations.createInput(template_url)

            op = operations.add(op_input)
            op.name = f"Op030_StudFinish_T{ALUMINUM_TOOLS['T2_finishing']['number']}"

            params = op.parameters

            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter_mm))
            self._set_param_safe(params, "spindleSpeed", feeds["rpm"])
            self._set_param_safe(params, "feedrate", finish_feed / 60.0)
            self._set_param_safe(params, "plungeRate", feeds["plunge_rate"] / 60.0)

            # No stock to leave - final pass
            self._set_param_safe(params, "stockToLeave", 0)
            self._set_param_safe(params, "maximumStepdown", self._cm(ALUMINUM_PARAMS["doc_finishing"] * 2))

            return op

        except Exception as e:
            print(f"Error creating stud finishing: {e}")
            return None

    def add_hollow_pocketing_operation(
        self,
        setup: adsk.cam.Setup,
        pocket_depth_mm: float,
        wall_thickness_mm: float = 1.5,
        tool_diameter_mm: float = 3.0
    ) -> Optional[adsk.cam.Operation]:
        """
        Add pocket operation for hollow interior (SETUP2 bottom).

        Args:
            setup: CAM setup
            pocket_depth_mm: Hollow depth
            wall_thickness_mm: Wall thickness to maintain
            tool_diameter_mm: Roughing tool diameter

        Returns:
            Operation or None
        """
        cam = self.cam
        feeds = self.calculate_aluminum_feeds_speeds(tool_diameter_mm)

        try:
            # Use adaptive or pocket for hollow
            template_lib = cam.templateLibrary
            templates = template_lib.templates

            pocket_template = None
            for template in templates:
                if 'pocket' in template.name.lower() and '2d' in template.name.lower():
                    pocket_template = template
                    break

            if pocket_template:
                template_url = pocket_template.url
            else:
                template_url = 'systempreferences://Strategies/Milling/2D%20Pocket'

            operations = setup.operations
            op_input = operations.createInput(template_url)

            op = operations.add(op_input)
            op.name = f"Op010_HollowRough_T{ALUMINUM_TOOLS['T1_roughing']['number']}"

            params = op.parameters

            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter_mm))
            self._set_param_safe(params, "spindleSpeed", feeds["rpm"])
            self._set_param_safe(params, "feedrate", feeds["feed_rate"] / 60.0)
            self._set_param_safe(params, "plungeRate", feeds["plunge_rate"] / 60.0)

            self._set_param_safe(params, "maximumStepdown", self._cm(ALUMINUM_PARAMS["doc_roughing"]))
            stepover = tool_diameter_mm * ALUMINUM_PARAMS["woc_roughing"]
            self._set_param_safe(params, "stepover", self._cm(stepover))
            self._set_param_safe(params, "stockToLeave", self._cm(ALUMINUM_PARAMS["stock_to_leave"]))

            return op

        except Exception as e:
            print(f"Error creating hollow pocket: {e}")
            return None

    def add_tube_milling_operation(
        self,
        setup: adsk.cam.Setup,
        tube_positions: List[tuple],
        tube_od_mm: float = 6.51,
        tube_id_mm: float = 4.8,
        tube_height_mm: float = 6.5,
        tool_diameter_mm: float = 2.0
    ) -> Optional[adsk.cam.Operation]:
        """
        Add circular milling for bottom tubes (stud receptacles).

        Args:
            setup: CAM setup
            tube_positions: List of (x, y) tube centers
            tube_od_mm: Outer diameter of tubes
            tube_id_mm: Inner diameter of tubes
            tube_height_mm: Height of tubes
            tool_diameter_mm: Tool diameter (must be < tube_id)

        Returns:
            Operation or None
        """
        cam = self.cam
        feeds = self.calculate_aluminum_feeds_speeds(tool_diameter_mm)

        # Finishing feed rate
        finish_feed = feeds["feed_rate"] * 0.7

        try:
            # Use bore/circular for tube walls
            template_lib = cam.templateLibrary
            templates = template_lib.templates

            bore_template = None
            for template in templates:
                if 'bore' in template.name.lower() or 'circular' in template.name.lower():
                    bore_template = template
                    break

            if bore_template:
                template_url = bore_template.url
            else:
                template_url = 'systempreferences://Strategies/Milling/Bore'

            operations = setup.operations
            op_input = operations.createInput(template_url)

            op = operations.add(op_input)
            op.name = f"Op020_Tubes_T{ALUMINUM_TOOLS['T2_finishing']['number']}"

            params = op.parameters

            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter_mm))
            self._set_param_safe(params, "spindleSpeed", feeds["rpm"])
            self._set_param_safe(params, "feedrate", finish_feed / 60.0)
            self._set_param_safe(params, "plungeRate", feeds["plunge_rate"] / 60.0)

            self._set_param_safe(params, "maximumStepdown", self._cm(ALUMINUM_PARAMS["doc_finishing"]))
            self._set_param_safe(params, "stockToLeave", 0)

            return op

        except Exception as e:
            print(f"Error creating tube milling: {e}")
            return None

    def add_hollow_finishing_operation(
        self,
        setup: adsk.cam.Setup,
        tool_diameter_mm: float = 2.0
    ) -> Optional[adsk.cam.Operation]:
        """
        Add contour finishing for hollow interior walls.

        Args:
            setup: CAM setup
            tool_diameter_mm: Finishing tool diameter

        Returns:
            Operation or None
        """
        cam = self.cam
        feeds = self.calculate_aluminum_feeds_speeds(tool_diameter_mm)
        finish_feed = feeds["feed_rate"] * 0.7

        try:
            template_url = 'systempreferences://Strategies/Milling/2D%20Contour'

            operations = setup.operations
            op_input = operations.createInput(template_url)

            op = operations.add(op_input)
            op.name = f"Op030_HollowFinish_T{ALUMINUM_TOOLS['T2_finishing']['number']}"

            params = op.parameters

            self._set_param_safe(params, "tool_diameter", self._cm(tool_diameter_mm))
            self._set_param_safe(params, "spindleSpeed", feeds["rpm"])
            self._set_param_safe(params, "feedrate", finish_feed / 60.0)
            self._set_param_safe(params, "plungeRate", feeds["plunge_rate"] / 60.0)

            self._set_param_safe(params, "stockToLeave", 0)
            self._set_param_safe(params, "maximumStepdown", self._cm(ALUMINUM_PARAMS["doc_finishing"] * 2))

            return op

        except Exception as e:
            print(f"Error creating hollow finishing: {e}")
            return None

    def create_aluminum_lego_cam(
        self,
        component_name: str,
        studs_x: int = 2,
        studs_y: int = 4,
        height_plates: int = 3,
        z_offset_mm: float = 1.0,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        Create complete CAM workflow for aluminum LEGO brick on Bantam Desktop CNC.

        This creates a two-setup workflow:
        - SETUP1 (G54): Top operations - facing, stud roughing, stud finishing
        - SETUP2 (G55): Bottom operations - hollow pocket, tubes, wall finishing

        Uses optimized 2-tool strategy:
        - T1: 3mm flat endmill (facing, roughing)
        - T2: 2mm flat endmill (finishing, tubes)

        Args:
            component_name: Name of LEGO brick component in Fusion 360
            studs_x: Number of studs in X direction (width)
            studs_y: Number of studs in Y direction (depth)
            height_plates: Brick height in plates (3 = standard brick)
            z_offset_mm: Extra stock on Z for facing
            output_dir: Output directory for G-code files

        Returns:
            Dict with setups, operations, and G-code paths
        """
        # Calculate brick dimensions
        brick_width = studs_x * LEGO_DIMS["pitch"]
        brick_depth = studs_y * LEGO_DIMS["pitch"]
        brick_height = height_plates * LEGO_DIMS["plate_height"]

        # Stock dimensions - exact X/Y, Z includes offset
        stock_width = brick_width
        stock_depth = brick_depth
        stock_height = brick_height

        # Check Bantam work envelope
        if stock_width > BANTAM_SPECS["work_envelope"]["x"]:
            raise ValueError(f"Brick too wide ({stock_width}mm) for Bantam ({BANTAM_SPECS['work_envelope']['x']}mm)")
        if stock_depth > BANTAM_SPECS["work_envelope"]["y"]:
            raise ValueError(f"Brick too deep ({stock_depth}mm) for Bantam ({BANTAM_SPECS['work_envelope']['y']}mm)")
        if stock_height + z_offset_mm > BANTAM_SPECS["work_envelope"]["z"]:
            raise ValueError(f"Brick too tall ({stock_height + z_offset_mm}mm) for Bantam Z travel")

        # Calculate stud positions
        stud_positions = []
        for ix in range(studs_x):
            for iy in range(studs_y):
                x = LEGO_DIMS["pitch"] / 2 + ix * LEGO_DIMS["pitch"]
                y = LEGO_DIMS["pitch"] / 2 + iy * LEGO_DIMS["pitch"]
                stud_positions.append((x, y))

        # Calculate tube positions (between studs for 2+ wide bricks)
        tube_positions = []
        if studs_x >= 2 and studs_y >= 2:
            for ix in range(studs_x - 1):
                for iy in range(studs_y - 1):
                    x = LEGO_DIMS["pitch"] + ix * LEGO_DIMS["pitch"]
                    y = LEGO_DIMS["pitch"] + iy * LEGO_DIMS["pitch"]
                    tube_positions.append((x, y))

        # Hollow depth (brick height minus top plate thickness)
        hollow_depth = brick_height - LEGO_DIMS["plate_height"]
        tube_height = hollow_depth - 0.5  # Slightly shorter than hollow

        result = {
            "brick": {
                "studs_x": studs_x,
                "studs_y": studs_y,
                "height_plates": height_plates,
                "dimensions_mm": {
                    "width": brick_width,
                    "depth": brick_depth,
                    "height": brick_height
                }
            },
            "stock": {
                "width": stock_width,
                "depth": stock_depth,
                "height": stock_height,
                "z_offset": z_offset_mm,
                "total_height": stock_height + z_offset_mm,
                "material": "Aluminum 6061-T6"
            },
            "tools": ALUMINUM_TOOLS,
            "setups": [],
            "gcode_files": {},
            "errors": []
        }

        # Create output directory
        if not output_dir:
            output_dir = os.path.join(
                os.path.expanduser("~"),
                "Documents", "LegoMCP", "exports", "cnc", "aluminum"
            )
        os.makedirs(output_dir, exist_ok=True)

        brick_name = f"LEGO_{studs_x}x{studs_y}"

        try:
            # =====================================================================
            # SETUP 1: TOP OPERATIONS (Studs)
            # =====================================================================
            setup1 = self.create_aluminum_brick_setup(
                component_name=component_name,
                setup_number=1,
                setup_type="top",
                stock_width_mm=stock_width,
                stock_depth_mm=stock_depth,
                stock_height_mm=stock_height,
                z_offset_mm=z_offset_mm
            )

            setup1_ops = []

            # Op 010: Face top (remove Z offset)
            face_op = self.add_facing_operation(
                setup1,
                tool_diameter_mm=3.0,
                depth_mm=z_offset_mm
            )
            if face_op:
                setup1_ops.append("Op010_Face_T1")

            # Op 020: Adaptive rough around studs
            rough_op = self.add_stud_roughing_operation(
                setup1,
                stud_positions=stud_positions,
                stud_height_mm=LEGO_DIMS["stud_height"],
                tool_diameter_mm=3.0
            )
            if rough_op:
                setup1_ops.append("Op020_StudRough_T1")

            # Op 030: Finish stud cylinders
            finish_op = self.add_stud_finishing_operation(
                setup1,
                stud_diameter_mm=LEGO_DIMS["stud_diameter"],
                tool_diameter_mm=2.0
            )
            if finish_op:
                setup1_ops.append("Op030_StudFinish_T2")

            # Generate toolpaths for SETUP1
            self.generate_toolpaths(setup1)

            # Export SETUP1 G-code
            setup1_path = os.path.join(output_dir, f"{brick_name}_SETUP1.nc")
            setup1_result = self.export_gcode(setup1, setup1_path, machine="bantam")

            result["setups"].append({
                "number": 1,
                "name": "SETUP1_TOP",
                "wcs": "G54",
                "type": "top",
                "operations": setup1_ops,
                "gcode_path": setup1_path if setup1_result.get("success") else None,
                "instructions": [
                    "Mount stock in soft jaws or fixture plate",
                    "Top of stock facing up (studs will be machined here)",
                    "Set Z zero on top of stock",
                    "Set X/Y zero at front-left corner",
                    "Use WD-40 mist for coolant"
                ]
            })

            if setup1_result.get("success"):
                result["gcode_files"]["SETUP1"] = setup1_path
            else:
                result["errors"].append(f"SETUP1 export failed: {setup1_result.get('error')}")

            # =====================================================================
            # SETUP 2: BOTTOM OPERATIONS (Hollow & Tubes)
            # =====================================================================
            setup2 = self.create_aluminum_brick_setup(
                component_name=component_name,
                setup_number=2,
                setup_type="bottom",
                stock_width_mm=stock_width,
                stock_depth_mm=stock_depth,
                stock_height_mm=stock_height,
                z_offset_mm=0  # No offset on bottom
            )

            setup2_ops = []

            # Op 010: Pocket hollow interior
            hollow_op = self.add_hollow_pocketing_operation(
                setup2,
                pocket_depth_mm=hollow_depth,
                wall_thickness_mm=LEGO_DIMS["wall_thickness"],
                tool_diameter_mm=3.0
            )
            if hollow_op:
                setup2_ops.append("Op010_HollowRough_T1")

            # Op 020: Mill tubes (if brick is 2x2 or larger)
            if tube_positions:
                tube_op = self.add_tube_milling_operation(
                    setup2,
                    tube_positions=tube_positions,
                    tube_od_mm=LEGO_DIMS["tube_od"],
                    tube_id_mm=LEGO_DIMS["tube_id"],
                    tube_height_mm=tube_height,
                    tool_diameter_mm=2.0
                )
                if tube_op:
                    setup2_ops.append("Op020_Tubes_T2")

            # Op 030: Finish hollow walls
            wall_op = self.add_hollow_finishing_operation(
                setup2,
                tool_diameter_mm=2.0
            )
            if wall_op:
                setup2_ops.append("Op030_HollowFinish_T2")

            # Generate toolpaths for SETUP2
            self.generate_toolpaths(setup2)

            # Export SETUP2 G-code
            setup2_path = os.path.join(output_dir, f"{brick_name}_SETUP2.nc")
            setup2_result = self.export_gcode(setup2, setup2_path, machine="bantam")

            result["setups"].append({
                "number": 2,
                "name": "SETUP2_BOTTOM",
                "wcs": "G55",
                "type": "bottom",
                "operations": setup2_ops,
                "gcode_path": setup2_path if setup2_result.get("success") else None,
                "instructions": [
                    "FLIP PART - bottom now facing up",
                    "Re-mount in soft jaws (protect finished studs)",
                    "Set Z zero on new top surface (bottom of brick)",
                    "Keep X/Y zero at front-left corner",
                    "Use G55 work coordinate system"
                ]
            })

            if setup2_result.get("success"):
                result["gcode_files"]["SETUP2"] = setup2_path
            else:
                result["errors"].append(f"SETUP2 export failed: {setup2_result.get('error')}")

            # Add summary
            result["summary"] = {
                "total_tools": 2,
                "tool_list": [
                    "T1: 3mm Flat Endmill (facing, roughing)",
                    "T2: 2mm Flat Endmill (finishing, tubes)"
                ],
                "total_setups": 2,
                "total_operations": len(setup1_ops) + len(setup2_ops),
                "output_directory": output_dir,
                "machine": "Bantam Desktop CNC",
                "material": "Aluminum 6061-T6"
            }

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def get_aluminum_workflow_status(self) -> Dict[str, Any]:
        """
        Get status of aluminum LEGO milling capabilities.

        Returns:
            Dict with available tools, machine specs, and feature support
        """
        return {
            "available": True,
            "machine": BANTAM_SPECS,
            "lego_dimensions": LEGO_DIMS,
            "aluminum_params": ALUMINUM_PARAMS,
            "tools": ALUMINUM_TOOLS,
            "workflow": {
                "type": "two_setup",
                "setup1": {
                    "name": "TOP",
                    "wcs": "G54",
                    "operations": ["facing", "stud_roughing", "stud_finishing"]
                },
                "setup2": {
                    "name": "BOTTOM",
                    "wcs": "G55",
                    "operations": ["hollow_pocketing", "tube_milling", "wall_finishing"]
                }
            },
            "max_brick_size": {
                "width_studs": int(BANTAM_SPECS["work_envelope"]["x"] / LEGO_DIMS["pitch"]),
                "depth_studs": int(BANTAM_SPECS["work_envelope"]["y"] / LEGO_DIMS["pitch"]),
                "height_plates": int((BANTAM_SPECS["work_envelope"]["z"] - 5) / LEGO_DIMS["plate_height"])
            }
        }
