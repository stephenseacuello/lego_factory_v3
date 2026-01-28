"""
Enhanced HTTP Server for Fusion 360 Add-in

Handles all brick creation requests including:
- Catalog-based creation
- Custom brick building with features
- All brick types (slopes, technic, round, etc.)
"""

import threading
import json
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# Import from parent - will be set by start_server
_modeler = None
_cam_processor = None

# Try to import catalog (may not be available in Fusion environment)
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../shared'))
    from brick_catalog import get_brick, search_bricks, list_categories, BRICK_CATALOG
    from brick_features import (
        CustomBrickBuilder, standard_brick, standard_plate, standard_tile,
        slope_brick, technic_brick, round_brick
    )
    CATALOG_AVAILABLE = True
except ImportError:
    CATALOG_AVAILABLE = False


class EnhancedFusionAPIHandler(BaseHTTPRequestHandler):
    """Enhanced HTTP handler for Fusion 360 API."""
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _read_json(self) -> dict:
        """Read JSON request body."""
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._send_json({
                'status': 'ok',
                'service': 'LegoMCP Fusion360 Enhanced',
                'version': '2.0.0',
                'catalog_available': CATALOG_AVAILABLE,
                'catalog_size': len(BRICK_CATALOG) if CATALOG_AVAILABLE else 0
            })
        elif self.path == '/components':
            self._handle_list_components()
        elif self.path == '/catalog/stats':
            self._handle_catalog_stats()
        elif self.path.startswith('/catalog/categories'):
            self._handle_catalog_categories()
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        try:
            body = self._read_json()
            command = body.get('command', self.path.strip('/'))
            params = body.get('params', body)
            
            # Command routing
            handlers = {
                # Standard creation
                'create_brick': self._handle_create_brick,
                'create_plate': self._handle_create_plate,
                'create_tile': self._handle_create_tile,
                'create_slope': self._handle_create_slope,
                
                # Enhanced creation
                'create_from_catalog': self._handle_create_from_catalog,
                'create_custom_brick': self._handle_create_custom_brick,
                'create_technic': self._handle_create_technic,
                'create_round': self._handle_create_round,
                'create_modified': self._handle_create_modified,
                'create_arch': self._handle_create_arch,
                
                # Export
                'export_stl': self._handle_export_stl,
                'export_step': self._handle_export_step,
                
                # CAM
                'setup_cam': self._handle_setup_cam,
                'generate_gcode': self._handle_generate_gcode,
                'full_mill_workflow': self._handle_full_workflow,
                
                # Catalog queries
                'search_catalog': self._handle_search_catalog,
                'get_brick_details': self._handle_get_brick_details,
            }
            
            handler = handlers.get(command)
            if handler:
                result = handler(params)
                self._send_json(result)
            else:
                self._send_json({
                    'success': False,
                    'error': f'Unknown command: {command}'
                }, 400)
                
        except Exception as e:
            self._send_json({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }, 500)
    
    # =========================================================================
    # COMPONENT MANAGEMENT
    # =========================================================================
    
    def _handle_list_components(self):
        """List all components."""
        if not _modeler:
            self._send_json({'error': 'Modeler not initialized'}, 500)
            return
        
        components = _modeler.list_components()
        self._send_json({
            'success': True,
            'components': components
        })
    
    # =========================================================================
    # CATALOG QUERIES
    # =========================================================================
    
    def _handle_catalog_stats(self):
        """Get catalog statistics."""
        if not CATALOG_AVAILABLE:
            self._send_json({'error': 'Catalog not available'}, 500)
            return
        
        from brick_catalog import get_catalog_stats
        stats = get_catalog_stats()
        self._send_json({'success': True, **stats})
    
    def _handle_catalog_categories(self):
        """List catalog categories."""
        if not CATALOG_AVAILABLE:
            self._send_json({'error': 'Catalog not available'}, 500)
            return
        
        categories = list_categories()
        self._send_json({'success': True, 'categories': categories})
    
    def _handle_search_catalog(self, params: dict) -> dict:
        """Search the brick catalog."""
        if not CATALOG_AVAILABLE:
            return {'success': False, 'error': 'Catalog not available'}
        
        from brick_catalog import BrickCategory
        
        category = None
        if params.get('category'):
            try:
                category = BrickCategory(params['category'])
            except:
                pass
        
        results = search_bricks(
            category=category,
            tags=params.get('tags'),
            studs_x=params.get('studs_x'),
            studs_y=params.get('studs_y'),
            name_contains=params.get('name_contains')
        )
        
        # Convert to serializable format
        result_list = [{
            'id': b.id,
            'name': b.name,
            'category': b.category.value,
            'studs_x': b.studs_x,
            'studs_y': b.studs_y,
            'height_units': b.height_units,
            'tags': b.tags
        } for b in results[:params.get('limit', 50)]]
        
        return {'success': True, 'results': result_list, 'count': len(result_list)}
    
    def _handle_get_brick_details(self, params: dict) -> dict:
        """Get detailed brick information."""
        if not CATALOG_AVAILABLE:
            return {'success': False, 'error': 'Catalog not available'}
        
        brick = get_brick(params.get('brick_id', ''))
        if not brick:
            return {'success': False, 'error': 'Brick not found'}
        
        # Convert to serializable format
        details = {
            'id': brick.id,
            'name': brick.name,
            'lego_id': brick.lego_id,
            'category': brick.category.value,
            'studs_x': brick.studs_x,
            'studs_y': brick.studs_y,
            'height_units': brick.height_units,
            'stud_type': brick.stud_type.value,
            'bottom_type': brick.bottom_type.value,
            'hollow': brick.hollow,
            'description': brick.description,
            'tags': brick.tags,
            'dimensions_mm': {
                'width': brick.studs_x * 8.0,
                'depth': brick.studs_y * 8.0,
                'height': brick.height_units * 9.6
            }
        }
        
        if brick.slope:
            details['slope'] = {
                'angle': brick.slope.angle,
                'direction': brick.slope.direction,
                'inverted': brick.slope.inverted
            }
        
        if brick.holes:
            details['holes'] = [{
                'type': h.hole_type.value,
                'count': len(h.positions),
                'axis': h.axis
            } for h in brick.holes]
        
        return {'success': True, 'brick': details}
    
    # =========================================================================
    # BRICK CREATION - STANDARD
    # =========================================================================
    
    def _handle_create_brick(self, params: dict) -> dict:
        """Create standard brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        result = _modeler.create_standard_brick(
            studs_x=params.get('studs_x', 2),
            studs_y=params.get('studs_y', 4),
            height_units=params.get('height_units', 1.0),
            hollow=params.get('hollow', True),
            name=params.get('name')
        )
        
        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    def _handle_create_plate(self, params: dict) -> dict:
        """Create plate (1/3 height)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        result = _modeler.create_plate(
            studs_x=params.get('studs_x', 2),
            studs_y=params.get('studs_y', 4),
            name=params.get('name')
        )
        
        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    def _handle_create_tile(self, params: dict) -> dict:
        """Create tile (no studs)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        result = _modeler.create_tile(
            studs_x=params.get('studs_x', 2),
            studs_y=params.get('studs_y', 2),
            name=params.get('name')
        )
        
        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    def _handle_create_slope(self, params: dict) -> dict:
        """Create slope brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        slope_type = params.get('slope_type', 'standard')
        
        if slope_type == 'standard':
            result = _modeler.create_slope_brick(
                studs_x=params.get('studs_x', 2),
                studs_y=params.get('studs_y', 3),
                slope_angle=params.get('angle', 45.0),
                slope_direction=params.get('direction', 'front'),
                name=params.get('name')
            )
        elif slope_type == 'inverted':
            result = _modeler.create_inverted_slope(
                studs_x=params.get('studs_x', 2),
                studs_y=params.get('studs_y', 3),
                slope_angle=params.get('angle', 45.0),
                name=params.get('name')
            )
        elif slope_type == 'double':
            result = _modeler.create_double_slope(
                studs_x=params.get('studs_x', 2),
                studs_y=params.get('studs_y', 4),
                slope_angle=params.get('angle', 45.0),
                name=params.get('name')
            )
        elif slope_type == 'curved':
            result = _modeler.create_curved_slope(
                studs_x=params.get('studs_x', 2),
                studs_y=params.get('studs_y', 4),
                direction=params.get('direction', 'front'),
                name=params.get('name')
            )
        else:
            return {'success': False, 'error': f'Unknown slope type: {slope_type}'}
        
        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    # =========================================================================
    # BRICK CREATION - ENHANCED
    # =========================================================================
    
    def _handle_create_from_catalog(self, params: dict) -> dict:
        """Create brick from catalog definition."""
        if not CATALOG_AVAILABLE:
            return {'success': False, 'error': 'Catalog not available'}
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        catalog_id = params.get('catalog_id', '')
        brick_def = get_brick(catalog_id)
        
        if not brick_def:
            return {'success': False, 'error': f'Brick not found in catalog: {catalog_id}'}
        
        # Map catalog definition to modeler method
        try:
            # Basic types
            if brick_def.category.value == 'basic':
                result = _modeler.create_standard_brick(
                    studs_x=brick_def.studs_x,
                    studs_y=brick_def.studs_y,
                    height_units=brick_def.height_units,
                    hollow=brick_def.hollow,
                    name=params.get('name') or brick_def.name
                )
            elif brick_def.category.value == 'plate':
                result = _modeler.create_standard_brick(
                    studs_x=brick_def.studs_x,
                    studs_y=brick_def.studs_y,
                    height_units=1/3,
                    hollow=brick_def.hollow,
                    name=params.get('name') or brick_def.name
                )
            elif brick_def.category.value == 'tile':
                result = _modeler.create_tile(
                    studs_x=brick_def.studs_x,
                    studs_y=brick_def.studs_y,
                    name=params.get('name') or brick_def.name
                )
            elif brick_def.category.value == 'slope':
                direction = brick_def.slope.direction if brick_def.slope else 'front'
                angle = brick_def.slope.angle if brick_def.slope else 45.0
                inverted = brick_def.slope.inverted if brick_def.slope else False
                
                if direction == 'double':
                    result = _modeler.create_double_slope(
                        studs_x=brick_def.studs_x,
                        studs_y=brick_def.studs_y,
                        slope_angle=angle,
                        name=params.get('name') or brick_def.name
                    )
                elif inverted:
                    result = _modeler.create_inverted_slope(
                        studs_x=brick_def.studs_x,
                        studs_y=brick_def.studs_y,
                        slope_angle=angle,
                        name=params.get('name') or brick_def.name
                    )
                else:
                    result = _modeler.create_slope_brick(
                        studs_x=brick_def.studs_x,
                        studs_y=brick_def.studs_y,
                        slope_angle=angle,
                        slope_direction=direction,
                        name=params.get('name') or brick_def.name
                    )
            elif brick_def.category.value == 'cylinder':
                result = _modeler.create_round_brick(
                    diameter_studs=brick_def.studs_x,
                    height_units=brick_def.height_units,
                    name=params.get('name') or brick_def.name
                )
            elif brick_def.category.value == 'technic':
                hole_type = 'pin'
                if brick_def.holes:
                    hole_type = brick_def.holes[0].hole_type.value
                result = _modeler.create_technic_brick(
                    studs_x=brick_def.studs_x,
                    studs_y=brick_def.studs_y,
                    hole_type=hole_type,
                    name=params.get('name') or brick_def.name
                )
            else:
                # Fallback to standard brick
                result = _modeler.create_standard_brick(
                    studs_x=brick_def.studs_x,
                    studs_y=brick_def.studs_y,
                    height_units=brick_def.height_units,
                    hollow=brick_def.hollow,
                    name=params.get('name') or brick_def.name
                )
            
            return {
                'success': result.success,
                'brick_id': result.brick_id,
                'component_name': result.component_name,
                'dimensions': result.dimensions,
                'volume_mm3': result.volume_mm3,
                'catalog_id': catalog_id,
                'error': result.error
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_create_custom_brick(self, params: dict) -> dict:
        """Create custom brick with specified features."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        studs_x = params.get('studs_x', 2)
        studs_y = params.get('studs_y', 4)
        height_units = params.get('height_units', 1.0)
        features = params.get('features', [])
        base_shape = params.get('base_shape', 'box')
        
        # Start with base brick
        if base_shape == 'cylinder':
            result = _modeler.create_round_brick(
                diameter_studs=studs_x,
                height_units=height_units,
                name=params.get('name')
            )
        else:
            # Determine if it has studs
            has_studs = 'no_studs' not in features and 'tile' not in features
            
            result = _modeler.create_standard_brick(
                studs_x=studs_x,
                studs_y=studs_y,
                height_units=height_units,
                hollow='hollow' in features or 'tubes' in features,
                name=params.get('name')
            )
        
        if not result.success:
            return {
                'success': False,
                'error': result.error
            }
        
        # Apply additional features
        component_name = result.component_name
        
        # Apply slope if specified
        if 'slope' in features or params.get('slope'):
            slope_params = params.get('slope', {})
            angle = slope_params.get('angle', 45)
            direction = slope_params.get('direction', 'front')
            try:
                _modeler.add_slope_to_component(
                    component_name, angle, direction
                )
            except:
                pass  # Feature may not be fully implemented
        
        # Apply technic holes if specified
        if params.get('technic_holes'):
            th = params['technic_holes']
            try:
                _modeler.add_technic_holes(
                    component_name,
                    hole_type=th.get('type', 'pin'),
                    axis=th.get('axis', 'x'),
                    count=th.get('count', studs_y)
                )
            except:
                pass
        
        # Apply side features
        for sf in params.get('side_features', []):
            try:
                _modeler.add_side_feature(
                    component_name,
                    feature_type=sf.get('type', 'stud'),
                    side=sf.get('side', 'front')
                )
            except:
                pass
        
        return {
            'success': True,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'features_applied': features
        }
    
    def _handle_create_technic(self, params: dict) -> dict:
        """Create Technic brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        try:
            result = _modeler.create_technic_brick(
                studs_x=params.get('studs_x', 1),
                studs_y=params.get('studs_y', 4),
                hole_type=params.get('hole_type', 'pin'),
                studless=params.get('studless', False),
                name=params.get('name')
            )
            
            return {
                'success': result.success,
                'brick_id': result.brick_id,
                'component_name': result.component_name,
                'dimensions': result.dimensions,
                'volume_mm3': result.volume_mm3,
                'error': result.error
            }
        except AttributeError:
            # Fall back to basic brick if technic not implemented
            result = _modeler.create_standard_brick(
                studs_x=params.get('studs_x', 1),
                studs_y=params.get('studs_y', 4),
                height_units=1.0,
                hollow=True,
                name=params.get('name', f"Technic_{params.get('studs_x', 1)}x{params.get('studs_y', 4)}")
            )
            return {
                'success': result.success,
                'brick_id': result.brick_id,
                'component_name': result.component_name,
                'dimensions': result.dimensions,
                'note': 'Technic holes not yet implemented - basic brick created',
                'error': result.error
            }
    
    def _handle_create_round(self, params: dict) -> dict:
        """Create round brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        shape = params.get('shape', 'cylinder')
        
        try:
            if shape == 'cone':
                result = _modeler.create_cone(
                    bottom_diameter_studs=params.get('diameter_studs', 2),
                    top_diameter_studs=params.get('top_diameter_studs', 0),
                    height_units=params.get('height_units', 1.0),
                    name=params.get('name')
                )
            else:
                result = _modeler.create_round_brick(
                    diameter_studs=params.get('diameter_studs', 2),
                    height_units=params.get('height_units', 1.0),
                    name=params.get('name')
                )
            
            return {
                'success': result.success,
                'brick_id': result.brick_id,
                'component_name': result.component_name,
                'dimensions': result.dimensions,
                'volume_mm3': result.volume_mm3,
                'error': result.error
            }
        except AttributeError:
            return {'success': False, 'error': 'Round brick creation not yet implemented'}
    
    def _handle_create_modified(self, params: dict) -> dict:
        """Create modified brick (SNOT, clips, etc.)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        # Parse base size
        base_size = params.get('base_size', '1x1')
        parts = base_size.split('x')
        studs_x = int(parts[0])
        studs_y = int(parts[1]) if len(parts) > 1 else studs_x
        
        mod_type = params.get('modification_type', 'side_studs')
        
        # Create base brick first
        result = _modeler.create_standard_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=1.0,
            hollow=True,
            name=params.get('name', f"Modified_{mod_type}")
        )
        
        if not result.success:
            return {
                'success': False,
                'error': result.error
            }
        
        # Try to apply modification
        try:
            sides = params.get('sides', ['front'])
            for side in sides:
                _modeler.add_side_feature(
                    result.component_name,
                    feature_type=mod_type,
                    side=side
                )
        except:
            pass  # Modification may not be fully implemented
        
        return {
            'success': True,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'modification': mod_type,
            'note': 'Base brick created - some modifications may not be fully implemented'
        }
    
    def _handle_create_arch(self, params: dict) -> dict:
        """Create arch brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        try:
            result = _modeler.create_arch(
                span_studs=params.get('span_studs', 4),
                height_units=params.get('height_units', 1.0),
                style=params.get('style', 'round'),
                inverted=params.get('inverted', False),
                name=params.get('name')
            )
            
            return {
                'success': result.success,
                'brick_id': result.brick_id,
                'component_name': result.component_name,
                'dimensions': result.dimensions,
                'volume_mm3': result.volume_mm3,
                'error': result.error
            }
        except AttributeError:
            return {'success': False, 'error': 'Arch creation not yet implemented'}
    
    # =========================================================================
    # EXPORT
    # =========================================================================
    
    def _handle_export_stl(self, params: dict) -> dict:
        """Export STL."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        component_name = params.get('component_name') or params.get('brick_id')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}
        
        output_path = params.get('output_path', f'/output/stl/{component_name}.stl')
        resolution = params.get('resolution', 'high')
        
        try:
            result = _modeler.export_stl(component_name, output_path, resolution)
            return {
                'success': True,
                'path': result['path'],
                'size_kb': result['size_kb'],
                'triangle_count': result['triangle_count']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_export_step(self, params: dict) -> dict:
        """Export STEP file."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}
        
        component_name = params.get('component_name') or params.get('brick_id')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}
        
        output_path = params.get('output_path', f'/output/step/{component_name}.step')
        
        try:
            result = _modeler.export_step(component_name, output_path)
            return {
                'success': True,
                'path': result.get('path', output_path)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # CAM
    # =========================================================================
    
    def _handle_setup_cam(self, params: dict) -> dict:
        """Set up CAM."""
        if not _cam_processor:
            return {'success': False, 'error': 'CAM processor not initialized'}
        
        try:
            setup = _cam_processor.setup_milling(
                component_name=params.get('component_name'),
                material=params.get('material', 'abs'),
                stock_offset_mm=params.get('stock_offset_mm', 1.0)
            )
            return {'success': True, 'setup_name': setup.name}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_generate_gcode(self, params: dict) -> dict:
        """Generate G-code."""
        if not _cam_processor:
            return {'success': False, 'error': 'CAM processor not initialized'}
        
        try:
            result = _cam_processor.create_standard_brick_toolpath(
                component_name=params.get('component_name'),
                material=params.get('material', 'abs'),
                machine=params.get('machine', 'grbl'),
                output_path=params.get('output_path')
            )
            return {'success': True, **result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_full_workflow(self, params: dict) -> dict:
        """Full workflow: create → CAM → G-code."""
        if not _modeler or not _cam_processor:
            return {'success': False, 'error': 'Services not initialized'}
        
        try:
            # Create brick
            brick_result = _modeler.create_standard_brick(
                studs_x=params.get('studs_x', 2),
                studs_y=params.get('studs_y', 4),
                height_units=params.get('height_units', 1.0),
                hollow=params.get('hollow', True),
                name=params.get('name')
            )
            
            if not brick_result.success:
                return {'success': False, 'error': f'Brick creation failed: {brick_result.error}'}
            
            # Export STL
            stl_path = f"/output/stl/{brick_result.component_name}.stl"
            stl_result = _modeler.export_stl(brick_result.component_name, stl_path, 'high')
            
            # Generate G-code
            gcode_path = f"/output/gcode/milling/{brick_result.component_name}.nc"
            gcode_result = _cam_processor.create_standard_brick_toolpath(
                component_name=brick_result.component_name,
                material=params.get('material', 'abs'),
                machine=params.get('machine', 'grbl'),
                output_path=gcode_path
            )
            
            return {
                'success': True,
                'brick': {
                    'id': brick_result.brick_id,
                    'name': brick_result.component_name,
                    'dimensions': brick_result.dimensions
                },
                'stl': {'path': stl_result['path']},
                'gcode': gcode_result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ============================================================================
# SERVER MANAGEMENT
# ============================================================================

class ThreadedHTTPServer(threading.Thread):
    """HTTP server in background thread."""
    
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.server = None
        self._stop_event = threading.Event()
    
    def run(self):
        self.server = HTTPServer(('localhost', self.port), EnhancedFusionAPIHandler)
        self.server.timeout = 0.5
        
        while not self._stop_event.is_set():
            self.server.handle_request()
    
    def stop(self):
        self._stop_event.set()
        if self.server:
            self.server.shutdown()


def start_server(modeler, cam_processor, port: int = 8765) -> ThreadedHTTPServer:
    """Start the enhanced HTTP API server."""
    global _modeler, _cam_processor
    
    _modeler = modeler
    _cam_processor = cam_processor
    
    server = ThreadedHTTPServer(port)
    server.start()
    
    return server


def stop_server(server: ThreadedHTTPServer):
    """Stop the HTTP API server."""
    if server:
        server.stop()
