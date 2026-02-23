"""
LEGO Factory v3 - MES Recipe Service (Facade)
==============================================
Facade that wraps the SCADA RecipeService (ISA-88) and adapts its interface
to the simpler contract expected by the MES API routes.

The SCADA service deals with ISA-88 concepts (master/control recipes, approval
workflows, versioning, batch tracking). The MES routes need a thinner
interface focused on basic CRUD, status transitions, and recipe download.
"""

import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from services.scada.recipe_management.recipe_service import (
    RecipeService as ScadaRecipeService,
    RecipeNotFoundError,
    RecipeStateError,
    RecipeApprovalError,
)

logger = logging.getLogger(__name__)


class RecipeService:
    """
    MES-facing recipe service that delegates to the SCADA RecipeService.

    Adapts method signatures so the MES API routes can call simple methods
    without knowing about the full ISA-88 recipe model underneath.
    """

    def __init__(self, session: Session):
        self._scada = ScadaRecipeService(session)

    # ------------------------------------------------------------------
    # List / Query
    # ------------------------------------------------------------------

    def get_recipes(
        self,
        status: Optional[str] = None,
        product_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return a flat list of recipes, optionally filtered by status and/or
        product_id.  The MES routes expect a plain list (not a (list, count)
        tuple), so we unpack the result from the SCADA service.
        """
        filters: Dict[str, Any] = {}
        if status:
            filters['status'] = status
        if product_id:
            filters['product_id'] = product_id

        recipes, _total = self._scada.list_recipes(
            filters=filters,
            pagination={'limit': 500, 'offset': 0},
        )
        return recipes

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_recipe(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new master recipe from a flat data dict coming from the
        MES POST /recipes endpoint.

        The MES routes pass the full request JSON as *data*; we map that to
        the keyword arguments the SCADA service expects.
        """
        return self._scada.create_recipe(
            name=data.get('name', 'Untitled Recipe'),
            description=data.get('description'),
            recipe_type=data.get('recipe_type', 'master'),
            parameters=data.get('parameters'),
            procedure_steps=data.get('operations') or data.get('procedure_steps'),
            product_id=data.get('product_id'),
            machine_type=data.get('machine_type'),
            gcode_content=data.get('gcode_content'),
            materials=data.get('materials'),
            tools=data.get('tools'),
            quality_specs=data.get('quality_specs'),
            estimated_cycle_time_seconds=data.get('estimated_cycle_time_seconds'),
            created_by=data.get('created_by'),
        )

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single recipe by its recipe_id.

        Returns None instead of raising when the recipe is not found,
        because the MES routes check ``if not recipe:`` rather than
        catching exceptions.
        """
        try:
            return self._scada.get_recipe(recipe_id)
        except RecipeNotFoundError:
            return None

    def update_recipe(
        self,
        recipe_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing recipe.  Returns None when the recipe cannot be
        found rather than raising.
        """
        try:
            return self._scada.update_recipe(recipe_id, updates=data)
        except RecipeNotFoundError:
            return None

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------

    def submit_for_approval(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Submit a draft recipe for approval.  Returns None when the recipe
        is not found or is not in draft status.
        """
        try:
            return self._scada.submit_for_approval(recipe_id)
        except (RecipeNotFoundError, RecipeStateError):
            return None

    def approve_recipe(
        self,
        recipe_id: str,
        approved_by: str = 'system',
    ) -> Optional[Dict[str, Any]]:
        """
        Approve a pending recipe.  ``approved_by`` maps to
        ``approver_id`` on the SCADA side.
        """
        try:
            return self._scada.approve_recipe(
                recipe_id,
                approver_id=approved_by,
            )
        except (RecipeNotFoundError, RecipeApprovalError):
            return None

    def obsolete_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Mark a recipe as obsolete by updating its status through the
        SCADA update_recipe method.
        """
        try:
            return self._scada.update_recipe(
                recipe_id,
                updates={'status': 'obsolete'},
            )
        except (RecipeNotFoundError, RecipeStateError):
            return None

    # ------------------------------------------------------------------
    # Recipe download (control recipe creation)
    # ------------------------------------------------------------------

    def download_recipe(
        self,
        recipe_id: str,
        machine_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        "Download" a recipe to a machine by creating a control recipe
        instance from the approved master recipe.

        If a *machine_id* is provided the control recipe is also started
        on that machine immediately.
        """
        try:
            control = self._scada.create_control_recipe(
                master_recipe_id=recipe_id,
                work_order_id=work_order_id,
            )

            # If a target machine was specified, start execution right away.
            if machine_id and control:
                control_id = str(control.get('id') or control.get('control_recipe_id', ''))
                if control_id:
                    try:
                        control = self._scada.start_recipe_execution(
                            control_recipe_id=control_id,
                            machine_id=machine_id,
                        )
                    except (RecipeStateError, Exception) as exc:
                        logger.warning(
                            "Created control recipe %s but could not auto-start "
                            "on machine %s: %s",
                            control_id, machine_id, exc,
                        )

            return control

        except (RecipeNotFoundError, RecipeStateError):
            return None
