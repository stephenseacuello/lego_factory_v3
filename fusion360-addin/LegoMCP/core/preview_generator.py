"""
Preview Image Generation for LEGO Bricks

Generates preview images of LEGO bricks using Fusion 360's viewport rendering.
Supports multiple view angles, styles, and export formats.
"""

import adsk.core
import adsk.fusion
import math
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


# ============================================================================
# ENUMS AND SETTINGS
# ============================================================================

class ViewAngle(Enum):
    """Predefined camera view angles."""
    FRONT = "front"
    BACK = "back"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    ISOMETRIC = "isometric"
    ISOMETRIC_TOP = "isometric_top"
    ISOMETRIC_BOTTOM = "isometric_bottom"
    FRONT_TOP = "front_top"
    CUSTOM = "custom"


class RenderStyle(Enum):
    """Render styles."""
    SHADED = "shaded"
    SHADED_EDGES = "shaded_edges"
    WIREFRAME = "wireframe"
    HIDDEN_EDGE = "hidden_edge"
    REALISTIC = "realistic"


class ImageFormat(Enum):
    """Output image formats."""
    PNG = "png"
    JPEG = "jpeg"
    BMP = "bmp"
    TIFF = "tiff"


@dataclass
class CameraSettings:
    """Camera position and orientation."""
    eye_x: float = 50.0
    eye_y: float = 50.0
    eye_z: float = 50.0
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    up_x: float = 0.0
    up_y: float = 0.0
    up_z: float = 1.0
    is_perspective: bool = True
    field_of_view: float = 45.0  # degrees


@dataclass
class ImageSettings:
    """Image export settings."""
    width: int = 800
    height: int = 600
    format: ImageFormat = ImageFormat.PNG
    background_color: Tuple[int, int, int] = (255, 255, 255)  # White
    transparent_background: bool = False
    anti_aliasing: bool = True


# ============================================================================
# PRESET CAMERA POSITIONS
# ============================================================================

def get_preset_camera(
    view: ViewAngle,
    brick_size: Tuple[float, float, float]
) -> CameraSettings:
    """
    Get camera settings for a preset view.
    
    Args:
        view: The view angle preset
        brick_size: (width, depth, height) of brick in mm
        
    Returns:
        CameraSettings for the view
    """
    w, d, h = brick_size
    
    # Calculate appropriate distance based on brick size
    max_dim = max(w, d, h)
    distance = max_dim * 3
    
    # Center point
    cx, cy, cz = w/2, d/2, h/2
    
    if view == ViewAngle.FRONT:
        return CameraSettings(
            eye_x=cx, eye_y=-distance, eye_z=cz,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.BACK:
        return CameraSettings(
            eye_x=cx, eye_y=d + distance, eye_z=cz,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.TOP:
        return CameraSettings(
            eye_x=cx, eye_y=cy, eye_z=h + distance,
            target_x=cx, target_y=cy, target_z=cz,
            up_x=0, up_y=1, up_z=0
        )
    elif view == ViewAngle.BOTTOM:
        return CameraSettings(
            eye_x=cx, eye_y=cy, eye_z=-distance,
            target_x=cx, target_y=cy, target_z=cz,
            up_x=0, up_y=-1, up_z=0
        )
    elif view == ViewAngle.LEFT:
        return CameraSettings(
            eye_x=-distance, eye_y=cy, eye_z=cz,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.RIGHT:
        return CameraSettings(
            eye_x=w + distance, eye_y=cy, eye_z=cz,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.ISOMETRIC:
        # Classic isometric: 45° around Z, 35.264° from XY plane
        angle_h = math.radians(45)
        angle_v = math.radians(35.264)
        
        eye_x = cx + distance * math.cos(angle_v) * math.cos(angle_h)
        eye_y = cy + distance * math.cos(angle_v) * math.sin(angle_h)
        eye_z = cz + distance * math.sin(angle_v)
        
        return CameraSettings(
            eye_x=eye_x, eye_y=eye_y, eye_z=eye_z,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.ISOMETRIC_TOP:
        # Top-down isometric
        angle_h = math.radians(45)
        angle_v = math.radians(60)
        
        eye_x = cx + distance * math.cos(angle_v) * math.cos(angle_h)
        eye_y = cy + distance * math.cos(angle_v) * math.sin(angle_h)
        eye_z = cz + distance * math.sin(angle_v)
        
        return CameraSettings(
            eye_x=eye_x, eye_y=eye_y, eye_z=eye_z,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.ISOMETRIC_BOTTOM:
        # Bottom-up isometric (shows underside)
        angle_h = math.radians(-135)
        angle_v = math.radians(-35)
        
        eye_x = cx + distance * math.cos(angle_v) * math.cos(angle_h)
        eye_y = cy + distance * math.cos(angle_v) * math.sin(angle_h)
        eye_z = cz + distance * math.sin(angle_v)
        
        return CameraSettings(
            eye_x=eye_x, eye_y=eye_y, eye_z=eye_z,
            target_x=cx, target_y=cy, target_z=cz
        )
    elif view == ViewAngle.FRONT_TOP:
        # 45° from front and top
        return CameraSettings(
            eye_x=cx, eye_y=-distance * 0.7, eye_z=cz + distance * 0.7,
            target_x=cx, target_y=cy, target_z=cz
        )
    else:
        # Default to isometric
        return get_preset_camera(ViewAngle.ISOMETRIC, brick_size)


# ============================================================================
# PREVIEW GENERATOR CLASS
# ============================================================================

class PreviewGenerator:
    """
    Generates preview images of LEGO bricks in Fusion 360.
    """
    
    def __init__(self, app: adsk.core.Application):
        self.app = app
        self.ui = app.userInterface
    
    @property
    def design(self) -> adsk.fusion.Design:
        """Get active design."""
        return adsk.fusion.Design.cast(self.app.activeProduct)
    
    @property
    def viewport(self) -> adsk.core.Viewport:
        """Get active viewport."""
        return self.app.activeViewport
    
    def _cm(self, mm: float) -> float:
        """Convert mm to cm."""
        return mm / 10.0
    
    def set_camera(self, settings: CameraSettings):
        """
        Set the viewport camera position.
        
        Args:
            settings: Camera settings to apply
        """
        camera = self.viewport.camera
        
        # Set eye (camera position)
        camera.eye = adsk.core.Point3D.create(
            self._cm(settings.eye_x),
            self._cm(settings.eye_y),
            self._cm(settings.eye_z)
        )
        
        # Set target (look at point)
        camera.target = adsk.core.Point3D.create(
            self._cm(settings.target_x),
            self._cm(settings.target_y),
            self._cm(settings.target_z)
        )
        
        # Set up vector
        camera.upVector = adsk.core.Vector3D.create(
            settings.up_x,
            settings.up_y,
            settings.up_z
        )
        
        # Perspective vs orthographic
        if settings.is_perspective:
            camera.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
            camera.perspectiveAngle = settings.field_of_view
        else:
            camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType
        
        # Apply camera
        camera.isSmoothTransition = False
        self.viewport.camera = camera
        self.viewport.refresh()
    
    def set_render_style(self, style: RenderStyle):
        """
        Set the viewport render style.
        
        Args:
            style: Render style to apply
        """
        visual_style = self.viewport.visualStyle
        
        if style == RenderStyle.SHADED:
            # Shaded without edges
            visual_style = adsk.core.VisualStyles.ShadedVisualStyle
        elif style == RenderStyle.SHADED_EDGES:
            visual_style = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
        elif style == RenderStyle.WIREFRAME:
            visual_style = adsk.core.VisualStyles.WireframeVisualStyle
        elif style == RenderStyle.HIDDEN_EDGE:
            visual_style = adsk.core.VisualStyles.ShadedWithHiddenEdgesVisualStyle
        elif style == RenderStyle.REALISTIC:
            # Use Fusion's realistic rendering
            visual_style = adsk.core.VisualStyles.RealisticVisualStyle
        
        self.viewport.visualStyle = visual_style
        self.viewport.refresh()
    
    def fit_to_view(self):
        """Fit the model to the current viewport."""
        self.viewport.fit()
    
    def capture_image(
        self,
        output_path: str,
        settings: ImageSettings = None
    ) -> bool:
        """
        Capture the current viewport to an image file.
        
        Args:
            output_path: Path to save the image
            settings: Image settings (size, format, etc.)
            
        Returns:
            True if successful
        """
        if settings is None:
            settings = ImageSettings()
        
        try:
            # Use save image with specified size
            success = self.viewport.saveAsImageFile(
                output_path,
                settings.width,
                settings.height
            )
            return success
        except Exception as e:
            print(f"Error capturing image: {e}")
            return False
    
    def generate_preview(
        self,
        component_name: str,
        output_path: str,
        view: ViewAngle = ViewAngle.ISOMETRIC,
        style: RenderStyle = RenderStyle.SHADED_EDGES,
        image_settings: ImageSettings = None,
        brick_size: Tuple[float, float, float] = None
    ) -> Dict[str, Any]:
        """
        Generate a preview image of a component.
        
        Args:
            component_name: Name of the component to capture
            output_path: Path to save the image
            view: Camera view angle
            style: Render style
            image_settings: Image export settings
            brick_size: (width, depth, height) in mm for camera positioning
            
        Returns:
            Result dictionary with status and info
        """
        if image_settings is None:
            image_settings = ImageSettings()
        
        if brick_size is None:
            # Default to 2x4 brick size
            brick_size = (16.0, 32.0, 9.6)
        
        try:
            # Find the component
            component = None
            for occ in self.design.rootComponent.occurrences:
                if occ.component.name == component_name:
                    component = occ.component
                    break
            
            if not component:
                return {
                    "success": False,
                    "error": f"Component not found: {component_name}"
                }
            
            # Calculate bounding box for camera
            if component.bRepBodies.count > 0:
                body = component.bRepBodies.item(0)
                bbox = body.boundingBox
                
                # Get actual dimensions
                brick_size = (
                    (bbox.maxPoint.x - bbox.minPoint.x) * 10,  # cm to mm
                    (bbox.maxPoint.y - bbox.minPoint.y) * 10,
                    (bbox.maxPoint.z - bbox.minPoint.z) * 10
                )
            
            # Set up camera
            camera_settings = get_preset_camera(view, brick_size)
            self.set_camera(camera_settings)
            
            # Set render style
            self.set_render_style(style)
            
            # Fit to view
            self.fit_to_view()
            
            # Capture image
            success = self.capture_image(output_path, image_settings)
            
            if success:
                return {
                    "success": True,
                    "output_path": output_path,
                    "view": view.value,
                    "style": style.value,
                    "size": [image_settings.width, image_settings.height],
                    "format": image_settings.format.value
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to capture image"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_all_views(
        self,
        component_name: str,
        output_dir: str,
        views: List[ViewAngle] = None,
        style: RenderStyle = RenderStyle.SHADED_EDGES,
        image_settings: ImageSettings = None
    ) -> Dict[str, Any]:
        """
        Generate preview images from multiple view angles.
        
        Args:
            component_name: Name of the component
            output_dir: Directory to save images
            views: List of view angles (default: front, top, isometric)
            style: Render style
            image_settings: Image settings
            
        Returns:
            Results for all views
        """
        if views is None:
            views = [
                ViewAngle.FRONT,
                ViewAngle.TOP,
                ViewAngle.ISOMETRIC,
                ViewAngle.ISOMETRIC_BOTTOM
            ]
        
        if image_settings is None:
            image_settings = ImageSettings()
        
        results = []
        
        for view in views:
            filename = f"{component_name}_{view.value}.{image_settings.format.value}"
            output_path = f"{output_dir}/{filename}"
            
            result = self.generate_preview(
                component_name,
                output_path,
                view,
                style,
                image_settings
            )
            
            results.append({
                "view": view.value,
                "path": output_path,
                "success": result.get("success", False),
                "error": result.get("error")
            })
        
        successful = sum(1 for r in results if r["success"])
        
        return {
            "component": component_name,
            "total_views": len(views),
            "successful": successful,
            "failed": len(views) - successful,
            "results": results
        }
    
    def generate_thumbnail(
        self,
        component_name: str,
        output_path: str,
        size: int = 256
    ) -> Dict[str, Any]:
        """
        Generate a small thumbnail image.
        
        Args:
            component_name: Name of the component
            output_path: Path to save thumbnail
            size: Thumbnail size (square)
            
        Returns:
            Result dictionary
        """
        settings = ImageSettings(
            width=size,
            height=size,
            format=ImageFormat.PNG
        )
        
        return self.generate_preview(
            component_name,
            output_path,
            ViewAngle.ISOMETRIC,
            RenderStyle.SHADED_EDGES,
            settings
        )


# ============================================================================
# STANDALONE FUNCTIONS FOR MCP
# ============================================================================

def generate_brick_preview(
    app: adsk.core.Application,
    component_name: str,
    output_path: str,
    view: str = "isometric",
    style: str = "shaded_edges",
    width: int = 800,
    height: int = 600
) -> Dict[str, Any]:
    """
    Generate a preview image of a LEGO brick.
    
    This is the main entry point for the MCP tool.
    """
    generator = PreviewGenerator(app)
    
    # Parse view
    view_enum = ViewAngle.ISOMETRIC
    for v in ViewAngle:
        if v.value == view:
            view_enum = v
            break
    
    # Parse style
    style_enum = RenderStyle.SHADED_EDGES
    for s in RenderStyle:
        if s.value == style:
            style_enum = s
            break
    
    settings = ImageSettings(width=width, height=height)
    
    return generator.generate_preview(
        component_name,
        output_path,
        view_enum,
        style_enum,
        settings
    )


def generate_brick_thumbnails(
    app: adsk.core.Application,
    component_name: str,
    output_dir: str,
    size: int = 256
) -> Dict[str, Any]:
    """
    Generate thumbnails from multiple angles.
    """
    generator = PreviewGenerator(app)
    
    views = [ViewAngle.ISOMETRIC, ViewAngle.TOP, ViewAngle.FRONT]
    
    settings = ImageSettings(width=size, height=size)
    
    return generator.generate_all_views(
        component_name,
        output_dir,
        views,
        RenderStyle.SHADED_EDGES,
        settings
    )


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

PREVIEW_TOOLS = {
    "generate_preview": {
        "description": """Generate a preview image of a LEGO brick.

Views: front, back, top, bottom, left, right, isometric, isometric_top, isometric_bottom, front_top
Styles: shaded, shaded_edges, wireframe, hidden_edge, realistic""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string",
                    "description": "Name of the brick component"
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to save the image"
                },
                "view": {
                    "type": "string",
                    "enum": ["front", "back", "top", "bottom", "left", "right",
                             "isometric", "isometric_top", "isometric_bottom", "front_top"],
                    "default": "isometric"
                },
                "style": {
                    "type": "string",
                    "enum": ["shaded", "shaded_edges", "wireframe", "hidden_edge", "realistic"],
                    "default": "shaded_edges"
                },
                "width": {
                    "type": "integer",
                    "default": 800
                },
                "height": {
                    "type": "integer",
                    "default": 600
                }
            },
            "required": ["component_name", "output_path"]
        }
    },
    
    "generate_all_views": {
        "description": "Generate preview images from multiple angles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string"
                },
                "output_dir": {
                    "type": "string"
                },
                "views": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["front", "top", "isometric", "isometric_bottom"]
                },
                "width": {
                    "type": "integer",
                    "default": 800
                },
                "height": {
                    "type": "integer", 
                    "default": 600
                }
            },
            "required": ["component_name", "output_dir"]
        }
    },
    
    "generate_thumbnail": {
        "description": "Generate a small thumbnail image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string"
                },
                "output_path": {
                    "type": "string"
                },
                "size": {
                    "type": "integer",
                    "default": 256
                }
            },
            "required": ["component_name", "output_path"]
        }
    }
}
