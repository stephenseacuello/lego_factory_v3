"""
OPC UA Integration API Routes
REST API endpoints for OPC UA server/client operations.
Part of Feature 1.5: OPC UA Integration (HIGH PRIORITY)
"""

import logging
from flask import Blueprint, jsonify, request
from typing import Dict

logger = logging.getLogger(__name__)

# Global service reference
opcua_service = None


def init_opcua_routes(app, service):
    """
    Initialize OPC UA routes with service dependency.

    Args:
        app: Flask application instance
        service: OPCUAService instance
    """
    global opcua_service
    opcua_service = service

    bp = create_opcua_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/opcua')
    logger.info("[OPCUA] Routes initialized")


def create_opcua_blueprint() -> Blueprint:
    """Create and configure OPC UA blueprint"""
    bp = Blueprint('opcua', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = opcua_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'opcua',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[OPCUA] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/server', methods=['POST'])
    def create_server():
        """
        Create and configure OPC UA server.

        Request Body (optional):
        {
            "port": 4840
        }

        Returns:
            201: Server created
            500: Server error
        """
        try:
            data = request.get_json() or {}
            port = data.get('port', 4840)

            server_info = opcua_service.create_server(port=port)

            if 'error' in server_info:
                return jsonify(server_info), 500

            return jsonify({
                'success': True,
                'message': 'OPC UA server configured',
                'server': server_info
            }), 201

        except Exception as e:
            logger.error(f"[OPCUA] Error creating server: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/nodes', methods=['POST'])
    def add_node():
        """
        Add node to OPC UA address space.

        Request Body:
        {
            "node_id": "ns=2;s=Machine.Custom",
            "name": "Custom Node",
            "type": "Variable",
            "datatype": "Float",
            "value": 0.0,
            "unit": "mm",
            "writable": true
        }

        Returns:
            201: Node added
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'node_id' not in data:
                return jsonify({'error': 'node_id required'}), 400

            node_id = data.pop('node_id')
            success = opcua_service.add_node(node_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Node added',
                    'node_id': node_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to add node'
                }), 500

        except Exception as e:
            logger.error(f"[OPCUA] Error adding node: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/nodes/<path:node_id>', methods=['GET'])
    def read_node(node_id: str):
        """
        Read value from OPC UA node.

        Returns:
            200: Node value
            404: Node not found
            500: Server error
        """
        try:
            node_data = opcua_service.read_node(node_id)

            if node_data:
                return jsonify({
                    'success': True,
                    'node': node_data
                }), 200
            else:
                return jsonify({
                    'error': f'Node not found: {node_id}'
                }), 404

        except Exception as e:
            logger.error(f"[OPCUA] Error reading node: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/nodes/<path:node_id>', methods=['PUT'])
    def write_node(node_id: str):
        """
        Write value to OPC UA node.

        Request Body:
        {
            "value": 42.0
        }

        Returns:
            200: Value written
            400: Invalid request
            404: Node not found
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'value' not in data:
                return jsonify({'error': 'value required'}), 400

            value = data['value']
            success = opcua_service.write_node(node_id, value)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Value written',
                    'node_id': node_id,
                    'value': value
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to write value (node may be read-only or not found)'
                }), 404

        except Exception as e:
            logger.error(f"[OPCUA] Error writing node: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/browse', methods=['GET'])
    def browse_nodes():
        """
        Browse OPC UA address space.

        Query Parameters:
            starting_node: Starting node ID (default: "ns=2;s=Machine")

        Returns:
            200: List of nodes
            500: Server error
        """
        try:
            starting_node = request.args.get('starting_node', 'ns=2;s=Machine')

            nodes = opcua_service.browse_nodes(starting_node)

            return jsonify({
                'starting_node': starting_node,
                'count': len(nodes),
                'nodes': nodes
            }), 200

        except Exception as e:
            logger.error(f"[OPCUA] Error browsing nodes: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/subscriptions', methods=['POST'])
    def create_subscription():
        """
        Create subscription for node value changes.

        Request Body:
        {
            "client_id": "unity_client_1",
            "node_ids": ["ns=2;s=Machine.Position.X", "ns=2;s=Machine.Position.Y"],
            "publishing_interval": 100
        }

        Returns:
            201: Subscription created
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'client_id' not in data or 'node_ids' not in data:
                return jsonify({'error': 'client_id and node_ids required'}), 400

            client_id = data['client_id']
            node_ids = data['node_ids']
            publishing_interval = data.get('publishing_interval', 100)

            subscription = opcua_service.create_subscription(
                client_id,
                node_ids,
                publishing_interval
            )

            if 'error' in subscription:
                return jsonify(subscription), 500

            return jsonify({
                'success': True,
                'message': 'Subscription created',
                'subscription': subscription
            }), 201

        except Exception as e:
            logger.error(f"[OPCUA] Error creating subscription: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/subscriptions/<subscription_id>', methods=['DELETE'])
    def delete_subscription(subscription_id: str):
        """
        Delete subscription.

        Returns:
            200: Subscription deleted
            404: Subscription not found
            500: Server error
        """
        try:
            success = opcua_service.delete_subscription(subscription_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Subscription deleted',
                    'subscription_id': subscription_id
                }), 200
            else:
                return jsonify({
                    'error': f'Subscription not found: {subscription_id}'
                }), 404

        except Exception as e:
            logger.error(f"[OPCUA] Error deleting subscription: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/client/connect', methods=['POST'])
    def connect_client():
        """
        Connect OPC UA client to external server.

        Request Body:
        {
            "endpoint": "opc.tcp://remote-server:4840",
            "username": "admin",
            "password": "password"
        }

        Returns:
            200: Client connected
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'endpoint' not in data:
                return jsonify({'error': 'endpoint required'}), 400

            endpoint = data['endpoint']
            username = data.get('username', '')
            password = data.get('password', '')

            client_info = opcua_service.connect_client(endpoint, username, password)

            if 'error' in client_info:
                return jsonify(client_info), 500

            return jsonify({
                'success': True,
                'message': 'Client connected',
                'client': client_info
            }), 200

        except Exception as e:
            logger.error(f"[OPCUA] Error connecting client: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/client/<client_id>/disconnect', methods=['POST'])
    def disconnect_client(client_id: str):
        """
        Disconnect OPC UA client.

        Returns:
            200: Client disconnected
            404: Client not found
            500: Server error
        """
        try:
            success = opcua_service.disconnect_client(client_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Client disconnected',
                    'client_id': client_id
                }), 200
            else:
                return jsonify({
                    'error': f'Client not found: {client_id}'
                }), 404

        except Exception as e:
            logger.error(f"[OPCUA] Error disconnecting client: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get OPC UA service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = opcua_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[OPCUA] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'OPC UA Integration API',
    'version': '1.0.0',
    'description': 'REST API for OPC UA industrial communication',
    'base_path': '/api/v1/opcua',
    'protocol': 'OPC UA (Unified Architecture)',
    'endpoints': [
        {
            'path': '/health',
            'method': 'GET',
            'description': 'Health check endpoint'
        },
        {
            'path': '/server',
            'method': 'POST',
            'description': 'Create and configure OPC UA server'
        },
        {
            'path': '/nodes',
            'method': 'POST',
            'description': 'Add node to address space'
        },
        {
            'path': '/nodes/<node_id>',
            'method': 'GET',
            'description': 'Read node value'
        },
        {
            'path': '/nodes/<node_id>',
            'method': 'PUT',
            'description': 'Write node value'
        },
        {
            'path': '/browse',
            'method': 'GET',
            'description': 'Browse OPC UA address space'
        },
        {
            'path': '/subscriptions',
            'method': 'POST',
            'description': 'Create subscription'
        },
        {
            'path': '/subscriptions/<subscription_id>',
            'method': 'DELETE',
            'description': 'Delete subscription'
        },
        {
            'path': '/client/connect',
            'method': 'POST',
            'description': 'Connect OPC UA client'
        },
        {
            'path': '/client/<client_id>/disconnect',
            'method': 'POST',
            'description': 'Disconnect OPC UA client'
        },
        {
            'path': '/statistics',
            'method': 'GET',
            'description': 'Get service statistics'
        }
    ]
}
