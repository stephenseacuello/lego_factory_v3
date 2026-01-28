"""
LEGO Factory v3 - Simulation View Routes
=========================================
Web view routes for simulation dashboards.
"""

from flask import Blueprint, render_template

simulation_views = Blueprint('simulation_views', __name__, url_prefix='/simulation')


@simulation_views.route('/dashboard')
def simulation_dashboard():
    """Render simulation dashboard."""
    return render_template('simulation/dashboard.html')


@simulation_views.route('/compare')
def algorithm_comparison():
    """Render algorithm comparison page."""
    return render_template('simulation/compare.html')
