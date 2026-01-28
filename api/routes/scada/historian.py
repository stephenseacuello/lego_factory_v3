"""
LEGO Factory v3 - Historian API Routes
======================================
REST API for time-series data storage and retrieval.
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
import tempfile
import os
import logging

from services.scada.historian.historian_service import (
    historian_writer,
    HistorianReader,
    HistorianExporter,
    start_historian,
    stop_historian,
    write_to_historian,
    read_from_historian,
    get_historian_stats
)

logger = logging.getLogger(__name__)

historian_bp = Blueprint('historian', __name__, url_prefix='/historian')


@historian_bp.route('/write', methods=['POST'])
@jwt_required()
def write_value():
    """Write a single value to the historian"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required = ['tag_id', 'value']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'error': f'Missing required fields: {missing}'}), 400

        timestamp = None
        if 'timestamp' in data:
            timestamp = datetime.fromisoformat(data['timestamp'])

        write_to_historian(
            tag_id=data['tag_id'],
            value=data['value'],
            timestamp=timestamp,
            quality=data.get('quality', 192),
            source=data.get('source')
        )
        return jsonify({'message': 'Value written', 'tag_id': data['tag_id']})
    except Exception as e:
        logger.error(f"Error writing to historian: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/write/batch', methods=['POST'])
@jwt_required()
def write_batch():
    """Write multiple values to the historian"""
    try:
        data = request.get_json()
        if not data or 'values' not in data:
            return jsonify({'error': 'No values provided'}), 400

        values = data['values']
        compress = data.get('compress', True)

        historian_writer.write_batch(values, compress)
        return jsonify({'message': 'Values written', 'count': len(values)})
    except Exception as e:
        logger.error(f"Error writing batch to historian: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/raw', methods=['GET'])
@jwt_required()
def get_raw_data():
    """Get raw historical data"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')
        limit = request.args.get('limit', 100000, type=int)

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        reader = HistorianReader()
        df = reader.get_raw(tag_ids, start, end, limit)

        # Convert to JSON-serializable format
        result = df.to_dict(orient='records')
        for row in result:
            if 'time' in row and hasattr(row['time'], 'isoformat'):
                row['time'] = row['time'].isoformat()

        return jsonify({
            'data': result,
            'count': len(result),
            'start': start.isoformat(),
            'end': end.isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting raw data: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/aggregated', methods=['GET'])
@jwt_required()
def get_aggregated_data():
    """Get aggregated historical data using TimescaleDB time_bucket"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')
        bucket = request.args.get('bucket', '1 minute')
        agg = request.args.get('agg', 'avg')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        reader = HistorianReader()
        df = reader.get_aggregated(tag_ids, start, end, bucket, agg)

        # Convert to JSON-serializable format
        result = df.to_dict(orient='records')
        for row in result:
            if 'bucket' in row and hasattr(row['bucket'], 'isoformat'):
                row['bucket'] = row['bucket'].isoformat()

        return jsonify({
            'data': result,
            'count': len(result),
            'bucket': bucket,
            'aggregation': agg
        })
    except Exception as e:
        logger.error(f"Error getting aggregated data: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/trend', methods=['GET'])
@jwt_required()
def get_trend_data():
    """Get downsampled trend data for visualization"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')
        max_points = request.args.get('max_points', 1000, type=int)

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        reader = HistorianReader()
        df = reader.get_trend(tag_ids, start, end, max_points)

        # Convert to JSON-serializable format
        result = df.to_dict(orient='records')
        for row in result:
            if 'bucket' in row and hasattr(row['bucket'], 'isoformat'):
                row['bucket'] = row['bucket'].isoformat()

        return jsonify({
            'data': result,
            'count': len(result),
            'max_points': max_points
        })
    except Exception as e:
        logger.error(f"Error getting trend data: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/statistics', methods=['GET'])
@jwt_required()
def get_statistics():
    """Get statistics for tags over a time period"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=24)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        reader = HistorianReader()
        df = reader.get_statistics(tag_ids, start, end)

        # Convert to JSON-serializable format
        result = df.to_dict(orient='records')
        for row in result:
            for key in ['first_time', 'last_time']:
                if key in row and hasattr(row[key], 'isoformat'):
                    row[key] = row[key].isoformat()

        return jsonify({
            'statistics': result,
            'count': len(result)
        })
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/export/csv', methods=['GET'])
@jwt_required()
def export_csv():
    """Export historical data to CSV"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')
        aggregation = request.args.get('aggregation')
        bucket = request.args.get('bucket', '1 minute')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)

        exporter = HistorianExporter()
        exporter.export_csv(tag_ids, start, end, path, aggregation, bucket)

        return send_file(
            path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'historian_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/export/parquet', methods=['GET'])
@jwt_required()
def export_parquet():
    """Export historical data to Parquet"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.parquet')
        os.close(fd)

        exporter = HistorianExporter()
        exporter.export_parquet(tag_ids, start, end, path)

        return send_file(
            path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=f'historian_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.parquet'
        )
    except Exception as e:
        logger.error(f"Error exporting Parquet: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/export/npz', methods=['GET'])
@jwt_required()
def export_npz():
    """Export historical data to NPZ format for ML training"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        start_str = request.args.get('start')
        end_str = request.args.get('end')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.npz')
        os.close(fd)

        exporter = HistorianExporter()
        exporter.export_npz(tag_ids, start, end, path)

        return send_file(
            path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=f'historian_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.npz'
        )
    except Exception as e:
        logger.error(f"Error exporting NPZ: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/start', methods=['POST'])
@jwt_required()
def start_writer():
    """Start the historian writer"""
    try:
        start_historian()
        return jsonify({'message': 'Historian writer started'})
    except Exception as e:
        logger.error(f"Error starting historian: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/stop', methods=['POST'])
@jwt_required()
def stop_writer():
    """Stop the historian writer"""
    try:
        stop_historian()
        return jsonify({'message': 'Historian writer stopped'})
    except Exception as e:
        logger.error(f"Error stopping historian: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """Get historian writer statistics"""
    try:
        stats = get_historian_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting historian stats: {e}")
        return jsonify({'error': str(e)}), 500


@historian_bp.route('/aggregations', methods=['GET'])
@jwt_required()
def get_aggregation_types():
    """Get available aggregation types"""
    return jsonify({
        'aggregations': ['avg', 'min', 'max', 'sum', 'count', 'first', 'last'],
        'default_buckets': ['1 second', '1 minute', '5 minutes', '1 hour', '1 day']
    })
