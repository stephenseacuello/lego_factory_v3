"""
LEGO Factory v3 - Tag API Routes
================================
REST API for tag management and real-time values with Pydantic validation.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
import asyncio
import logging

from services.scada.tag_management.tag_service import (
    tag_cache,
    get_tag_service,
    read_tag_value,
    read_tag_values,
    write_tag_value
)
from config.database import get_db_session

# Import Pydantic schemas and validation utilities
from api.schemas import (
    TagCreate,
    TagUpdate,
    TagValueWrite,
    TagValueBulkWrite,
    TagGroupCreate,
    TagBulkCreate,
    TagImportRequest,
    TagScaleRequest,
    TagListParams,
)
from api.utils.validation import validate_request, validate_query_params, validate_path_param

logger = logging.getLogger(__name__)

tags_bp = Blueprint('tags', __name__, url_prefix='/tags')


def run_async(coro):
    """Helper to run async functions in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tags_bp.route('', methods=['GET'])
@jwt_required(optional=True)
def list_tags():
    """Get all tags with filtering"""
    try:
        area = request.args.get('area')
        equipment = request.args.get('equipment')
        category = request.args.get('category')
        search = request.args.get('search')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        with get_db_session() as session:
            service = get_tag_service(session)
            tags = service.get_tags(
                area=area,
                equipment=equipment,
                category=category,
                search=search,
                limit=limit,
                offset=offset
            )
            return jsonify({'tags': tags, 'count': len(tags)})
    except Exception as e:
        logger.error(f"Error listing tags: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/<tag_id>', methods=['GET'])
@jwt_required()
def get_tag(tag_id: str):
    """Get tag by ID"""
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            tag = service.get_tag(tag_id)
            if not tag:
                return jsonify({'error': 'Tag not found'}), 404
            return jsonify(tag)
    except Exception as e:
        logger.error(f"Error getting tag {tag_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('', methods=['POST'])
@validate_request(TagCreate)
def create_tag(validated_data: TagCreate):
    """
    Create a new tag.

    Request body (validated by Pydantic):
        {
            "tag_id": "string (required, unique identifier)",
            "name": "string (required, 1-200 chars)",
            "data_type": "boolean|int16|int32|float32|... (default: float32)",
            "category": "analog_input|digital_output|... (default: analog_input)",
            "area": "string (optional)",
            "equipment": "string (optional)",
            "eng_units": "string (optional, e.g., 'degC', 'bar')",
            "eng_low": "float (optional, low engineering scale)",
            "eng_high": "float (optional, high engineering scale)",
            "historize": "boolean (default: true)",
            "scan_rate_ms": "integer (default: 1000, 10-3600000)"
        }

    Returns:
        201: Created tag
        400: Validation error with field details
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            tag = service.create_tag(validated_data.model_dump(exclude_none=True))
            session.commit()
            return jsonify(tag), 201
    except Exception as e:
        logger.error(f"Error creating tag: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/<tag_id>', methods=['PUT'])
@validate_path_param('tag_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]*$', max_length=100)
@validate_request(TagUpdate)
def update_tag(validated_data: TagUpdate, tag_id: str):
    """
    Update tag configuration.

    Path parameters:
        - tag_id: Tag identifier

    Request body (validated by Pydantic):
        {
            "name": "string (optional)",
            "description": "string (optional)",
            "eng_units": "string (optional)",
            "historize": "boolean (optional)",
            ...
        }

    Returns:
        200: Updated tag
        400: Validation error
        404: Tag not found
        500: Server error
    """
    try:
        update_data = validated_data.model_dump(exclude_none=True)
        if not update_data:
            return jsonify({'error': 'No data provided'}), 400

        with get_db_session() as session:
            service = get_tag_service(session)
            tag = service.update_tag(tag_id, update_data)
            if not tag:
                return jsonify({'error': 'Tag not found'}), 404
            session.commit()
            return jsonify(tag)
    except Exception as e:
        logger.error(f"Error updating tag {tag_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/<tag_id>', methods=['DELETE'])
@validate_path_param('tag_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]*$', max_length=100)
def delete_tag(tag_id: str):
    """
    Delete a tag (soft delete).

    Path parameters:
        - tag_id: Tag identifier (alphanumeric with underscores, dots, dashes)

    Returns:
        200: Tag deleted successfully
        404: Tag not found
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            success = service.delete_tag(tag_id)
            if not success:
                return jsonify({'error': 'Tag not found'}), 404
            session.commit()
            return jsonify({'message': 'Tag deleted'})
    except Exception as e:
        logger.error(f"Error deleting tag {tag_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/<tag_id>/value', methods=['GET'])
@jwt_required()
def get_tag_value(tag_id: str):
    """Get current tag value from cache"""
    try:
        value = run_async(read_tag_value(tag_id))
        if not value:
            return jsonify({'error': 'Tag value not found'}), 404
        return jsonify({
            'tag_id': value.tag_id,
            'tag_name': value.tag_name,
            'value': value.value,
            'quality': value.quality,
            'timestamp': value.timestamp.isoformat(),
            'eng_units': value.eng_units
        })
    except Exception as e:
        logger.error(f"Error getting tag value {tag_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/<tag_id>/value', methods=['PUT'])
@validate_path_param('tag_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]*$', max_length=100)
@validate_request(TagValueWrite)
def set_tag_value(validated_data: TagValueWrite, tag_id: str):
    """
    Write a value to a tag.

    Path parameters:
        - tag_id: Tag identifier

    Request body (validated by Pydantic):
        {
            "value": "any (required, type depends on tag)",
            "quality": "integer (optional, OPC quality code, default: 192)",
            "tag_name": "string (optional)",
            "eng_units": "string (optional)"
        }

    Returns:
        200: Value written successfully
        400: Validation error
        500: Write failed
    """
    try:
        run_async(write_tag_value(
            tag_id=tag_id,
            value=validated_data.value,
            quality=validated_data.quality,
            tag_name=validated_data.tag_name,
            eng_units=validated_data.eng_units
        ))
        return jsonify({'message': 'Value written', 'tag_id': tag_id})
    except Exception as e:
        logger.error(f"Error writing tag value {tag_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/values', methods=['GET'])
@jwt_required()
def get_tag_values():
    """Get multiple tag values"""
    try:
        tag_ids = request.args.getlist('tag_id')
        if not tag_ids:
            return jsonify({'error': 'No tag IDs provided'}), 400

        values = run_async(read_tag_values(tag_ids))
        result = {}
        for tag_id, value in values.items():
            result[tag_id] = {
                'tag_name': value.tag_name,
                'value': value.value,
                'quality': value.quality,
                'timestamp': value.timestamp.isoformat(),
                'eng_units': value.eng_units
            }
        return jsonify({'values': result, 'count': len(result)})
    except Exception as e:
        logger.error(f"Error getting tag values: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/values', methods=['PUT'])
@validate_request(TagValueBulkWrite)
def set_tag_values(validated_data: TagValueBulkWrite):
    """
    Write multiple tag values in bulk.

    Request body (validated by Pydantic):
        {
            "values": [
                {
                    "tag_id": "string (required)",
                    "value": "any (required)",
                    "quality": "integer (optional, default: 192)",
                    "tag_name": "string (optional)",
                    "eng_units": "string (optional)"
                },
                ...
            ]
        }

    Returns:
        200: Values written successfully
        400: Validation error
        500: Write failed
    """
    try:
        for item in validated_data.values:
            run_async(write_tag_value(
                tag_id=item.tag_id,
                value=item.value,
                quality=item.quality,
                tag_name=item.tag_name,
                eng_units=item.eng_units
            ))
        return jsonify({'message': 'Values written', 'count': len(validated_data.values)})
    except Exception as e:
        logger.error(f"Error writing tag values: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/groups', methods=['GET'])
@jwt_required()
def list_tag_groups():
    """Get tag groups"""
    try:
        parent_id = request.args.get('parent_id')

        with get_db_session() as session:
            service = get_tag_service(session)
            groups = service.get_tag_groups(parent_id)
            return jsonify({'groups': groups, 'count': len(groups)})
    except Exception as e:
        logger.error(f"Error listing tag groups: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/groups', methods=['POST'])
@validate_request(TagGroupCreate)
def create_tag_group(validated_data: TagGroupCreate):
    """
    Create a tag group.

    Request body (validated by Pydantic):
        {
            "name": "string (required, 1-100 chars)",
            "description": "string (optional, max 500 chars)",
            "parent_id": "string (optional, parent group ID)",
            "tag_ids": ["array of tag IDs to include (optional)"]
        }

    Returns:
        201: Created tag group
        400: Validation error
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            group = service.create_tag_group(
                name=validated_data.name,
                description=validated_data.description,
                parent_id=validated_data.parent_id,
                tag_ids=validated_data.tag_ids or []
            )
            session.commit()
            return jsonify(group), 201
    except Exception as e:
        logger.error(f"Error creating tag group: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/bulk', methods=['POST'])
@validate_request(TagBulkCreate)
def bulk_create_tags(validated_data: TagBulkCreate):
    """
    Create multiple tags at once.

    Request body (validated by Pydantic):
        {
            "tags": [
                {
                    "tag_id": "string (required)",
                    "name": "string (required)",
                    "data_type": "boolean|int16|float32|...",
                    "category": "analog_input|digital_output|...",
                    ...
                },
                ...
            ]
        }

    Returns:
        201: Created tags
        400: Validation error
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            tags_data = [tag.model_dump(exclude_none=True) for tag in validated_data.tags]
            tags = service.bulk_create_tags(tags_data)
            session.commit()
            return jsonify({'tags': tags, 'count': len(tags)}), 201
    except Exception as e:
        logger.error(f"Error bulk creating tags: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/export', methods=['GET'])
@jwt_required()
def export_tags():
    """Export tags to JSON"""
    try:
        area = request.args.get('area')

        with get_db_session() as session:
            service = get_tag_service(session)
            tags = service.export_tags(area)
            return jsonify({'tags': tags, 'count': len(tags)})
    except Exception as e:
        logger.error(f"Error exporting tags: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/import', methods=['POST'])
@validate_request(TagImportRequest)
def import_tags(validated_data: TagImportRequest):
    """
    Import tags from JSON.

    Request body (validated by Pydantic):
        {
            "tags": [
                {
                    "tag_id": "string (required)",
                    "name": "string (required)",
                    ...
                },
                ...
            ],
            "update_existing": "boolean (default: false)",
            "source": "string (optional, source system name)"
        }

    Returns:
        200: Import result with created/updated counts
        400: Validation error
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            tags_data = [tag.model_dump(exclude_none=True) for tag in validated_data.tags]
            result = service.import_tags(tags_data, validated_data.update_existing)
            session.commit()
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error importing tags: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@tags_bp.route('/types', methods=['GET'])
@jwt_required()
def get_tag_types():
    """Get available tag data types and categories"""
    from models.scada.tags import TagDataType, TagCategory, TagQuality

    return jsonify({
        'data_types': [t.value for t in TagDataType],
        'categories': [c.value for c in TagCategory],
        'quality_codes': {q.name: q.value for q in TagQuality}
    })


@tags_bp.route('/<tag_id>/scale', methods=['POST'])
@validate_path_param('tag_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_.-]*$', max_length=100)
@validate_request(TagScaleRequest)
def scale_tag_value(validated_data: TagScaleRequest, tag_id: str):
    """
    Convert raw value to engineering units.

    Path parameters:
        - tag_id: Tag identifier

    Request body (validated by Pydantic):
        {
            "raw_value": "number (required)",
            "raw_low": "number (optional, override raw low range)",
            "raw_high": "number (optional, override raw high range)"
        }

    Returns:
        200: Scaled engineering value
        400: Validation error
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_tag_service(session)
            eng_value = service.scale_value(tag_id, validated_data.raw_value)
            return jsonify({
                'tag_id': tag_id,
                'raw_value': validated_data.raw_value,
                'eng_value': eng_value
            })
    except Exception as e:
        logger.error(f"Error scaling tag value {tag_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500
