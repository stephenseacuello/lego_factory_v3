"""
LEGO Factory v3 - Recipe API Routes
===================================
REST API for ISA-88 recipe management.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
import logging

from config.database import get_db_session

logger = logging.getLogger(__name__)

recipes_bp = Blueprint('recipes', __name__, url_prefix='/recipes')


def get_recipe_service(session):
    """Get recipe service - placeholder for full implementation"""
    from models.scada.recipes import MasterRecipe, ControlRecipe, RecipeApproval, RecipeParameter
    return RecipeService(session)


class RecipeService:
    """ISA-88 Recipe Management Service"""

    def __init__(self, session):
        self.session = session

    def get_master_recipes(self, recipe_type=None, status=None, search=None,
                           limit=100, offset=0):
        """Get master recipes with filtering"""
        from models.scada.recipes import MasterRecipe, RecipeType, RecipeStatus

        query = self.session.query(MasterRecipe).filter(MasterRecipe.is_deleted == False)

        if recipe_type:
            query = query.filter(MasterRecipe.recipe_type == RecipeType(recipe_type))
        if status:
            query = query.filter(MasterRecipe.status == RecipeStatus(status))
        if search:
            query = query.filter(MasterRecipe.name.ilike(f'%{search}%'))

        recipes = query.order_by(MasterRecipe.name).offset(offset).limit(limit).all()
        return [r.to_dict() for r in recipes]

    def get_master_recipe(self, recipe_id):
        """Get master recipe by ID"""
        from models.scada.recipes import MasterRecipe
        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id
        ).first()
        return recipe.to_dict() if recipe else None

    def create_master_recipe(self, data):
        """Create a new master recipe"""
        from models.scada.recipes import MasterRecipe, RecipeType, RecipeStatus

        recipe = MasterRecipe(
            recipe_id=data['recipe_id'],
            name=data['name'],
            description=data.get('description'),
            recipe_type=RecipeType(data.get('recipe_type', 'machining')),
            version=data.get('version', '1.0'),
            status=RecipeStatus.draft,
            product_id=data.get('product_id'),
            gcode_content=data.get('gcode_content'),
            parameters=data.get('parameters', {}),
            equipment_requirements=data.get('equipment_requirements', {}),
            created_by=data.get('created_by', 'system')
        )
        self.session.add(recipe)
        self.session.flush()
        return recipe.to_dict()

    def update_master_recipe(self, recipe_id, data):
        """Update master recipe"""
        from models.scada.recipes import MasterRecipe

        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id
        ).first()
        if not recipe:
            return None

        for key, value in data.items():
            if hasattr(recipe, key) and key not in ('id', 'recipe_id', 'created_at'):
                setattr(recipe, key, value)

        recipe.updated_at = datetime.utcnow()
        self.session.flush()
        return recipe.to_dict()

    def approve_recipe(self, recipe_id, user_id, comments=None):
        """Submit recipe for approval"""
        from models.scada.recipes import MasterRecipe, RecipeApproval, ApprovalStatus, RecipeStatus

        recipe = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == recipe_id
        ).first()
        if not recipe:
            return None

        approval = RecipeApproval(
            recipe_id=recipe_id,
            approver_id=user_id,
            status=ApprovalStatus.approved,
            comments=comments,
            approved_at=datetime.utcnow()
        )
        self.session.add(approval)

        recipe.status = RecipeStatus.approved
        recipe.approved_by = user_id
        recipe.approved_at = datetime.utcnow()
        self.session.flush()

        return recipe.to_dict()

    def create_control_recipe(self, master_recipe_id, work_order_id, data=None):
        """Create a control recipe instance from master recipe"""
        from models.scada.recipes import MasterRecipe, ControlRecipe

        master = self.session.query(MasterRecipe).filter(
            MasterRecipe.recipe_id == master_recipe_id
        ).first()
        if not master:
            return None

        data = data or {}
        control = ControlRecipe(
            master_recipe_id=master_recipe_id,
            work_order_id=work_order_id,
            machine_id=data.get('machine_id'),
            parameters=data.get('parameters', master.parameters.copy()),
            runtime_parameters=data.get('runtime_parameters', {})
        )
        self.session.add(control)
        self.session.flush()
        return control.to_dict()

    def get_control_recipes(self, work_order_id=None, machine_id=None, limit=100):
        """Get control recipes"""
        from models.scada.recipes import ControlRecipe

        query = self.session.query(ControlRecipe)

        if work_order_id:
            query = query.filter(ControlRecipe.work_order_id == work_order_id)
        if machine_id:
            query = query.filter(ControlRecipe.machine_id == machine_id)

        recipes = query.order_by(ControlRecipe.created_at.desc()).limit(limit).all()
        return [r.to_dict() for r in recipes]


@recipes_bp.route('/master', methods=['GET'])
@jwt_required(optional=True)
def list_master_recipes():
    """Get all master recipes with filtering"""
    try:
        recipe_type = request.args.get('type')
        status = request.args.get('status')
        search = request.args.get('search')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        with get_db_session() as session:
            service = get_recipe_service(session)
            recipes = service.get_master_recipes(
                recipe_type=recipe_type,
                status=status,
                search=search,
                limit=limit,
                offset=offset
            )
            return jsonify({'recipes': recipes, 'count': len(recipes)})
    except Exception as e:
        logger.error(f"Error listing master recipes: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/master/<recipe_id>', methods=['GET'])
@jwt_required()
def get_master_recipe(recipe_id: str):
    """Get master recipe by ID"""
    try:
        with get_db_session() as session:
            service = get_recipe_service(session)
            recipe = service.get_master_recipe(recipe_id)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404
            return jsonify(recipe)
    except Exception as e:
        logger.error(f"Error getting master recipe {recipe_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/master', methods=['POST'])
@jwt_required()
def create_master_recipe():
    """Create a new master recipe"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required = ['recipe_id', 'name']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'error': f'Missing required fields: {missing}'}), 400

        with get_db_session() as session:
            service = get_recipe_service(session)
            recipe = service.create_master_recipe(data)
            session.commit()
            return jsonify(recipe), 201
    except Exception as e:
        logger.error(f"Error creating master recipe: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/master/<recipe_id>', methods=['PUT'])
@jwt_required()
def update_master_recipe(recipe_id: str):
    """Update master recipe"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        with get_db_session() as session:
            service = get_recipe_service(session)
            recipe = service.update_master_recipe(recipe_id, data)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404
            session.commit()
            return jsonify(recipe)
    except Exception as e:
        logger.error(f"Error updating master recipe {recipe_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/master/<recipe_id>/approve', methods=['POST'])
@jwt_required()
def approve_master_recipe(recipe_id: str):
    """Approve a master recipe"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'system')
        comments = data.get('comments')

        with get_db_session() as session:
            service = get_recipe_service(session)
            recipe = service.approve_recipe(recipe_id, user_id, comments)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404
            session.commit()
            return jsonify(recipe)
    except Exception as e:
        logger.error(f"Error approving master recipe {recipe_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/control', methods=['GET'])
@jwt_required()
def list_control_recipes():
    """Get control recipes"""
    try:
        work_order_id = request.args.get('work_order_id')
        machine_id = request.args.get('machine_id')
        limit = request.args.get('limit', 100, type=int)

        with get_db_session() as session:
            service = get_recipe_service(session)
            recipes = service.get_control_recipes(
                work_order_id=work_order_id,
                machine_id=machine_id,
                limit=limit
            )
            return jsonify({'recipes': recipes, 'count': len(recipes)})
    except Exception as e:
        logger.error(f"Error listing control recipes: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/control', methods=['POST'])
@jwt_required()
def create_control_recipe():
    """Create a control recipe from master recipe"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required = ['master_recipe_id', 'work_order_id']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'error': f'Missing required fields: {missing}'}), 400

        with get_db_session() as session:
            service = get_recipe_service(session)
            recipe = service.create_control_recipe(
                data['master_recipe_id'],
                data['work_order_id'],
                data
            )
            if not recipe:
                return jsonify({'error': 'Master recipe not found'}), 404
            session.commit()
            return jsonify(recipe), 201
    except Exception as e:
        logger.error(f"Error creating control recipe: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@recipes_bp.route('/types', methods=['GET'])
@jwt_required()
def get_recipe_types():
    """Get available recipe types and statuses"""
    from models.scada.recipes import RecipeType, RecipeStatus, ApprovalStatus

    return jsonify({
        'recipe_types': [t.value for t in RecipeType],
        'recipe_statuses': [s.value for s in RecipeStatus],
        'approval_statuses': [s.value for s in ApprovalStatus]
    })
