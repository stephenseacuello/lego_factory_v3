"""
Quality Heatmap API Routes
==========================

REST API endpoints for 3D quality heatmaps and defect mapping.

Endpoints:
- Heatmap generation and retrieval
- 3D defect mapping
- Defect clustering analysis
- Temporal trend analysis

Author: LegoMCP Team
Version: 2.0.0
"""

from flask import Blueprint, request, jsonify, send_file
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
import uuid
import io

logger = logging.getLogger(__name__)

# Create Blueprint
heatmap_bp = Blueprint('heatmap', __name__, url_prefix='/heatmap')


# ================== Heatmap Management ==================

@heatmap_bp.route('/', methods=['GET'])
def list_heatmaps():
    """
    List generated quality heatmaps.

    Query Parameters:
        equipment_id: Filter by equipment
        part_id: Filter by part
        heatmap_type: Filter by type
        since: Filter by generation date

    Returns:
        List of heatmaps
    """
    try:
        from services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()

        equipment_id = request.args.get('equipment_id')
        part_id = request.args.get('part_id')
        heatmap_type = request.args.get('heatmap_type')

        heatmaps = generator.list_heatmaps(
            equipment_id=equipment_id,
            part_id=part_id,
            heatmap_type=heatmap_type
        )

        return jsonify({
            'success': True,
            'count': len(heatmaps),
            'data': [h.to_dict() for h in heatmaps]
        })

    except Exception as e:
        logger.error(f"Error listing heatmaps: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/', methods=['POST'])
def generate_heatmap():
    """
    Generate a new quality heatmap.

    Body:
        part_id: Part identifier
        equipment_id: Equipment OME ID (optional)
        heatmap_type: Type (defect_density, dimensional_deviation, surface_quality, temperature)
        time_range: Time range for data collection
        resolution: Resolution (high, medium, low)

    Returns:
        Generation task ID
    """
    try:
        from services.vision import (
            get_quality_heatmap_generator,
            HeatmapType,
            HeatmapConfig
        )

        data = request.get_json()

        if not data or 'part_id' not in data or 'heatmap_type' not in data:
            return jsonify({
                'success': False,
                'error': 'part_id and heatmap_type required'
            }), 400

        generator = get_quality_heatmap_generator()

        # Parse time range
        time_range = data.get('time_range', {})
        start_time = None
        end_time = None
        if 'start' in time_range:
            start_time = datetime.fromisoformat(time_range['start'].replace('Z', '+00:00'))
        if 'end' in time_range:
            end_time = datetime.fromisoformat(time_range['end'].replace('Z', '+00:00'))

        # Create config
        config = HeatmapConfig(
            heatmap_type=HeatmapType(data['heatmap_type']),
            resolution=data.get('resolution', 'medium'),
            time_start=start_time,
            time_end=end_time
        )

        # Start generation
        task_id = generator.generate_async(
            part_id=data['part_id'],
            equipment_id=data.get('equipment_id'),
            config=config
        )

        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'status': 'generating',
                'message': 'Heatmap generation started'
            }
        }), 202

    except Exception as e:
        logger.error(f"Error generating heatmap: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@heatmap_bp.route('/<heatmap_id>', methods=['GET'])
def get_heatmap(heatmap_id: str):
    """
    Get heatmap data.

    Path Parameters:
        heatmap_id: Heatmap identifier

    Query Parameters:
        resolution: Override resolution (high, medium, low)
        format: Output format (json, mesh)

    Returns:
        Heatmap data for Unity visualization
    """
    try:
        from services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()

        resolution = request.args.get('resolution', 'medium')
        output_format = request.args.get('format', 'json')

        heatmap = generator.get_heatmap(heatmap_id)

        if not heatmap:
            return jsonify({
                'success': False,
                'error': 'Heatmap not found'
            }), 404

        if output_format == 'mesh':
            # Return mesh data for Unity
            mesh_data = generator.get_mesh_data(heatmap_id, resolution)
            return jsonify({
                'success': True,
                'data': mesh_data
            })

        return jsonify({
            'success': True,
            'data': heatmap.to_unity_dict(resolution)
        })

    except Exception as e:
        logger.error(f"Error getting heatmap: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/<heatmap_id>/mesh', methods=['GET'])
def download_heatmap_mesh(heatmap_id: str):
    """
    Download heatmap as 3D mesh file.

    Path Parameters:
        heatmap_id: Heatmap identifier

    Query Parameters:
        format: Mesh format (obj, stl, gltf)

    Returns:
        Mesh file download
    """
    try:
        from services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()

        mesh_format = request.args.get('format', 'obj')

        mesh_data, filename = generator.export_mesh(heatmap_id, mesh_format)

        if not mesh_data:
            return jsonify({
                'success': False,
                'error': 'Could not generate mesh'
            }), 500

        return send_file(
            io.BytesIO(mesh_data),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Error downloading mesh: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/<heatmap_id>/statistics', methods=['GET'])
def get_heatmap_statistics(heatmap_id: str):
    """
    Get heatmap statistics.

    Path Parameters:
        heatmap_id: Heatmap identifier

    Returns:
        Statistical analysis of heatmap
    """
    try:
        from services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()
        stats = generator.get_statistics(heatmap_id)

        if not stats:
            return jsonify({
                'success': False,
                'error': 'Heatmap not found'
            }), 404

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== 3D Defect Mapping ==================

@heatmap_bp.route('/defects/3d-map', methods=['POST'])
def map_defects_to_3d():
    """
    Map 2D defect detections to 3D coordinates.

    Body:
        detections: List of 2D detections with camera info
        camera_calibration: Camera intrinsics and extrinsics
        part_geometry: Part 3D model reference (optional)

    Returns:
        3D defect positions
    """
    try:
        from services.vision import get_defect_mapping_service

        data = request.get_json()

        if not data or 'detections' not in data or 'camera_calibration' not in data:
            return jsonify({
                'success': False,
                'error': 'detections and camera_calibration required'
            }), 400

        mapper = get_defect_mapping_service()

        result = mapper.map_to_3d(
            detections=data['detections'],
            camera_calibration=data['camera_calibration'],
            part_geometry=data.get('part_geometry')
        )

        return jsonify({
            'success': True,
            'data': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Error mapping defects: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@heatmap_bp.route('/defects/clusters', methods=['GET'])
def get_defect_clusters():
    """
    Get clustered defect analysis.

    Query Parameters:
        part_id: Filter by part
        min_cluster_size: Minimum cluster size (default: 3)
        max_distance_mm: Maximum distance between points (default: 10)

    Returns:
        Defect clusters with analysis
    """
    try:
        from services.vision import get_defect_mapping_service

        mapper = get_defect_mapping_service()

        part_id = request.args.get('part_id')
        min_size = int(request.args.get('min_cluster_size', 3))
        max_distance = float(request.args.get('max_distance_mm', 10))

        clusters = mapper.get_clusters(
            part_id=part_id,
            min_cluster_size=min_size,
            max_distance_mm=max_distance
        )

        return jsonify({
            'success': True,
            'count': len(clusters),
            'data': [c.to_dict() for c in clusters]
        })

    except Exception as e:
        logger.error(f"Error getting clusters: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/defects/clusters/<cluster_id>', methods=['GET'])
def get_cluster_details(cluster_id: str):
    """
    Get detailed cluster analysis.

    Path Parameters:
        cluster_id: Cluster identifier

    Returns:
        Cluster details with root cause analysis
    """
    try:
        from services.vision import get_defect_mapping_service

        mapper = get_defect_mapping_service()
        cluster = mapper.get_cluster(cluster_id)

        if not cluster:
            return jsonify({
                'success': False,
                'error': 'Cluster not found'
            }), 404

        return jsonify({
            'success': True,
            'data': cluster.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting cluster: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Temporal Trends ==================

@heatmap_bp.route('/trends/temporal', methods=['GET'])
def get_temporal_trends():
    """
    Get temporal quality trends.

    Query Parameters:
        part_id: Part to analyze
        metric: Metric type (defect_rate, dimensions, surface)
        period: Analysis period (1d, 7d, 30d)
        granularity: Data granularity (hour, day, week)

    Returns:
        Temporal trend data
    """
    try:
        from services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()

        part_id = request.args.get('part_id')
        metric = request.args.get('metric', 'defect_rate')
        period = request.args.get('period', '7d')
        granularity = request.args.get('granularity', 'day')

        if not part_id:
            return jsonify({
                'success': False,
                'error': 'part_id required'
            }), 400

        trends = generator.get_temporal_trends(
            part_id=part_id,
            metric=metric,
            period=period,
            granularity=granularity
        )

        return jsonify({
            'success': True,
            'data': trends
        })

    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/trends/spatial', methods=['GET'])
def get_spatial_trends():
    """
    Get spatial quality trends.

    Query Parameters:
        part_id: Part to analyze
        region: Specific region to analyze (optional)

    Returns:
        Spatial trend data
    """
    try:
        from services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()

        part_id = request.args.get('part_id')
        region = request.args.get('region')

        if not part_id:
            return jsonify({
                'success': False,
                'error': 'part_id required'
            }), 400

        trends = generator.get_spatial_trends(
            part_id=part_id,
            region=region
        )

        return jsonify({
            'success': True,
            'data': trends
        })

    except Exception as e:
        logger.error(f"Error getting spatial trends: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Root Cause Analysis ==================

@heatmap_bp.route('/analysis/root-cause', methods=['POST'])
def analyze_root_cause():
    """
    Analyze root cause of quality issues.

    Body:
        cluster_ids: List of cluster IDs to analyze
        include_equipment: Include equipment data
        include_process: Include process parameters

    Returns:
        Root cause analysis
    """
    try:
        from services.vision import get_quality_heatmap_generator

        data = request.get_json()

        if not data or 'cluster_ids' not in data:
            return jsonify({
                'success': False,
                'error': 'cluster_ids required'
            }), 400

        generator = get_quality_heatmap_generator()

        analysis = generator.analyze_root_cause(
            cluster_ids=data['cluster_ids'],
            include_equipment=data.get('include_equipment', True),
            include_process=data.get('include_process', True)
        )

        return jsonify({
            'success': True,
            'data': analysis
        })

    except Exception as e:
        logger.error(f"Error analyzing root cause: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/analysis/correlation', methods=['POST'])
def analyze_correlation():
    """
    Analyze correlation between defects and process parameters.

    Body:
        defect_type: Type of defect to analyze
        parameters: List of parameters to correlate

    Returns:
        Correlation analysis
    """
    try:
        from services.vision import get_quality_heatmap_generator

        data = request.get_json()

        if not data or 'defect_type' not in data:
            return jsonify({
                'success': False,
                'error': 'defect_type required'
            }), 400

        generator = get_quality_heatmap_generator()

        correlation = generator.analyze_correlation(
            defect_type=data['defect_type'],
            parameters=data.get('parameters', [])
        )

        return jsonify({
            'success': True,
            'data': correlation
        })

    except Exception as e:
        logger.error(f"Error analyzing correlation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Unity Integration ==================

@heatmap_bp.route('/unity/overlay', methods=['GET'])
def get_unity_overlay():
    """
    Get heatmap overlay data for Unity.

    Query Parameters:
        heatmap_id: Heatmap to overlay
        equipment_id: Equipment to overlay on

    Returns:
        Unity-compatible overlay data
    """
    try:
        from services.vision import get_quality_heatmap_generator

        heatmap_id = request.args.get('heatmap_id')
        equipment_id = request.args.get('equipment_id')

        if not heatmap_id:
            return jsonify({
                'success': False,
                'error': 'heatmap_id required'
            }), 400

        generator = get_quality_heatmap_generator()

        overlay = generator.get_unity_overlay(
            heatmap_id=heatmap_id,
            equipment_id=equipment_id
        )

        return jsonify({
            'success': True,
            'data': overlay
        })

    except Exception as e:
        logger.error(f"Error getting overlay: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@heatmap_bp.route('/unity/color-scale', methods=['GET'])
def get_color_scale():
    """
    Get color scale configuration for Unity.

    Query Parameters:
        heatmap_type: Type of heatmap

    Returns:
        Color scale configuration
    """
    try:
        heatmap_type = request.args.get('heatmap_type', 'defect_density')

        # Default color scales
        color_scales = {
            'defect_density': {
                'min_color': '#00FF00',  # Green - low defects
                'max_color': '#FF0000',  # Red - high defects
                'mid_color': '#FFFF00',  # Yellow - medium
                'min_value': 0,
                'max_value': 1
            },
            'dimensional_deviation': {
                'min_color': '#0000FF',  # Blue - under
                'max_color': '#FF0000',  # Red - over
                'mid_color': '#00FF00',  # Green - nominal
                'min_value': -0.5,
                'max_value': 0.5
            },
            'surface_quality': {
                'min_color': '#FF0000',  # Red - poor
                'max_color': '#00FF00',  # Green - excellent
                'min_value': 0,
                'max_value': 100
            },
            'temperature': {
                'min_color': '#0000FF',  # Blue - cold
                'max_color': '#FF0000',  # Red - hot
                'mid_color': '#FFFF00',  # Yellow - warm
                'min_value': 20,
                'max_value': 250
            }
        }

        scale = color_scales.get(heatmap_type, color_scales['defect_density'])

        return jsonify({
            'success': True,
            'data': {
                'heatmap_type': heatmap_type,
                'color_scale': scale
            }
        })

    except Exception as e:
        logger.error(f"Error getting color scale: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


__all__ = ['heatmap_bp']
