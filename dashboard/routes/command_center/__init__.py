"""
LEGO MCP V8 Command Center Routes
==================================

Unified command and control dashboard routes.

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta
import asyncio

command_center_bp = Blueprint('command_center', __name__, url_prefix='/command-center')


@command_center_bp.route('/')
def index():
    """Main command center dashboard"""
    return render_template('pages/command_center/dashboard.html')


@command_center_bp.route('/actions')
def actions():
    """Action console page"""
    return render_template('pages/command_center/actions.html')


@command_center_bp.route('/cosim')
def cosimulation():
    """Co-simulation control page"""
    return render_template('pages/command_center/cosimulation.html')


@command_center_bp.route('/alerts')
def alerts():
    """Alert management page"""
    return render_template('pages/command_center/alerts.html')


# API Endpoints

@command_center_bp.route('/api/status')
def api_status():
    """Get complete system status"""
    try:
        from services.command_center import get_health_service
        health_service = get_health_service()

        # Run async check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            summary = loop.run_until_complete(health_service.check_all())
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": summary.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/kpis')
def api_kpis():
    """Get aggregated KPIs"""
    try:
        from services.command_center import get_kpi_aggregator

        level = request.args.get('level', 'plant')
        period = request.args.get('period', 'realtime')

        aggregator = get_kpi_aggregator()
        dashboard = aggregator.get_dashboard()

        return jsonify({
            "success": True,
            "data": dashboard.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/kpis/<kpi_name>')
def api_kpi_detail(kpi_name):
    """Get specific KPI with history"""
    try:
        from services.command_center import get_kpi_aggregator

        aggregator = get_kpi_aggregator()
        metric = aggregator.get_metric(kpi_name)
        history = aggregator.get_metric_history(
            kpi_name,
            since=datetime.now() - timedelta(hours=24),
            limit=100
        )

        return jsonify({
            "success": True,
            "data": {
                "current": metric.to_dict() if metric else None,
                "history": [m.to_dict() for m in history]
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/alerts', methods=['GET'])
def api_alerts_list():
    """Get active alerts"""
    try:
        from services.command_center import get_alert_manager

        severity = request.args.get('severity')
        source = request.args.get('source')
        limit = int(request.args.get('limit', 100))

        manager = get_alert_manager()
        alerts = manager.get_active_alerts(limit=limit)
        summary = manager.get_summary()

        return jsonify({
            "success": True,
            "data": {
                "alerts": [a.to_dict() for a in alerts],
                "summary": summary.to_dict()
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/alerts/<alert_id>/acknowledge', methods=['POST'])
def api_alert_acknowledge(alert_id):
    """Acknowledge an alert"""
    try:
        from services.command_center import get_alert_manager

        data = request.get_json() or {}
        user = data.get('user', 'anonymous')
        note = data.get('note', '')

        manager = get_alert_manager()
        alert = manager.acknowledge_alert(alert_id, user, note)

        if alert:
            return jsonify({
                "success": True,
                "data": alert.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/alerts/<alert_id>/resolve', methods=['POST'])
def api_alert_resolve(alert_id):
    """Resolve an alert"""
    try:
        from services.command_center import get_alert_manager

        data = request.get_json() or {}
        user = data.get('user', 'anonymous')
        resolution = data.get('resolution', '')

        manager = get_alert_manager()
        alert = manager.resolve_alert(alert_id, user, resolution)

        if alert:
            return jsonify({
                "success": True,
                "data": alert.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/actions', methods=['GET'])
def api_actions_list():
    """Get pending actions"""
    try:
        from services.command_center import get_action_console

        console = get_action_console()
        pending = console.get_pending_actions()
        stats = console.get_queue_stats()

        return jsonify({
            "success": True,
            "data": {
                "pending": [a.to_dict() for a in pending],
                "stats": stats.to_dict()
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/actions', methods=['POST'])
def api_actions_create():
    """Create a new action"""
    try:
        from services.command_center import (
            get_action_console,
            ActionCategory,
            ActionPriority
        )

        data = request.get_json()
        console = get_action_console()

        action = console.create_action(
            title=data.get('title'),
            description=data.get('description'),
            category=ActionCategory(data.get('category', 'preventive')),
            executor=data.get('executor'),
            parameters=data.get('parameters', {}),
            priority=ActionPriority(data.get('priority', 'normal')),
            source=data.get('source', 'manual')
        )

        return jsonify({
            "success": True,
            "data": action.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/actions/<action_id>/approve', methods=['POST'])
def api_action_approve(action_id):
    """Approve an action"""
    try:
        from services.command_center import get_action_console

        data = request.get_json() or {}
        user = data.get('user', 'anonymous')
        note = data.get('note', '')

        console = get_action_console()
        action = console.approve_action(action_id, user, note)

        if action:
            return jsonify({
                "success": True,
                "data": action.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Action not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/actions/<action_id>/reject', methods=['POST'])
def api_action_reject(action_id):
    """Reject an action"""
    try:
        from services.command_center import get_action_console

        data = request.get_json() or {}
        user = data.get('user', 'anonymous')
        reason = data.get('reason', '')

        console = get_action_console()
        action = console.reject_action(action_id, user, reason)

        if action:
            return jsonify({
                "success": True,
                "data": action.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Action not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/cosim/run', methods=['POST'])
def api_cosim_run():
    """Run a co-simulation"""
    try:
        from services.cosimulation import (
            get_cosim_coordinator,
            SimulationConfig,
            SimulationMode,
            SimulationEngine
        )

        data = request.get_json()
        coordinator = get_cosim_coordinator()

        config = SimulationConfig(
            mode=SimulationMode(data.get('mode', 'accelerated')),
            engines=[SimulationEngine(e) for e in data.get('engines', ['des'])],
            start_time=datetime.fromisoformat(data.get('start_time', datetime.now().isoformat())),
            end_time=datetime.fromisoformat(data.get('end_time', (datetime.now() + timedelta(hours=8)).isoformat())),
            time_step_seconds=data.get('time_step', 60.0),
            speedup_factor=data.get('speedup', 100.0),
            parameters=data.get('parameters', {})
        )

        # Run async simulation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coordinator.run_simulation(config))
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/cosim/<simulation_id>')
def api_cosim_status(simulation_id):
    """Get simulation status"""
    try:
        from services.cosimulation import get_cosim_coordinator

        coordinator = get_cosim_coordinator()
        result = coordinator.get_simulation(simulation_id)

        if result:
            return jsonify({
                "success": True,
                "data": result.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Simulation not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/cosim/<simulation_id>/stop', methods=['POST'])
def api_cosim_stop(simulation_id):
    """Stop a running simulation"""
    try:
        from services.cosimulation import get_cosim_coordinator

        coordinator = get_cosim_coordinator()
        coordinator.stop_simulation(simulation_id)

        return jsonify({
            "success": True,
            "message": "Simulation stopped"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================
# V8 Enhanced API Routes
# ============================================

@command_center_bp.route('/api/orchestration/workflows')
def api_workflows_list():
    """Get all workflows"""
    try:
        from services.command_center import get_orchestrator

        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))

        orchestrator = get_orchestrator()
        workflows = orchestrator.get_workflows(status=status, limit=limit)

        return jsonify({
            "success": True,
            "data": {
                "workflows": [w.to_dict() for w in workflows],
                "count": len(workflows)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/orchestration/workflows', methods=['POST'])
def api_workflow_create():
    """Create a new workflow"""
    try:
        from services.command_center import get_orchestrator, create_production_workflow

        data = request.get_json()
        orchestrator = get_orchestrator()

        workflow = create_production_workflow(
            name=data.get('name'),
            job_id=data.get('job_id'),
            parameters=data.get('parameters', {})
        )

        orchestrator.register_workflow(workflow)

        return jsonify({
            "success": True,
            "data": workflow.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/orchestration/workflows/<workflow_id>')
def api_workflow_detail(workflow_id):
    """Get workflow details"""
    try:
        from services.command_center import get_orchestrator

        orchestrator = get_orchestrator()
        workflow = orchestrator.get_workflow(workflow_id)

        if workflow:
            return jsonify({
                "success": True,
                "data": workflow.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Workflow not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/orchestration/workflows/<workflow_id>/start', methods=['POST'])
def api_workflow_start(workflow_id):
    """Start a workflow"""
    try:
        from services.command_center import get_orchestrator

        orchestrator = get_orchestrator()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(orchestrator.start_workflow(workflow_id))
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": result.to_dict() if hasattr(result, 'to_dict') else result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/orchestration/workflows/<workflow_id>/pause', methods=['POST'])
def api_workflow_pause(workflow_id):
    """Pause a workflow"""
    try:
        from services.command_center import get_orchestrator

        orchestrator = get_orchestrator()
        orchestrator.pause_workflow(workflow_id)

        return jsonify({
            "success": True,
            "message": "Workflow paused"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/orchestration/workflows/<workflow_id>/resume', methods=['POST'])
def api_workflow_resume(workflow_id):
    """Resume a paused workflow"""
    try:
        from services.command_center import get_orchestrator

        orchestrator = get_orchestrator()
        orchestrator.resume_workflow(workflow_id)

        return jsonify({
            "success": True,
            "message": "Workflow resumed"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/services')
def api_services_list():
    """Get registered services"""
    try:
        from services.command_center import get_registry

        registry = get_registry()
        services = registry.get_all_services()

        return jsonify({
            "success": True,
            "data": {
                "services": [s.to_dict() for s in services],
                "count": len(services)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/services/<service_id>/health')
def api_service_health(service_id):
    """Get service health"""
    try:
        from services.command_center import get_registry

        registry = get_registry()
        service = registry.get_service(service_id)

        if service:
            health = registry.check_service_health(service_id)
            return jsonify({
                "success": True,
                "data": {
                    "service": service.to_dict(),
                    "health": health.to_dict() if hasattr(health, 'to_dict') else health
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Service not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/equipment')
def api_equipment_list():
    """Get equipment status from ROS2"""
    try:
        from services.command_center import get_ros2_command_center

        ros2 = get_ros2_command_center()
        dashboard_data = ros2.get_dashboard_data()

        return jsonify({
            "success": True,
            "data": dashboard_data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/equipment/<equipment_id>')
def api_equipment_detail(equipment_id):
    """Get equipment details"""
    try:
        from services.command_center import get_ros2_command_center

        ros2 = get_ros2_command_center()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            state = loop.run_until_complete(ros2.get_equipment_state(equipment_id))
        finally:
            loop.close()

        if state:
            return jsonify({
                "success": True,
                "data": state.to_dict() if hasattr(state, 'to_dict') else state
            })
        else:
            return jsonify({
                "success": False,
                "error": "Equipment not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/equipment/<equipment_id>/control', methods=['POST'])
def api_equipment_control(equipment_id):
    """Control equipment"""
    try:
        from services.command_center import get_ros2_command_center

        data = request.get_json()
        action = data.get('action')
        parameters = data.get('parameters', {})

        ros2 = get_ros2_command_center()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if action == 'activate':
                result = loop.run_until_complete(ros2.activate_node(equipment_id))
            elif action == 'deactivate':
                result = loop.run_until_complete(ros2.deactivate_node(equipment_id))
            elif action == 'configure':
                result = loop.run_until_complete(ros2.configure_node(equipment_id))
            elif action == 'set_parameter':
                param_name = parameters.get('name')
                param_value = parameters.get('value')
                result = loop.run_until_complete(
                    ros2.set_equipment_parameter(equipment_id, param_name, param_value)
                )
            else:
                return jsonify({
                    "success": False,
                    "error": f"Unknown action: {action}"
                }), 400
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": result.to_dict() if hasattr(result, 'to_dict') else result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/equipment/emergency-stop', methods=['POST'])
def api_emergency_stop():
    """Trigger emergency stop"""
    try:
        from services.command_center import get_ros2_command_center

        data = request.get_json() or {}
        reason = data.get('reason', 'Manual emergency stop')

        ros2 = get_ros2_command_center()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(ros2.trigger_emergency_stop(reason))
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": result.to_dict() if hasattr(result, 'to_dict') else result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/equipment/emergency-stop/reset', methods=['POST'])
def api_emergency_stop_reset():
    """Reset emergency stop"""
    try:
        from services.command_center import get_ros2_command_center

        data = request.get_json() or {}
        authorized_by = data.get('authorized_by', 'anonymous')

        ros2 = get_ros2_command_center()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(ros2.reset_emergency_stop(authorized_by))
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": result.to_dict() if hasattr(result, 'to_dict') else result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/events')
def api_events_list():
    """Get system events"""
    try:
        from services.command_center import get_message_bus

        event_type = request.args.get('type')
        limit = int(request.args.get('limit', 100))
        since = request.args.get('since')

        bus = get_message_bus()

        if since:
            since_dt = datetime.fromisoformat(since)
        else:
            since_dt = datetime.now() - timedelta(hours=24)

        events = bus.get_events(event_type=event_type, since=since_dt, limit=limit)

        return jsonify({
            "success": True,
            "data": {
                "events": [e.to_dict() for e in events],
                "count": len(events)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/events', methods=['POST'])
def api_events_emit():
    """Emit a system event"""
    try:
        from services.command_center import get_message_bus, EventType, EventPriority

        data = request.get_json()
        bus = get_message_bus()

        event = bus.emit(
            event_type=EventType(data.get('type', 'system')),
            source=data.get('source', 'api'),
            payload=data.get('payload', {}),
            priority=EventPriority(data.get('priority', 'normal'))
        )

        return jsonify({
            "success": True,
            "data": event.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/notifications', methods=['POST'])
def api_send_notification():
    """Send a notification"""
    try:
        from services.notifications import (
            get_notification_service,
            NotificationChannel,
            NotificationPriority
        )

        data = request.get_json()
        service = get_notification_service()

        channels = [NotificationChannel(c) for c in data.get('channels', ['in_app'])]

        result = service.send(
            title=data.get('title'),
            body=data.get('body'),
            channels=channels,
            priority=NotificationPriority(data.get('priority', 'normal')),
            recipients=data.get('recipients'),
            metadata=data.get('metadata', {})
        )

        return jsonify({
            "success": True,
            "data": result.to_dict() if hasattr(result, 'to_dict') else result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/audit')
def api_audit_log():
    """Get audit log entries"""
    try:
        from services.compliance import get_audit_logger

        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 100))
        user_id = request.args.get('user')

        audit = get_audit_logger()

        if user_id:
            events = audit.get_events_by_user(user_id, limit=limit)
        else:
            events = audit.get_recent_events(hours=hours, limit=limit)

        return jsonify({
            "success": True,
            "data": {
                "events": events,
                "count": len(events)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/audit/compliance')
def api_compliance_dashboard():
    """Get compliance dashboard data"""
    try:
        from services.compliance import get_audit_logger

        audit = get_audit_logger()
        data = audit.get_compliance_dashboard_data()

        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/performance')
def api_performance_metrics():
    """Get performance metrics"""
    try:
        from services.monitoring import get_performance_collector

        period = int(request.args.get('period', 15))
        category = request.args.get('category')

        collector = get_performance_collector()
        report = collector.generate_report(period_minutes=period)

        return jsonify({
            "success": True,
            "data": report.to_dict() if hasattr(report, 'to_dict') else report
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/decisions')
def api_decisions_list():
    """Get pending decisions"""
    try:
        from services.orchestration import get_decision_engine

        status = request.args.get('status', 'pending')
        limit = int(request.args.get('limit', 50))

        engine = get_decision_engine()
        decisions = engine.get_decisions(status=status, limit=limit)

        return jsonify({
            "success": True,
            "data": {
                "decisions": [d.to_dict() for d in decisions],
                "count": len(decisions)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/decisions/<decision_id>/approve', methods=['POST'])
def api_decision_approve(decision_id):
    """Approve a decision"""
    try:
        from services.orchestration import get_decision_engine

        data = request.get_json() or {}
        user = data.get('user', 'anonymous')
        note = data.get('note', '')

        engine = get_decision_engine()
        decision = engine.approve_decision(decision_id, user, note)

        if decision:
            return jsonify({
                "success": True,
                "data": decision.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Decision not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/decisions/<decision_id>/reject', methods=['POST'])
def api_decision_reject(decision_id):
    """Reject a decision"""
    try:
        from services.orchestration import get_decision_engine

        data = request.get_json() or {}
        user = data.get('user', 'anonymous')
        reason = data.get('reason', '')

        engine = get_decision_engine()
        decision = engine.reject_decision(decision_id, user, reason)

        if decision:
            return jsonify({
                "success": True,
                "data": decision.to_dict()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Decision not found"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/scenarios')
def api_scenarios_list():
    """Get available scenarios"""
    try:
        from services.cosimulation import get_scenario_manager

        manager = get_scenario_manager()
        scenarios = manager.get_scenarios()

        return jsonify({
            "success": True,
            "data": {
                "scenarios": [s.to_dict() for s in scenarios],
                "count": len(scenarios)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/scenarios/<scenario_id>/run', methods=['POST'])
def api_scenario_run(scenario_id):
    """Run a scenario"""
    try:
        from services.cosimulation import get_scenario_manager

        data = request.get_json() or {}
        compare_with = data.get('compare_with', [])

        manager = get_scenario_manager()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(manager.run_scenario(scenario_id))

            comparison = None
            if compare_with:
                comparison = loop.run_until_complete(
                    manager.compare_scenarios([scenario_id] + compare_with)
                )
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": {
                "result": result.to_dict() if hasattr(result, 'to_dict') else result,
                "comparison": comparison
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@command_center_bp.route('/api/dashboard')
def api_unified_dashboard():
    """Get unified dashboard data"""
    try:
        from services.command_center import (
            SystemHealthService,
            KPIAggregator,
            AlertManager,
            ActionConsole,
            get_registry
        )
        from services.monitoring import get_performance_collector

        # Collect all dashboard data
        health_service = SystemHealthService()
        kpi_aggregator = KPIAggregator()
        alert_manager = AlertManager()
        action_console = ActionConsole()
        registry = get_registry()
        perf_collector = get_performance_collector()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            health_summary = loop.run_until_complete(health_service.check_all())
        finally:
            loop.close()

        dashboard_data = {
            "health": health_summary.to_dict(),
            "kpis": kpi_aggregator.get_dashboard().to_dict(),
            "alerts": {
                "active": [a.to_dict() for a in alert_manager.get_active_alerts(limit=10)],
                "summary": alert_manager.get_summary().to_dict()
            },
            "actions": {
                "pending": [a.to_dict() for a in action_console.get_pending_actions()[:10]],
                "stats": action_console.get_queue_stats().to_dict()
            },
            "services": {
                "count": len(registry.get_all_services()),
                "healthy": len([s for s in registry.get_all_services() if s.status == 'healthy'])
            },
            "performance": perf_collector.generate_report(period_minutes=15).to_dict(),
            "timestamp": datetime.now().isoformat()
        }

        return jsonify({
            "success": True,
            "data": dashboard_data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
