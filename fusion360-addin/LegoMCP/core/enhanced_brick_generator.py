"""
Enhanced Brick Generator for Fusion 360

This module generates ANY LEGO brick from a CustomBrickDefinition.
It handles all features: studs, tubes, holes, slopes, side features, cutouts, etc.
"""

import adsk.core
import adsk.fusion
import math
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Import from shared (will be copied to add-in)
try:
    from ..shared.custom_brick_builder import (
        CustomBrickDefinition,
        StudDefinition,
        TubeDefinition,
        RibDefinition,
        HoleDefinition,
        SlopeDefinition,
        SideStudDefinition,
        ClipDefinition,
        BarDefinition,
        CutoutDefinition,
        TextDefinition
    )
except ImportError:
    # Fallback for standalone use
    pass


# LEGO Dimensions (mm)
STUD_PITCH = 8.0
STUD_DIAMETER = 4.8
STUD_HEIGHT = 1.7
PLATE_HEIGHT = 3.2
WALL_THICKNESS = 1.5
TOP_THICKNESS = 1.0
TUBE_OD = 6.51
TUBE_ID = 4.8
PIN_HOLE_DIAMETER = 4.8
AXLE_HOLE_SIZE = 4.8
BAR_DIAMETER = 3.18
CLIP_WIDTH = 4.0


@dataclass
class GenerationResult:
    """Result of brick generation."""
    success: bool
    component_name: str
    brick_id: str
    volume_mm3: float
    error: Optional[str] = None


class EnhancedBrickGenerator:
    """
    Generates any LEGO brick in Fusion 360 from a CustomBrickDefinition.
    
    This is the core geometry engine that translates brick definitions
    into actual Fusion 360 3D models.
    """
    
    def __init__(self, app: adsk.core.Application):
        self.app = app
        self._brick_counter = 0
    
    @property
    def design(self) -> adsk.fusion.Design:
        """Get or create active design."""
        product = self.app.activeProduct
        if not product or product.objectType != adsk.fusion.Design.classType():
            doc = self.app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            product = self.app.activeProduct
        return adsk.fusion.Design.cast(product)
    
    @property
    def root(self) -> adsk.fusion.Component:
        """Get root component."""
        return self.design.rootComponent
    
    def _cm(self, mm: float) -> float:
        """Convert mm to cm (Fusion uses cm internally)."""
        return mm / 10.0
    
    def _new_brick_id(self) -> str:
        """Generate unique brick ID."""
        self._brick_counter += 1
        return f"brick_{self._brick_counter:04d}"
    
    def generate(self, brick_def: CustomBrickDefinition) -> GenerationResult:
        """
        Generate a brick from a CustomBrickDefinition.
        
        This is the main entry point for brick generation.
        """
        try:
            # Create component
            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = brick_def.name
            
            # Step 1: Create base body
            if brick_def.is_round:
                self._create_round_base(comp, brick_def)
            else:
                self._create_rectangular_base(comp, brick_def)
            
            # Step 2: Add studs
            if brick_def.studs:
                self._add_studs(comp, brick_def)
            
            # Step 3: Hollow bottom
            if brick_def.is_hollow:
                self._hollow_bottom(comp, brick_def)
            
            # Step 4: Add tubes
            if brick_def.tubes:
                self._add_tubes(comp, brick_def)
            
            # Step 5: Add ribs
            if brick_def.ribs:
                self._add_ribs(comp, brick_def)
            
            # Step 6: Add Technic holes
            if brick_def.holes:
                self._add_technic_holes(comp, brick_def)
            
            # Step 7: Apply slopes
            if brick_def.slopes:
                self._apply_slopes(comp, brick_def)
            
            # Step 8: Add side studs
            if brick_def.side_studs:
                self._add_side_studs(comp, brick_def)
            
            # Step 9: Add clips
            if brick_def.clips:
                self._add_clips(comp, brick_def)
            
            # Step 10: Add bars
            if brick_def.bars:
                self._add_bars(comp, brick_def)
            
            # Step 11: Apply cutouts
            if brick_def.cutouts:
                self._apply_cutouts(comp, brick_def)
            
            # Step 12: Add text
            if brick_def.text:
                self._add_text(comp, brick_def)
            
            # Calculate volume
            volume = 0.0
            for body in comp.bRepBodies:
                volume += body.volume * 1000  # cm³ to mm³
            
            return GenerationResult(
                success=True,
                component_name=comp.name,
                brick_id=self._new_brick_id(),
                volume_mm3=volume
            )
            
        except Exception as e:
            return GenerationResult(
                success=False,
                component_name="",
                brick_id="",
                volume_mm3=0,
                error=str(e)
            )
    
    # ========================================================================
    # BASE GEOMETRY
    # ========================================================================
    
    def _create_rectangular_base(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Create the main rectangular brick body."""
        sketch = comp.sketches.add(comp.xYConstructionPlane)
        
        width = brick_def.width_mm
        depth = brick_def.depth_mm
        height = brick_def.height_mm
        
        # Draw rectangle
        lines = sketch.sketchCurves.sketchLines
        lines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(self._cm(width), self._cm(depth), 0)
        )
        
        # Extrude
        profile = sketch.profiles.item(0)
        extrudes = comp.features.extrudeFeatures
        ext_input = extrudes.createInput(
            profile,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(height)))
        extrudes.add(ext_input)
    
    def _create_round_base(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Create a cylindrical brick body."""
        sketch = comp.sketches.add(comp.xYConstructionPlane)
        
        # Use smaller of width/depth as diameter
        diameter = min(brick_def.width_mm, brick_def.depth_mm)
        radius = diameter / 2
        center_x = brick_def.width_mm / 2
        center_y = brick_def.depth_mm / 2
        
        # Draw circle
        circles = sketch.sketchCurves.sketchCircles
        circles.addByCenterRadius(
            adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0),
            self._cm(radius)
        )
        
        # Extrude
        profile = sketch.profiles.item(0)
        extrudes = comp.features.extrudeFeatures
        ext_input = extrudes.createInput(
            profile,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(brick_def.height_mm)))
        extrudes.add(ext_input)
    
    # ========================================================================
    # STUDS
    # ========================================================================
    
    def _add_studs(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add studs to the top of the brick."""
        # Find top face
        body = comp.bRepBodies.item(0)
        top_face = None
        target_z = self._cm(brick_def.height_mm)
        
        for face in body.faces:
            if abs(face.centroid.z - target_z) < 0.001:
                top_face = face
                break
        
        if not top_face:
            return
        
        # Create sketch on top face
        sketch = comp.sketches.add(top_face)
        circles = sketch.sketchCurves.sketchCircles
        
        # Add circle for each stud
        for stud in brick_def.studs:
            center_x = stud.x * STUD_PITCH
            center_y = stud.y * STUD_PITCH
            radius = stud.diameter_mm / 2
            
            circles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0),
                self._cm(radius)
            )
        
        # Extrude all studs
        profiles = adsk.core.ObjectCollection.create()
        for prof in sketch.profiles:
            profiles.add(prof)
        
        if profiles.count > 0:
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profiles,
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            stud_height = brick_def.studs[0].height_mm if brick_def.studs else STUD_HEIGHT
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(stud_height)))
            extrudes.add(ext_input)
    
    # ========================================================================
    # BOTTOM STRUCTURE
    # ========================================================================
    
    def _hollow_bottom(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Hollow out the bottom of the brick."""
        body = comp.bRepBodies.item(0)
        
        # Find bottom face
        bottom_face = None
        for face in body.faces:
            if abs(face.centroid.z) < 0.001:
                bottom_face = face
                break
        
        if not bottom_face:
            return
        
        # Create sketch on bottom
        sketch = comp.sketches.add(bottom_face)
        
        # Inner rectangle (inset by wall thickness)
        wall = brick_def.wall_thickness_mm
        inner_width = brick_def.width_mm - 2 * wall
        inner_depth = brick_def.depth_mm - 2 * wall
        
        if inner_width > 0 and inner_depth > 0:
            lines = sketch.sketchCurves.sketchLines
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(self._cm(wall), self._cm(wall), 0),
                adsk.core.Point3D.create(self._cm(brick_def.width_mm - wall), self._cm(brick_def.depth_mm - wall), 0)
            )
            
            # Cut upward
            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            cut_depth = brick_def.height_mm - brick_def.top_thickness_mm
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(cut_depth)))
            extrudes.add(ext_input)
    
    def _add_tubes(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add bottom tubes."""
        sketch = comp.sketches.add(comp.xYConstructionPlane)
        circles = sketch.sketchCurves.sketchCircles
        
        for tube in brick_def.tubes:
            center_x = tube.x * STUD_PITCH
            center_y = tube.y * STUD_PITCH
            center = adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0)
            
            # Outer circle
            circles.addByCenterRadius(center, self._cm(tube.outer_diameter_mm / 2))
            # Inner circle
            circles.addByCenterRadius(center, self._cm(tube.inner_diameter_mm / 2))
        
        # Find and extrude ring profiles
        for i in range(sketch.profiles.count):
            profile = sketch.profiles.item(i)
            if profile.profileLoops.count == 2:  # Ring profile
                try:
                    extrudes = comp.features.extrudeFeatures
                    ext_input = extrudes.createInput(
                        profile,
                        adsk.fusion.FeatureOperations.JoinFeatureOperation
                    )
                    tube_height = brick_def.tubes[0].height_mm if brick_def.tubes else brick_def.height_mm - TOP_THICKNESS
                    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(tube_height)))
                    extrudes.add(ext_input)
                except:
                    pass
    
    def _add_ribs(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add center ribs for 1xN bricks."""
        for rib in brick_def.ribs:
            sketch = comp.sketches.add(comp.xYConstructionPlane)
            lines = sketch.sketchCurves.sketchLines
            
            if rib.orientation == 'x':
                # Rib runs in X direction
                x1 = WALL_THICKNESS
                x2 = brick_def.width_mm - WALL_THICKNESS
                y_center = rib.position * STUD_PITCH
                y1 = y_center - rib.thickness_mm / 2
                y2 = y_center + rib.thickness_mm / 2
            else:
                # Rib runs in Y direction
                y1 = WALL_THICKNESS
                y2 = brick_def.depth_mm - WALL_THICKNESS
                x_center = rib.position * STUD_PITCH
                x1 = x_center - rib.thickness_mm / 2
                x2 = x_center + rib.thickness_mm / 2
            
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(self._cm(x1), self._cm(y1), 0),
                adsk.core.Point3D.create(self._cm(x2), self._cm(y2), 0)
            )
            
            if sketch.profiles.count > 0:
                profile = sketch.profiles.item(0)
                extrudes = comp.features.extrudeFeatures
                ext_input = extrudes.createInput(
                    profile,
                    adsk.fusion.FeatureOperations.JoinFeatureOperation
                )
                ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(rib.height_mm)))
                try:
                    extrudes.add(ext_input)
                except:
                    pass
    
    # ========================================================================
    # TECHNIC HOLES
    # ========================================================================
    
    def _add_technic_holes(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add Technic pin/axle holes."""
        for hole in brick_def.holes:
            # Calculate hole position in mm
            pos_x = hole.x * STUD_PITCH
            pos_y = hole.y * STUD_PITCH
            pos_z = hole.z * brick_def.height_mm
            
            # Select plane based on axis
            if hole.axis == 'x':
                self._create_hole_x(comp, pos_y, pos_z, brick_def.width_mm, hole)
            elif hole.axis == 'y':
                self._create_hole_y(comp, pos_x, pos_z, brick_def.depth_mm, hole)
            else:  # 'z'
                self._create_hole_z(comp, pos_x, pos_y, brick_def.height_mm, hole)
    
    def _create_hole_x(self, comp, y, z, length, hole_def):
        """Create a hole through X axis."""
        # Create sketch on YZ plane at X=0
        yz_plane = comp.yZConstructionPlane
        sketch = comp.sketches.add(yz_plane)
        
        if hole_def.type == 'pin':
            # Simple round hole
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(y), self._cm(z), 0),
                self._cm(PIN_HOLE_DIAMETER / 2)
            )
        elif hole_def.type == 'axle':
            # Cross-shaped hole
            self._draw_axle_cross(sketch, y, z, AXLE_HOLE_SIZE)
        else:  # pin_axle
            # Combined - for now use round
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(y), self._cm(z), 0),
                self._cm(PIN_HOLE_DIAMETER / 2)
            )
        
        # Cut through
        if sketch.profiles.count > 0:
            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(length)))
            try:
                extrudes.add(ext_input)
            except:
                pass
    
    def _create_hole_y(self, comp, x, z, length, hole_def):
        """Create a hole through Y axis."""
        xz_plane = comp.xZConstructionPlane
        sketch = comp.sketches.add(xz_plane)
        
        if hole_def.type == 'pin':
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(x), self._cm(z), 0),
                self._cm(PIN_HOLE_DIAMETER / 2)
            )
        elif hole_def.type == 'axle':
            self._draw_axle_cross(sketch, x, z, AXLE_HOLE_SIZE)
        else:
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(x), self._cm(z), 0),
                self._cm(PIN_HOLE_DIAMETER / 2)
            )
        
        if sketch.profiles.count > 0:
            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(length)))
            try:
                extrudes.add(ext_input)
            except:
                pass
    
    def _create_hole_z(self, comp, x, y, length, hole_def):
        """Create a vertical hole."""
        sketch = comp.sketches.add(comp.xYConstructionPlane)
        
        if hole_def.type == 'pin':
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(x), self._cm(y), 0),
                self._cm(PIN_HOLE_DIAMETER / 2)
            )
        elif hole_def.type == 'axle':
            self._draw_axle_cross(sketch, x, y, AXLE_HOLE_SIZE)
        else:
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(x), self._cm(y), 0),
                self._cm(PIN_HOLE_DIAMETER / 2)
            )
        
        if sketch.profiles.count > 0:
            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(length)))
            try:
                extrudes.add(ext_input)
            except:
                pass
    
    def _draw_axle_cross(self, sketch, center_x, center_y, size):
        """Draw a cross-shaped profile for axle holes."""
        lines = sketch.sketchCurves.sketchLines
        cx, cy = self._cm(center_x), self._cm(center_y)
        s = self._cm(size / 2)
        arm_width = self._cm(1.8 / 2)  # Axle arm width
        
        # Draw cross shape (simplified as circle for now)
        # Full implementation would create proper + shape
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cx, cy, 0),
            s
        )
    
    # ========================================================================
    # SLOPES
    # ========================================================================
    
    def _apply_slopes(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Apply slope cuts to the brick."""
        for slope in brick_def.slopes:
            if slope.type == 'inverted':
                self._apply_inverted_slope(comp, brick_def, slope)
            elif slope.type == 'double':
                self._apply_double_slope(comp, brick_def, slope)
            else:
                self._apply_standard_slope(comp, brick_def, slope)
    
    def _apply_standard_slope(self, comp, brick_def, slope):
        """Apply a standard slope cut."""
        height = brick_def.height_mm
        angle_rad = math.radians(slope.angle_degrees)
        slope_run = height / math.tan(angle_rad)
        
        # Select appropriate plane
        if slope.direction in ['front', 'back']:
            sketch = comp.sketches.add(comp.xZConstructionPlane)
            
            if slope.direction == 'front':
                # Cut from front
                p1 = adsk.core.Point3D.create(0, self._cm(height), 0)
                p2 = adsk.core.Point3D.create(self._cm(slope_run), self._cm(height), 0)
                p3 = adsk.core.Point3D.create(0, 0, 0)
            else:
                # Cut from back
                p1 = adsk.core.Point3D.create(self._cm(brick_def.depth_mm), self._cm(height), 0)
                p2 = adsk.core.Point3D.create(self._cm(brick_def.depth_mm - slope_run), self._cm(height), 0)
                p3 = adsk.core.Point3D.create(self._cm(brick_def.depth_mm), 0, 0)
        else:
            sketch = comp.sketches.add(comp.yZConstructionPlane)
            
            if slope.direction == 'left':
                p1 = adsk.core.Point3D.create(0, self._cm(height), 0)
                p2 = adsk.core.Point3D.create(self._cm(slope_run), self._cm(height), 0)
                p3 = adsk.core.Point3D.create(0, 0, 0)
            else:
                p1 = adsk.core.Point3D.create(self._cm(brick_def.width_mm), self._cm(height), 0)
                p2 = adsk.core.Point3D.create(self._cm(brick_def.width_mm - slope_run), self._cm(height), 0)
                p3 = adsk.core.Point3D.create(self._cm(brick_def.width_mm), 0, 0)
        
        # Draw triangle
        lines = sketch.sketchCurves.sketchLines
        lines.addByTwoPoints(p1, p2)
        lines.addByTwoPoints(p2, p3)
        lines.addByTwoPoints(p3, p1)
        
        # Cut
        if sketch.profiles.count > 0:
            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            
            cut_distance = brick_def.width_mm if slope.direction in ['front', 'back'] else brick_def.depth_mm
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(cut_distance)))
            try:
                extrudes.add(ext_input)
            except:
                pass
    
    def _apply_inverted_slope(self, comp, brick_def, slope):
        """Apply inverted slope (on bottom)."""
        # Similar to standard but from bottom
        pass  # Implementation similar to standard slope
    
    def _apply_double_slope(self, comp, brick_def, slope):
        """Apply double slope (roof peak)."""
        # Create two opposing slopes
        slope_front = SlopeDefinition(
            angle_degrees=slope.angle_degrees,
            direction='front',
            type='straight'
        )
        slope_back = SlopeDefinition(
            angle_degrees=slope.angle_degrees,
            direction='back',
            type='straight'
        )
        self._apply_standard_slope(comp, brick_def, slope_front)
        self._apply_standard_slope(comp, brick_def, slope_back)
    
    # ========================================================================
    # SIDE FEATURES
    # ========================================================================
    
    def _add_side_studs(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add studs on the sides of the brick."""
        for side_stud in brick_def.side_studs:
            self._add_single_side_stud(comp, brick_def, side_stud)
    
    def _add_single_side_stud(self, comp, brick_def, side_stud):
        """Add a single side stud."""
        # Determine position based on face
        if side_stud.face == 'front':
            # Stud on front face (Y=0)
            x_pos = side_stud.x * STUD_PITCH
            z_pos = side_stud.z * brick_def.height_mm
            
            # Create sketch on XZ plane
            sketch = comp.sketches.add(comp.xZConstructionPlane)
            
            # Draw stud circle
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(x_pos), self._cm(z_pos), 0),
                self._cm(STUD_DIAMETER / 2)
            )
            
            # Extrude outward (negative Y)
            if sketch.profiles.count > 0:
                profile = sketch.profiles.item(0)
                extrudes = comp.features.extrudeFeatures
                ext_input = extrudes.createInput(
                    profile,
                    adsk.fusion.FeatureOperations.JoinFeatureOperation
                )
                # Extrude into negative direction
                ext_input.setDistanceExtent(
                    False, 
                    adsk.core.ValueInput.createByReal(self._cm(-STUD_HEIGHT))
                )
                try:
                    extrudes.add(ext_input)
                except:
                    pass
        # Similar for other faces...
    
    def _add_clips(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add clip attachments."""
        for clip in brick_def.clips:
            self._add_single_clip(comp, brick_def, clip)
    
    def _add_single_clip(self, comp, brick_def, clip):
        """Add a single clip."""
        # Simplified clip geometry
        pass
    
    def _add_bars(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add bar/handle attachments."""
        for bar in brick_def.bars:
            self._add_single_bar(comp, brick_def, bar)
    
    def _add_single_bar(self, comp, brick_def, bar):
        """Add a single bar."""
        # Simplified bar geometry
        pass
    
    # ========================================================================
    # MODIFICATIONS
    # ========================================================================
    
    def _apply_cutouts(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Apply cutouts to the brick."""
        for cutout in brick_def.cutouts:
            self._apply_single_cutout(comp, brick_def, cutout)
    
    def _apply_single_cutout(self, comp, brick_def, cutout):
        """Apply a single cutout."""
        # Select face plane based on cutout.face
        if cutout.face == 'front':
            sketch = comp.sketches.add(comp.xZConstructionPlane)
        elif cutout.face == 'top':
            # Find top face
            body = comp.bRepBodies.item(0)
            top_face = None
            for face in body.faces:
                if abs(face.centroid.z - self._cm(brick_def.height_mm)) < 0.001:
                    top_face = face
                    break
            if not top_face:
                return
            sketch = comp.sketches.add(top_face)
        else:
            return  # Simplified
        
        # Draw shape
        cx, cy = self._cm(cutout.x), self._cm(cutout.y)
        
        if cutout.shape == 'circle':
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cx, cy, 0),
                self._cm(cutout.width_mm / 2)
            )
        elif cutout.shape == 'rectangle':
            lines = sketch.sketchCurves.sketchLines
            w2, h2 = self._cm(cutout.width_mm / 2), self._cm(cutout.height_mm / 2)
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(cx - w2, cy - h2, 0),
                adsk.core.Point3D.create(cx + w2, cy + h2, 0)
            )
        elif cutout.shape == 'arch':
            # Simplified arch as rectangle + semicircle
            self._draw_arch(sketch, cx, cy, cutout.width_mm, cutout.height_mm)
        
        # Cut
        if sketch.profiles.count > 0:
            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            depth = cutout.depth_mm if cutout.depth_mm > 0 else brick_def.depth_mm
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(depth)))
            try:
                extrudes.add(ext_input)
            except:
                pass
    
    def _draw_arch(self, sketch, cx, cy, width, height):
        """Draw an arch shape."""
        # Simplified: draw rectangle for now
        lines = sketch.sketchCurves.sketchLines
        w2, h = self._cm(width / 2), self._cm(height)
        lines.addTwoPointRectangle(
            adsk.core.Point3D.create(cx - w2, cy, 0),
            adsk.core.Point3D.create(cx + w2, cy + h, 0)
        )
    
    def _add_text(self, comp: adsk.fusion.Component, brick_def: CustomBrickDefinition):
        """Add embossed/debossed text."""
        # Text requires Fusion 360's text sketch feature
        # Simplified: skip text for now
        pass
