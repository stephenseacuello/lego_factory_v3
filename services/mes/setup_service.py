"""
Setup Time Reduction (SMED) Tracking Service
=============================================
Tracks setup/changeover times and supports SMED analysis.
Enhanced with benchmarking, improvement tracking, and procedure checklists.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import statistics
import uuid


class SetupType(str, Enum):
    """Setup activity classification per SMED methodology."""
    INTERNAL = 'internal'  # Must be done with machine stopped
    EXTERNAL = 'external'  # Can be done while machine running


class SetupPhase(str, Enum):
    """Phases of a setup operation."""
    PREPARATION = 'preparation'
    REMOVAL = 'removal'
    INSTALLATION = 'installation'
    ADJUSTMENT = 'adjustment'
    TRIAL_RUN = 'trial_run'


class SetupStatus(str, Enum):
    """Status of an active setup."""
    NOT_STARTED = 'not_started'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


@dataclass
class SetupStep:
    """Individual step in a setup procedure."""
    step_id: str
    sequence: int
    description: str
    setup_type: SetupType
    phase: SetupPhase
    estimated_minutes: float
    actual_minutes: Optional[float] = None
    notes: str = ''
    completed: bool = False
    completed_at: Optional[datetime] = None


@dataclass
class SetupProcedureLocal:
    """Standardized setup procedure checklist."""
    procedure_id: str
    name: str
    machine_id: str
    from_product: Optional[str]
    to_product: Optional[str]
    steps: List[SetupStep] = field(default_factory=list)
    total_estimated_minutes: float = 0
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ActiveSetup:
    """Tracks an in-progress setup operation."""
    setup_id: str
    machine_id: str
    job_id: str
    procedure_id: Optional[str]
    from_product: Optional[str]
    to_product: Optional[str]
    operator_id: Optional[str]
    status: SetupStatus
    started_at: Optional[datetime]
    paused_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_pause_minutes: float
    current_step_index: int
    step_times: Dict[str, float] = field(default_factory=dict)
    notes: str = ''


@dataclass
class SetupBenchmarkLocal:
    """Benchmark data for setup times."""
    machine_id: str
    product_transition: str  # "from_product -> to_product"
    best_time_minutes: float
    avg_time_minutes: float
    worst_time_minutes: float
    std_dev_minutes: float
    sample_count: int
    last_updated: datetime


@dataclass
class SMEDImprovement:
    """Track SMED improvement project results."""
    project_id: str
    machine_id: str
    product_transition: str
    baseline_minutes: float
    current_minutes: float
    target_minutes: float
    improvement_pct: float
    internal_converted_to_external: List[str]
    streamlined_steps: List[str]
    start_date: datetime
    status: str  # 'active', 'completed', 'on_hold'


class SetupService:
    def __init__(self, session):
        self.session = session
        # Transient state for in-progress setups (OK to lose on restart)
        self._active_setups: Dict[str, ActiveSetup] = {}

    def record_setup(self, machine_id: str, job_id: str, duration_minutes: float,
                     from_material: str = None, to_material: str = None,
                     setup_type: str = 'internal', notes: str = None) -> Dict[str, Any]:
        """Record a completed setup event (legacy compatibility)."""
        from models.mes.setup import SetupEvent

        setup_id = f"SETUP-{uuid.uuid4().hex[:8].upper()}"

        db_event = SetupEvent(
            setup_id=setup_id,
            machine_id=machine_id,
            job_id=job_id,
            from_product=from_material,
            to_product=to_material,
            setup_type=setup_type,
            duration_minutes=duration_minutes,
            notes=notes,
            completed_at=datetime.utcnow(),
        )
        self.session.add(db_event)
        self.session.flush()

        event = db_event.to_dict()

        self._update_benchmark(machine_id, from_material, to_material, duration_minutes)

        return {'status': 'recorded', 'event': event}

    def start_setup(self, machine_id: str, job_id: str,
                    from_product: str = None, to_product: str = None,
                    procedure_id: str = None, operator_id: str = None) -> ActiveSetup:
        """Start tracking a new setup operation."""
        setup_id = f"SETUP-{uuid.uuid4().hex[:8].upper()}"

        active = ActiveSetup(
            setup_id=setup_id,
            machine_id=machine_id,
            job_id=job_id,
            procedure_id=procedure_id,
            from_product=from_product,
            to_product=to_product,
            operator_id=operator_id,
            status=SetupStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
            paused_at=None,
            completed_at=None,
            total_pause_minutes=0,
            current_step_index=0,
        )

        self._active_setups[setup_id] = active
        return active

    def pause_setup(self, setup_id: str, reason: str = None) -> Dict[str, Any]:
        """Pause an active setup (e.g., waiting for parts)."""
        if setup_id not in self._active_setups:
            return {'error': 'Setup not found'}

        setup = self._active_setups[setup_id]
        if setup.status != SetupStatus.IN_PROGRESS:
            return {'error': f'Cannot pause setup in status {setup.status.value}'}

        setup.status = SetupStatus.PAUSED
        setup.paused_at = datetime.utcnow()
        if reason:
            setup.notes += f"\nPaused: {reason}"

        return {'status': 'paused', 'setup_id': setup_id, 'paused_at': setup.paused_at.isoformat()}

    def resume_setup(self, setup_id: str) -> Dict[str, Any]:
        """Resume a paused setup."""
        if setup_id not in self._active_setups:
            return {'error': 'Setup not found'}

        setup = self._active_setups[setup_id]
        if setup.status != SetupStatus.PAUSED:
            return {'error': f'Cannot resume setup in status {setup.status.value}'}

        if setup.paused_at:
            pause_duration = (datetime.utcnow() - setup.paused_at).total_seconds() / 60
            setup.total_pause_minutes += pause_duration

        setup.status = SetupStatus.IN_PROGRESS
        setup.paused_at = None

        return {
            'status': 'resumed',
            'setup_id': setup_id,
            'total_pause_minutes': round(setup.total_pause_minutes, 1),
        }

    def complete_step(self, setup_id: str, step_id: str = None,
                      actual_minutes: float = None) -> Dict[str, Any]:
        """Mark a setup step as completed."""
        if setup_id not in self._active_setups:
            return {'error': 'Setup not found'}

        setup = self._active_setups[setup_id]

        if step_id and actual_minutes:
            setup.step_times[step_id] = actual_minutes

        setup.current_step_index += 1

        return {
            'status': 'step_completed',
            'setup_id': setup_id,
            'step_id': step_id,
            'current_step_index': setup.current_step_index,
        }

    def complete_setup(self, setup_id: str, notes: str = None) -> Dict[str, Any]:
        """Complete a setup operation and record metrics."""
        from models.mes.setup import SetupEvent

        if setup_id not in self._active_setups:
            return {'error': 'Setup not found'}

        setup = self._active_setups[setup_id]
        setup.completed_at = datetime.utcnow()
        setup.status = SetupStatus.COMPLETED
        if notes:
            setup.notes += f"\n{notes}"

        total_duration = (setup.completed_at - setup.started_at).total_seconds() / 60
        active_duration = total_duration - setup.total_pause_minutes

        db_event = SetupEvent(
            setup_id=setup_id,
            machine_id=setup.machine_id,
            job_id=setup.job_id,
            from_product=setup.from_product,
            to_product=setup.to_product,
            operator_id=setup.operator_id,
            setup_type='internal',
            duration_minutes=round(active_duration, 1),
            total_duration_minutes=round(total_duration, 1),
            pause_minutes=round(setup.total_pause_minutes, 1),
            step_times=setup.step_times,
            notes=setup.notes,
            completed_at=setup.completed_at,
        )
        self.session.add(db_event)
        self.session.flush()

        event = db_event.to_dict()

        self._update_benchmark(
            setup.machine_id,
            setup.from_product,
            setup.to_product,
            active_duration
        )

        del self._active_setups[setup_id]

        return {
            'status': 'completed',
            'setup_id': setup_id,
            'duration_minutes': round(active_duration, 1),
            'event': event,
        }

    def _update_benchmark(self, machine_id: str, from_product: str,
                          to_product: str, duration_minutes: float):
        """Update benchmark statistics for a product transition."""
        from models.mes.setup import SetupEvent as SetupEventModel
        from models.mes.setup import SetupBenchmark as SetupBenchmarkModel

        transition = f"{from_product or '?'} -> {to_product or '?'}"

        # Query all relevant setup events from DB
        relevant_events = self.session.query(SetupEventModel).filter(
            SetupEventModel.machine_id == machine_id,
            SetupEventModel.from_product == from_product,
            SetupEventModel.to_product == to_product,
            SetupEventModel.is_deleted == False,
        ).all()

        if not relevant_events:
            durations = [duration_minutes]
        else:
            durations = [e.duration_minutes for e in relevant_events]

        # Upsert the benchmark
        benchmark = self.session.query(SetupBenchmarkModel).filter(
            SetupBenchmarkModel.machine_id == machine_id,
            SetupBenchmarkModel.product_transition == transition,
        ).first()

        if benchmark:
            benchmark.best_time_minutes = round(min(durations), 1)
            benchmark.avg_time_minutes = round(statistics.mean(durations), 1)
            benchmark.worst_time_minutes = round(max(durations), 1)
            benchmark.std_dev_minutes = round(statistics.stdev(durations), 1) if len(durations) > 1 else 0
            benchmark.sample_count = len(durations)
        else:
            benchmark = SetupBenchmarkModel(
                machine_id=machine_id,
                product_transition=transition,
                best_time_minutes=round(min(durations), 1),
                avg_time_minutes=round(statistics.mean(durations), 1),
                worst_time_minutes=round(max(durations), 1),
                std_dev_minutes=round(statistics.stdev(durations), 1) if len(durations) > 1 else 0,
                sample_count=len(durations),
            )
            self.session.add(benchmark)

        self.session.flush()

    def create_procedure(self, name: str, machine_id: str,
                         from_product: str = None, to_product: str = None,
                         steps: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a standardized setup procedure checklist."""
        from models.mes.setup import SetupProcedure

        procedure_id = f"PROC-{uuid.uuid4().hex[:8].upper()}"

        setup_steps = []
        total_estimated = 0
        for i, step_data in enumerate(steps or []):
            step = {
                'step_id': f"{procedure_id}-S{i + 1:02d}",
                'sequence': i + 1,
                'description': step_data.get('description', ''),
                'setup_type': step_data.get('setup_type', 'internal'),
                'phase': step_data.get('phase', 'adjustment'),
                'estimated_minutes': step_data.get('estimated_minutes', 1.0),
            }
            setup_steps.append(step)
            total_estimated += step['estimated_minutes']

        db_procedure = SetupProcedure(
            procedure_id=procedure_id,
            name=name,
            machine_id=machine_id,
            from_product=from_product,
            to_product=to_product,
            steps=setup_steps,
            total_estimated_minutes=round(total_estimated, 1),
        )
        self.session.add(db_procedure)
        self.session.flush()

        return db_procedure.to_dict()

    def get_procedure(self, procedure_id: str) -> Optional[Dict[str, Any]]:
        """Get a setup procedure by ID."""
        from models.mes.setup import SetupProcedure

        proc = self.session.query(SetupProcedure).filter(
            SetupProcedure.procedure_id == procedure_id,
            SetupProcedure.is_deleted == False,
        ).first()

        return proc.to_dict() if proc else None

    def get_procedures_for_machine(self, machine_id: str) -> List[Dict[str, Any]]:
        """Get all procedures for a machine."""
        from models.mes.setup import SetupProcedure

        procs = self.session.query(SetupProcedure).filter(
            SetupProcedure.machine_id == machine_id,
            SetupProcedure.is_deleted == False,
        ).all()

        return [p.to_dict() for p in procs]

    def get_setup_trends(self, machine_id: str = None, months: int = 6) -> Dict[str, Any]:
        """Get setup time trends over time."""
        from models.mes.setup import SetupEvent

        cutoff = datetime.utcnow() - timedelta(days=months * 30)

        query = self.session.query(SetupEvent).filter(
            SetupEvent.created_at >= cutoff,
            SetupEvent.is_deleted == False,
        )
        if machine_id:
            query = query.filter(SetupEvent.machine_id == machine_id)

        filtered = query.all()

        if not filtered:
            return {
                'machine_id': machine_id,
                'months': months,
                'avg_setup_minutes': 0,
                'count': 0,
                'trend': [],
            }

        monthly = defaultdict(list)
        for e in filtered:
            month = e.created_at.strftime('%Y-%m')
            monthly[month].append(e.duration_minutes)

        trend = [
            {
                'month': m,
                'avg_minutes': round(sum(v) / len(v), 1),
                'min_minutes': round(min(v), 1),
                'max_minutes': round(max(v), 1),
                'count': len(v),
            }
            for m, v in sorted(monthly.items())
        ]

        avg = sum(e.duration_minutes for e in filtered) / len(filtered)

        trend_direction = 'stable'
        if len(trend) >= 2:
            first_avg = trend[0]['avg_minutes']
            last_avg = trend[-1]['avg_minutes']
            change_pct = ((last_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
            if change_pct < -10:
                trend_direction = 'improving'
            elif change_pct > 10:
                trend_direction = 'degrading'

        return {
            'machine_id': machine_id,
            'months': months,
            'avg_setup_minutes': round(avg, 1),
            'count': len(filtered),
            'trend': trend,
            'trend_direction': trend_direction,
        }

    def analyze_setup_reduction(self, machine_id: str = None) -> Dict[str, Any]:
        """Analyze setup times for SMED improvement opportunities."""
        from models.mes.setup import SetupEvent

        query = self.session.query(SetupEvent).filter(
            SetupEvent.is_deleted == False,
        )
        if machine_id:
            query = query.filter(SetupEvent.machine_id == machine_id)

        filtered = query.all()

        if not filtered:
            return {'message': 'No setup data available'}

        internal = [e for e in filtered if e.setup_type == 'internal']
        external = [e for e in filtered if e.setup_type == 'external']

        changeover_pairs = defaultdict(list)
        for e in filtered:
            pair = f"{e.from_product or '?'} -> {e.to_product or '?'}"
            changeover_pairs[pair].append(e.duration_minutes)

        top_pairs = sorted(
            changeover_pairs.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )[:5]

        improvement_opportunities = []
        for pair, durations in top_pairs:
            avg_duration = sum(durations) / len(durations)
            best_duration = min(durations)
            if avg_duration > best_duration * 1.2:
                improvement_opportunities.append({
                    'transition': pair,
                    'avg_minutes': round(avg_duration, 1),
                    'best_minutes': round(best_duration, 1),
                    'potential_savings_pct': round(
                        ((avg_duration - best_duration) / avg_duration) * 100, 1
                    ),
                    'count': len(durations),
                })

        return {
            'total_setups': len(filtered),
            'internal_count': len(internal),
            'external_count': len(external),
            'internal_pct': round(len(internal) / max(len(filtered), 1) * 100, 1),
            'avg_internal_min': round(
                sum(e.duration_minutes for e in internal) / max(len(internal), 1), 1
            ),
            'avg_external_min': round(
                sum(e.duration_minutes for e in external) / max(len(external), 1), 1
            ),
            'top_changeover_pairs': [
                {
                    'pair': p,
                    'avg_minutes': round(sum(d) / len(d), 1),
                    'best_minutes': round(min(d), 1),
                    'count': len(d),
                }
                for p, d in top_pairs
            ],
            'improvement_opportunities': improvement_opportunities,
        }

    def get_benchmarks(self, machine_id: str = None) -> List[Dict[str, Any]]:
        """Get setup benchmarks for comparison."""
        from models.mes.setup import SetupBenchmark as SetupBenchmarkModel

        query = self.session.query(SetupBenchmarkModel)
        if machine_id:
            query = query.filter(SetupBenchmarkModel.machine_id == machine_id)

        benchmarks = query.order_by(SetupBenchmarkModel.avg_time_minutes.desc()).all()

        return [b.to_dict() for b in benchmarks]

    def compare_to_benchmark(self, machine_id: str, from_product: str,
                              to_product: str, actual_minutes: float) -> Dict[str, Any]:
        """Compare a setup time to benchmark."""
        from models.mes.setup import SetupBenchmark as SetupBenchmarkModel

        transition = f"{from_product or '?'} -> {to_product or '?'}"

        benchmark = self.session.query(SetupBenchmarkModel).filter(
            SetupBenchmarkModel.machine_id == machine_id,
            SetupBenchmarkModel.product_transition == transition,
        ).first()

        if not benchmark:
            return {
                'has_benchmark': False,
                'actual_minutes': actual_minutes,
                'message': 'No benchmark data available for this transition',
            }

        vs_best = actual_minutes - benchmark.best_time_minutes
        vs_avg = actual_minutes - benchmark.avg_time_minutes

        performance = 'average'
        if actual_minutes <= benchmark.best_time_minutes * 1.05:
            performance = 'excellent'
        elif actual_minutes <= benchmark.avg_time_minutes:
            performance = 'good'
        elif actual_minutes >= benchmark.worst_time_minutes:
            performance = 'poor'

        return {
            'has_benchmark': True,
            'actual_minutes': round(actual_minutes, 1),
            'benchmark': {
                'best': benchmark.best_time_minutes,
                'avg': benchmark.avg_time_minutes,
                'worst': benchmark.worst_time_minutes,
            },
            'vs_best_minutes': round(vs_best, 1),
            'vs_avg_minutes': round(vs_avg, 1),
            'performance': performance,
            'pct_of_best': round((actual_minutes / benchmark.best_time_minutes) * 100, 1)
            if benchmark.best_time_minutes > 0 else 0,
        }

    def create_smed_project(self, machine_id: str, from_product: str,
                            to_product: str, target_minutes: float) -> Dict[str, Any]:
        """Create a SMED improvement project."""
        from models.mes.setup import SetupBenchmark as SetupBenchmarkModel
        from models.mes.setup import SMEDProject

        project_id = f"SMED-{uuid.uuid4().hex[:8].upper()}"
        transition = f"{from_product or '?'} -> {to_product or '?'}"

        benchmark = self.session.query(SetupBenchmarkModel).filter(
            SetupBenchmarkModel.machine_id == machine_id,
            SetupBenchmarkModel.product_transition == transition,
        ).first()

        baseline = benchmark.avg_time_minutes if benchmark else 0

        db_project = SMEDProject(
            project_id=project_id,
            machine_id=machine_id,
            product_transition=transition,
            baseline_minutes=baseline,
            current_minutes=baseline,
            target_minutes=target_minutes,
            improvement_pct=0,
            internal_converted_to_external=[],
            streamlined_steps=[],
            status='active',
        )
        self.session.add(db_project)
        self.session.flush()

        return db_project.to_dict()

    def update_smed_progress(self, project_id: str,
                              current_minutes: float = None,
                              converted_steps: List[str] = None,
                              streamlined_steps: List[str] = None) -> Dict[str, Any]:
        """Update SMED project progress."""
        from models.mes.setup import SMEDProject

        project = self.session.query(SMEDProject).filter(
            SMEDProject.project_id == project_id,
            SMEDProject.is_deleted == False,
        ).first()

        if not project:
            return {'error': 'Project not found'}

        if current_minutes is not None:
            project.current_minutes = current_minutes
            if project.baseline_minutes > 0:
                project.improvement_pct = round(
                    ((project.baseline_minutes - current_minutes) / project.baseline_minutes) * 100, 1
                )

        if converted_steps:
            existing = list(project.internal_converted_to_external or [])
            existing.extend(converted_steps)
            project.internal_converted_to_external = existing

        if streamlined_steps:
            existing = list(project.streamlined_steps or [])
            existing.extend(streamlined_steps)
            project.streamlined_steps = existing

        self.session.flush()

        target_achieved = current_minutes <= project.target_minutes if current_minutes else False

        return {
            'project_id': project_id,
            'current_minutes': project.current_minutes,
            'improvement_pct': project.improvement_pct,
            'target_achieved': target_achieved,
            'remaining_to_target': round(project.current_minutes - project.target_minutes, 1),
        }

    def get_smed_projects(self, machine_id: str = None,
                           status: str = None) -> List[Dict[str, Any]]:
        """Get SMED improvement projects."""
        from models.mes.setup import SMEDProject

        query = self.session.query(SMEDProject).filter(
            SMEDProject.is_deleted == False,
        )
        if machine_id:
            query = query.filter(SMEDProject.machine_id == machine_id)
        if status:
            query = query.filter(SMEDProject.status == status)

        projects = query.all()
        return [p.to_dict() for p in projects]

    def get_setup_by_operator(self, months: int = 3) -> Dict[str, Any]:
        """Analyze setup performance by operator."""
        from models.mes.setup import SetupEvent

        cutoff = datetime.utcnow() - timedelta(days=months * 30)

        events = self.session.query(SetupEvent).filter(
            SetupEvent.created_at >= cutoff,
            SetupEvent.operator_id.isnot(None),
            SetupEvent.operator_id != '',
            SetupEvent.is_deleted == False,
        ).all()

        by_operator = defaultdict(list)
        for e in events:
            by_operator[e.operator_id].append(e.duration_minutes)

        analysis = []
        for operator_id, durations in by_operator.items():
            analysis.append({
                'operator_id': operator_id,
                'setup_count': len(durations),
                'avg_minutes': round(statistics.mean(durations), 1),
                'best_minutes': round(min(durations), 1),
                'consistency': round(statistics.stdev(durations), 1) if len(durations) > 1 else 0,
            })

        return {
            'period_months': months,
            'operators': sorted(analysis, key=lambda x: x['avg_minutes']),
            'best_performer': min(analysis, key=lambda x: x['avg_minutes'])['operator_id']
            if analysis else None,
        }

    def get_phase_analysis(self, machine_id: str = None) -> Dict[str, Any]:
        """Analyze setup time by phase (for SMED analysis)."""
        from models.mes.setup import SetupEvent

        query = self.session.query(SetupEvent).filter(
            SetupEvent.step_times.isnot(None),
            SetupEvent.is_deleted == False,
        )
        if machine_id:
            query = query.filter(SetupEvent.machine_id == machine_id)

        relevant = query.all()

        # Filter out events with empty step_times dicts
        relevant = [e for e in relevant if e.step_times]

        if not relevant:
            return {'message': 'No detailed phase data available'}

        phase_totals = defaultdict(list)
        for event in relevant:
            for step_id, duration in (event.step_times or {}).items():
                phase = step_id.split('-')[-1] if '-' in step_id else 'unknown'
                phase_totals[phase].append(duration)

        phases = [
            {
                'phase': phase,
                'avg_minutes': round(statistics.mean(durations), 1),
                'total_minutes': round(sum(durations), 1),
                'count': len(durations),
            }
            for phase, durations in phase_totals.items()
        ]

        return {
            'machine_id': machine_id,
            'phases': sorted(phases, key=lambda x: x['total_minutes'], reverse=True),
            'longest_phase': max(phases, key=lambda x: x['avg_minutes'])['phase'] if phases else None,
        }
