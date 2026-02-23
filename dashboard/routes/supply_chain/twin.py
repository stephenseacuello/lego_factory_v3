"""
Supply Chain Digital Twin API Routes
====================================

REST API endpoints for supply chain digital twin.

Endpoints:
- Network topology and visualization
- Node and edge management
- Disruption simulation
- Risk propagation analysis
- Material flow visualization

Author: LegoMCP Team
Version: 2.0.0
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

# Create Blueprint
supply_chain_twin_bp = Blueprint('supply_chain_twin', __name__, url_prefix='/twin')


# ================== Network Topology ==================

@supply_chain_twin_bp.route('/network', methods=['GET'])
def get_network():
    """
    Get complete supply chain network topology.

    Query Parameters:
        include_metrics: Include performance metrics (default: true)
        include_risks: Include risk scores (default: true)

    Returns:
        Network topology with nodes and edges
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()

        include_metrics = request.args.get('include_metrics', 'true').lower() == 'true'
        include_risks = request.args.get('include_risks', 'true').lower() == 'true'

        network = service.get_network(
            include_metrics=include_metrics,
            include_risks=include_risks
        )

        return jsonify({
            'success': True,
            'data': network.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting network: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/network/summary', methods=['GET'])
def get_network_summary():
    """
    Get network summary statistics.

    Returns:
        Summary with node counts, avg lead times, risk scores
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        summary = service.get_network_summary()

        return jsonify({
            'success': True,
            'data': summary
        })

    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Node Management ==================

@supply_chain_twin_bp.route('/nodes', methods=['GET'])
def list_nodes():
    """
    List all supply chain nodes.

    Query Parameters:
        node_type: Filter by type (supplier, warehouse, distribution_center, plant, customer)
        status: Filter by status (active, at_risk, disrupted, offline)
        country: Filter by country

    Returns:
        List of nodes
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service, NodeType, NodeStatus

        service = get_supply_chain_twin_service()

        node_type_filter = request.args.get('node_type')
        status_filter = request.args.get('status')
        country_filter = request.args.get('country')

        nodes = service.get_all_nodes()

        # Apply filters
        if node_type_filter:
            try:
                node_type = NodeType(node_type_filter)
                nodes = [n for n in nodes if n.node_type == node_type]
            except ValueError:
                pass

        if status_filter:
            try:
                status = NodeStatus(status_filter)
                nodes = [n for n in nodes if n.status == status]
            except ValueError:
                pass

        if country_filter:
            nodes = [n for n in nodes if n.location and n.location.country == country_filter]

        return jsonify({
            'success': True,
            'count': len(nodes),
            'data': [n.to_dict() for n in nodes]
        })

    except Exception as e:
        logger.error(f"Error listing nodes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/nodes', methods=['POST'])
def create_node():
    """
    Add a new node to the supply chain network.

    Body:
        node_type: Type (supplier, warehouse, distribution_center, plant, customer)
        name: Node name
        location: Location data (latitude, longitude, country, city)
        capacity: Capacity data
        lead_time_days: Lead time in days

    Returns:
        Created node
    """
    try:
        from services.digital_twin import (
            get_supply_chain_twin_service,
            SupplyChainNode,
            NodeType,
            NodeStatus,
            GeoLocation
        )

        data = request.get_json()

        if not data or 'node_type' not in data or 'name' not in data:
            return jsonify({
                'success': False,
                'error': 'node_type and name required'
            }), 400

        # Parse location
        location = None
        if 'location' in data:
            loc = data['location']
            location = GeoLocation(
                latitude=loc.get('latitude', 0),
                longitude=loc.get('longitude', 0),
                country=loc.get('country'),
                city=loc.get('city'),
                address=loc.get('address')
            )

        node = SupplyChainNode(
            id=str(uuid.uuid4()),
            node_id=data.get('node_id', f"node-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"),
            name=data['name'],
            node_type=NodeType(data['node_type']),
            status=NodeStatus.ACTIVE,
            location=location,
            capacity=data.get('capacity', {}),
            lead_time_days=data.get('lead_time_days', 0)
        )

        service = get_supply_chain_twin_service()
        created = service.add_node(node)

        return jsonify({
            'success': True,
            'data': created.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error creating node: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@supply_chain_twin_bp.route('/nodes/<node_id>', methods=['GET'])
def get_node(node_id: str):
    """
    Get node details.

    Path Parameters:
        node_id: Node identifier

    Returns:
        Node details with connections
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        node = service.get_node(node_id)

        if not node:
            return jsonify({
                'success': False,
                'error': 'Node not found'
            }), 404

        # Get connections
        upstream = service.get_upstream_nodes(node_id)
        downstream = service.get_downstream_nodes(node_id)

        return jsonify({
            'success': True,
            'data': {
                'node': node.to_dict(),
                'upstream': [n.to_dict() for n in upstream],
                'downstream': [n.to_dict() for n in downstream]
            }
        })

    except Exception as e:
        logger.error(f"Error getting node: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/nodes/<node_id>', methods=['PUT'])
def update_node(node_id: str):
    """
    Update a node.

    Path Parameters:
        node_id: Node identifier

    Body:
        Any node properties to update

    Returns:
        Updated node
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        data = request.get_json()

        service = get_supply_chain_twin_service()
        updated = service.update_node(node_id, data)

        if not updated:
            return jsonify({
                'success': False,
                'error': 'Node not found'
            }), 404

        return jsonify({
            'success': True,
            'data': updated.to_dict()
        })

    except Exception as e:
        logger.error(f"Error updating node: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@supply_chain_twin_bp.route('/nodes/<node_id>/status', methods=['PUT'])
def update_node_status(node_id: str):
    """
    Update node status.

    Path Parameters:
        node_id: Node identifier

    Body:
        status: New status (active, at_risk, disrupted, offline)
        reason: Reason for status change

    Returns:
        Updated node
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service, NodeStatus

        data = request.get_json()

        if not data or 'status' not in data:
            return jsonify({
                'success': False,
                'error': 'status required'
            }), 400

        service = get_supply_chain_twin_service()
        updated = service.update_node_status(
            node_id=node_id,
            status=NodeStatus(data['status']),
            reason=data.get('reason')
        )

        return jsonify({
            'success': True,
            'data': updated.to_dict()
        })

    except Exception as e:
        logger.error(f"Error updating status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ================== Edge Management ==================

@supply_chain_twin_bp.route('/edges', methods=['GET'])
def list_edges():
    """
    List all supply chain edges (connections).

    Query Parameters:
        transport_mode: Filter by transport mode
        source_id: Filter by source node
        target_id: Filter by target node

    Returns:
        List of edges
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()

        transport_mode = request.args.get('transport_mode')
        source_id = request.args.get('source_id')
        target_id = request.args.get('target_id')

        edges = service.get_all_edges()

        if transport_mode:
            edges = [e for e in edges if e.transport_mode.value == transport_mode]
        if source_id:
            edges = [e for e in edges if e.source_id == source_id]
        if target_id:
            edges = [e for e in edges if e.target_id == target_id]

        return jsonify({
            'success': True,
            'count': len(edges),
            'data': [e.to_dict() for e in edges]
        })

    except Exception as e:
        logger.error(f"Error listing edges: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/edges', methods=['POST'])
def create_edge():
    """
    Create a new edge between nodes.

    Body:
        source_id: Source node ID
        target_id: Target node ID
        transport_mode: Transport mode (road, rail, air, sea, multimodal)
        lead_time_days: Transit time in days
        cost_per_unit: Cost per unit
        capacity_per_day: Daily capacity

    Returns:
        Created edge
    """
    try:
        from services.digital_twin import (
            get_supply_chain_twin_service,
            SupplyChainEdge,
            TransportMode
        )

        data = request.get_json()

        if not data or 'source_id' not in data or 'target_id' not in data:
            return jsonify({
                'success': False,
                'error': 'source_id and target_id required'
            }), 400

        edge = SupplyChainEdge(
            id=str(uuid.uuid4()),
            source_id=data['source_id'],
            target_id=data['target_id'],
            transport_mode=TransportMode(data.get('transport_mode', 'road')),
            distance_km=data.get('distance_km', 0),
            transit_time_hours=data.get('lead_time_days', 1) * 24,
            cost_per_unit=data.get('cost_per_unit'),
            capacity_per_day=data.get('capacity_per_day'),
            carbon_per_unit_kg=data.get('carbon_footprint_kg')
        )

        service = get_supply_chain_twin_service()
        created = service.add_edge(edge)

        return jsonify({
            'success': True,
            'data': created.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error creating edge: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ================== Disruption Simulation ==================

@supply_chain_twin_bp.route('/simulate/disruption', methods=['POST'])
def simulate_disruption():
    """
    Simulate supply chain disruption.

    Body:
        disruption_type: Type (supplier_failure, logistics_delay, demand_spike, natural_disaster, geopolitical)
        affected_nodes: List of affected node IDs
        severity: Severity (0-1)
        duration_days: Duration in days
        simulation_horizon_days: How far to simulate

    Returns:
        Simulation results with impact analysis
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        data = request.get_json()

        if not data or 'disruption_type' not in data or 'affected_nodes' not in data:
            return jsonify({
                'success': False,
                'error': 'disruption_type and affected_nodes required'
            }), 400

        service = get_supply_chain_twin_service()

        result = service.simulate_disruption(
            disruption_type=data['disruption_type'],
            affected_nodes=data['affected_nodes'],
            severity=data.get('severity', 0.5),
            duration_days=data.get('duration_days', 7),
            horizon_days=data.get('simulation_horizon_days', 30)
        )

        return jsonify({
            'success': True,
            'data': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Error simulating disruption: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@supply_chain_twin_bp.route('/simulate/scenarios', methods=['GET'])
def list_simulation_scenarios():
    """
    List saved disruption scenarios.

    Returns:
        List of scenarios
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        scenarios = service.get_scenarios()

        return jsonify({
            'success': True,
            'count': len(scenarios),
            'data': [s.to_dict() for s in scenarios]
        })

    except Exception as e:
        logger.error(f"Error listing scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/simulate/scenarios', methods=['POST'])
def save_simulation_scenario():
    """
    Save a disruption scenario for reuse.

    Body:
        name: Scenario name
        description: Description
        disruption_config: Disruption configuration

    Returns:
        Saved scenario
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service, DisruptionScenario

        data = request.get_json()

        if not data or 'name' not in data:
            return jsonify({
                'success': False,
                'error': 'name required'
            }), 400

        scenario = DisruptionScenario(
            id=str(uuid.uuid4()),
            name=data['name'],
            description=data.get('description', ''),
            disruption_type=data.get('disruption_type'),
            affected_nodes=data.get('affected_nodes', []),
            severity=data.get('severity', 0.5),
            duration_days=data.get('duration_days', 7)
        )

        service = get_supply_chain_twin_service()
        saved = service.save_scenario(scenario)

        return jsonify({
            'success': True,
            'data': saved.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error saving scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ================== Risk Analysis ==================

@supply_chain_twin_bp.route('/risk/propagation', methods=['GET'])
def analyze_risk_propagation():
    """
    Analyze how risks propagate through supply chain.

    Query Parameters:
        source_node_id: Node where risk originates
        risk_type: Type of risk

    Returns:
        Risk propagation analysis
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        source_node_id = request.args.get('source_node_id')
        risk_type = request.args.get('risk_type')

        if not source_node_id:
            return jsonify({
                'success': False,
                'error': 'source_node_id required'
            }), 400

        service = get_supply_chain_twin_service()
        analysis = service.analyze_risk_propagation(
            source_node_id=source_node_id,
            risk_type=risk_type
        )

        return jsonify({
            'success': True,
            'data': analysis
        })

    except Exception as e:
        logger.error(f"Error analyzing risk: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/risk/scores', methods=['GET'])
def get_risk_scores():
    """
    Get risk scores for all nodes.

    Returns:
        Risk scores with contributing factors
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        scores = service.get_risk_scores()

        return jsonify({
            'success': True,
            'data': scores
        })

    except Exception as e:
        logger.error(f"Error getting risk scores: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/risk/bottlenecks', methods=['GET'])
def identify_bottlenecks():
    """
    Identify bottleneck nodes in the supply chain.

    Returns:
        List of bottleneck nodes with impact scores
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        bottlenecks = service.identify_bottlenecks()

        return jsonify({
            'success': True,
            'count': len(bottlenecks),
            'data': bottlenecks
        })

    except Exception as e:
        logger.error(f"Error identifying bottlenecks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Material Flow ==================

@supply_chain_twin_bp.route('/flow/visualize', methods=['GET'])
def get_material_flow():
    """
    Get material flow visualization data.

    Query Parameters:
        material_id: Filter by material
        timeframe: Time period (1d, 7d, 30d)

    Returns:
        Flow visualization data for Unity
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        material_id = request.args.get('material_id')
        timeframe = request.args.get('timeframe', '7d')

        service = get_supply_chain_twin_service()
        flow_data = service.get_material_flow(
            material_id=material_id,
            timeframe=timeframe
        )

        return jsonify({
            'success': True,
            'data': flow_data
        })

    except Exception as e:
        logger.error(f"Error getting flow data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/flow/in-transit', methods=['GET'])
def get_in_transit():
    """
    Get materials currently in transit.

    Returns:
        List of in-transit shipments
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        shipments = service.get_in_transit()

        return jsonify({
            'success': True,
            'count': len(shipments),
            'data': [s.to_dict() for s in shipments]
        })

    except Exception as e:
        logger.error(f"Error getting in-transit: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Inventory ==================

@supply_chain_twin_bp.route('/inventory', methods=['GET'])
def get_inventory_levels():
    """
    Get inventory levels across the network.

    Query Parameters:
        node_id: Filter by node
        material_id: Filter by material
        below_safety: Only show items below safety stock

    Returns:
        Inventory levels
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()

        node_id = request.args.get('node_id')
        material_id = request.args.get('material_id')
        below_safety = request.args.get('below_safety', 'false').lower() == 'true'

        inventory = service.get_inventory_levels(
            node_id=node_id,
            material_id=material_id,
            below_safety_only=below_safety
        )

        return jsonify({
            'success': True,
            'data': inventory
        })

    except Exception as e:
        logger.error(f"Error getting inventory: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@supply_chain_twin_bp.route('/inventory/forecast', methods=['GET'])
def forecast_inventory():
    """
    Forecast inventory levels.

    Query Parameters:
        node_id: Node to forecast
        material_id: Material to forecast
        horizon_days: Forecast horizon

    Returns:
        Inventory forecast
    """
    try:
        from services.digital_twin import get_supply_chain_twin_service

        node_id = request.args.get('node_id')
        material_id = request.args.get('material_id')
        horizon_days = int(request.args.get('horizon_days', 30))

        if not node_id or not material_id:
            return jsonify({
                'success': False,
                'error': 'node_id and material_id required'
            }), 400

        service = get_supply_chain_twin_service()
        forecast = service.forecast_inventory(
            node_id=node_id,
            material_id=material_id,
            horizon_days=horizon_days
        )

        return jsonify({
            'success': True,
            'data': forecast
        })

    except Exception as e:
        logger.error(f"Error forecasting inventory: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


__all__ = ['supply_chain_twin_bp']
