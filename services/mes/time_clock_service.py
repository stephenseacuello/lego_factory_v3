"""
Time Clock & Labor Cost Tracking Service
=========================================
Clock in/out, timesheets, overtime, labor cost allocation,
skill matrix, certification tracking, and cross-training recommendations.
"""
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
import statistics


class CertificationStatus(str, Enum):
    """Status of a worker certification."""
    ACTIVE = 'active'
    EXPIRING_SOON = 'expiring_soon'  # < 30 days
    EXPIRED = 'expired'
    PENDING = 'pending'
    REVOKED = 'revoked'


class SkillLevel(int, Enum):
    """Skill proficiency levels."""
    TRAINEE = 1
    BEGINNER = 2
    INTERMEDIATE = 3
    PROFICIENT = 4
    EXPERT = 5


@dataclass
class Certification:
    """Worker certification record."""
    cert_id: str
    worker_id: str
    certification_type: str
    certification_name: str
    issued_date: date
    expiry_date: date
    issuing_authority: str
    status: CertificationStatus = CertificationStatus.ACTIVE
    credential_number: str = ''
    notes: str = ''

    def days_until_expiry(self) -> int:
        return (self.expiry_date - date.today()).days

    def is_expired(self) -> bool:
        return self.expiry_date < date.today()

    def is_expiring_soon(self, days: int = 30) -> bool:
        return 0 <= self.days_until_expiry() <= days


@dataclass
class WorkerSkill:
    """Worker skill record."""
    worker_id: str
    skill_id: str
    skill_name: str
    level: SkillLevel
    acquired_date: date
    last_assessed_date: Optional[date] = None
    hours_practiced: float = 0
    training_completed: List[str] = field(default_factory=list)
    required_for_machines: List[str] = field(default_factory=list)


@dataclass
class WorkerProfile:
    """Complete worker profile with skills and certifications."""
    worker_id: str
    name: str
    department: str
    hire_date: date
    hourly_rate: float
    skills: Dict[str, WorkerSkill] = field(default_factory=dict)
    certifications: Dict[str, Certification] = field(default_factory=dict)
    efficiency_rating: float = 1.0
    availability_status: str = 'available'
    primary_machines: List[str] = field(default_factory=list)


@dataclass
class TimeEntryLocal:
    """Time clock entry record (local/in-memory dataclass)."""
    entry_id: str
    worker_id: str
    clock_in: datetime
    clock_out: Optional[datetime]
    machine_id: Optional[str]
    job_id: Optional[str]
    skill_used: Optional[str]
    regular_hours: float = 0
    overtime_hours: float = 0
    break_minutes: float = 0
    labor_cost: float = 0
    notes: str = ''


@dataclass
class LaborEfficiency:
    """Labor efficiency metrics for a worker."""
    worker_id: str
    skill_id: str
    period_start: date
    period_end: date
    total_hours: float
    productive_hours: float
    efficiency_pct: float
    units_produced: int
    units_per_hour: float
    quality_score: float
    benchmark_comparison: float  # vs. average


@dataclass
class CrossTrainingRecommendation:
    """Cross-training recommendation for a worker."""
    worker_id: str
    skill_id: str
    skill_name: str
    priority: int  # 1-5, 1 is highest
    reason: str
    estimated_training_hours: float
    business_impact: str
    prerequisite_skills: List[str]
    recommended_by: str = 'system'


class TimeClockService:
    def __init__(self, session):
        self.session = session
        self._skill_requirements: Dict[str, List[str]] = {}  # machine_id -> required skills

        self._overtime_rules = {
            'weekly_threshold': 40.0,
            'daily_threshold': 8.0,
            'overtime_multiplier': 1.5,
            'double_time_threshold': 12.0,
            'double_time_multiplier': 2.0,
        }

    # =========================================================================
    # DB Helper
    # =========================================================================

    def _resolve_worker(self, employee_id: str):
        """Look up a Worker by employee_id, auto-creating if not found."""
        from models.mes.labor import Worker as WorkerModel

        worker = self.session.query(WorkerModel).filter(
            WorkerModel.employee_id == employee_id
        ).first()
        if not worker:
            worker = WorkerModel(
                employee_id=employee_id,
                first_name=employee_id,
                last_name='',
                department='Production',
                hourly_rate=25.0,
            )
            self.session.add(worker)
            self.session.flush()
        return worker

    @staticmethod
    def _parse_date(value) -> date:
        """Parse a value into a date object, handling strings and date/datetime."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            # Try ISO format first (YYYY-MM-DD)
            for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse date string: {value}")
        return value

    # =========================================================================
    # Clock In/Out
    # =========================================================================

    def clock_in(self, worker_id: str, machine_id: str = None,
                 job_id: str = None, skill_id: str = None) -> Dict[str, Any]:
        """Clock in a worker. Persists active session to DB."""
        from models.mes.labor import ActiveClockSession

        existing = self.session.query(ActiveClockSession).filter(
            ActiveClockSession.employee_id == worker_id
        ).first()

        if existing:
            return {
                'error': 'Already clocked in',
                'clock_in': existing.clock_in.isoformat()
            }

        worker_db = self._resolve_worker(worker_id)
        now = datetime.utcnow()

        session_row = ActiveClockSession(
            worker_id=worker_db.id,
            employee_id=worker_id,
            job_id=job_id,
            machine_id=machine_id,
            skill_id=skill_id,
            clock_in=now,
            breaks=[],
        )
        self.session.add(session_row)
        self.session.flush()

        return {
            'status': 'clocked_in',
            'worker_id': worker_id,
            'clock_in': now.isoformat(),
            'machine_id': machine_id,
            'job_id': job_id,
        }

    def start_break(self, worker_id: str, break_type: str = 'standard') -> Dict[str, Any]:
        """Start a break for a clocked-in worker."""
        from models.mes.labor import ActiveClockSession

        session_row = self.session.query(ActiveClockSession).filter(
            ActiveClockSession.employee_id == worker_id
        ).first()

        if not session_row:
            return {'error': 'Not clocked in'}

        breaks = list(session_row.breaks or [])
        breaks.append({
            'start': datetime.utcnow().isoformat(),
            'end': None,
            'type': break_type,
        })
        session_row.breaks = breaks
        self.session.flush()

        return {
            'status': 'break_started',
            'worker_id': worker_id,
            'break_type': break_type,
        }

    def end_break(self, worker_id: str) -> Dict[str, Any]:
        """End the current break."""
        from models.mes.labor import ActiveClockSession

        session_row = self.session.query(ActiveClockSession).filter(
            ActiveClockSession.employee_id == worker_id
        ).first()

        if not session_row:
            return {'error': 'Not clocked in'}

        breaks = list(session_row.breaks or [])
        if not breaks or breaks[-1]['end'] is not None:
            return {'error': 'No active break'}

        now = datetime.utcnow()
        breaks[-1]['end'] = now.isoformat()
        start = datetime.fromisoformat(breaks[-1]['start'])
        break_minutes = (now - start).total_seconds() / 60
        session_row.breaks = breaks
        self.session.flush()

        return {
            'status': 'break_ended',
            'worker_id': worker_id,
            'break_minutes': round(break_minutes, 1),
        }

    def clock_out(self, worker_id: str, notes: str = '') -> Dict[str, Any]:
        """Clock out a worker and create time entry. Reads from DB session."""
        from models.mes.labor import ActiveClockSession, TimeEntry as TimeEntryModel

        session_row = self.session.query(ActiveClockSession).filter(
            ActiveClockSession.employee_id == worker_id
        ).first()

        if not session_row:
            return {'error': 'Not clocked in'}

        clock_out = datetime.utcnow()

        total_break_minutes = 0
        for brk in (session_row.breaks or []):
            end_str = brk.get('end')
            start_str = brk.get('start')
            if end_str and start_str:
                brk_start = datetime.fromisoformat(start_str)
                brk_end = datetime.fromisoformat(end_str)
                total_break_minutes += (brk_end - brk_start).total_seconds() / 60

        total_hours = (clock_out - session_row.clock_in).total_seconds() / 3600
        work_hours = total_hours - (total_break_minutes / 60)

        regular_hours, overtime_hours = self._calculate_overtime(work_hours)

        # Resolve worker from DB for hourly rate
        worker_db = self._resolve_worker(worker_id)
        hourly_rate = worker_db.hourly_rate if worker_db.hourly_rate else 25.0
        labor_cost = (regular_hours * hourly_rate +
                      overtime_hours * hourly_rate * self._overtime_rules['overtime_multiplier'])

        entry_id = f"TE-{uuid.uuid4().hex[:8].upper()}"

        # Build notes field: include job_id as metadata if present
        job_id_str = session_row.job_id or ''
        if job_id_str:
            db_notes = f"job:{job_id_str}"
            if notes:
                db_notes = f"job:{job_id_str} | {notes}"
        else:
            db_notes = notes

        # Persist TimeEntry to DB
        db_entry = TimeEntryModel(
            worker_id=worker_db.id,
            clock_in=session_row.clock_in,
            clock_out=clock_out,
            break_minutes=int(total_break_minutes),
            regular_hours=round(regular_hours, 2),
            overtime_hours=round(overtime_hours, 2),
            entry_type='direct',
            notes=db_notes,
        )
        self.session.add(db_entry)

        # Remove the active session
        clock_in_time = session_row.clock_in
        machine_id = session_row.machine_id
        ses_job_id = session_row.job_id
        self.session.delete(session_row)
        self.session.flush()

        # Post labor cost to GL (ISA-95 Level 3→4 integration)
        self._post_labor_gl_entry(
            worker_db=worker_db,
            labor_cost=labor_cost,
            regular_hours=regular_hours,
            overtime_hours=overtime_hours,
            job_id=ses_job_id,
            entry_id=entry_id,
        )

        return {
            'status': 'clocked_out',
            'worker_id': worker_id,
            'entry_id': entry_id,
            'clock_in': clock_in_time.isoformat(),
            'clock_out': clock_out.isoformat(),
            'total_hours': round(total_hours, 2),
            'work_hours': round(work_hours, 2),
            'regular_hours': round(regular_hours, 2),
            'overtime_hours': round(overtime_hours, 2),
            'break_minutes': round(total_break_minutes, 1),
            'labor_cost': round(labor_cost, 2),
            'machine_id': machine_id,
            'job_id': ses_job_id,
        }

    def _calculate_overtime(self, hours: float) -> tuple:
        """Calculate regular and overtime hours."""
        daily_threshold = self._overtime_rules['daily_threshold']
        if hours <= daily_threshold:
            return hours, 0
        return daily_threshold, hours - daily_threshold

    def _post_labor_gl_entry(self, worker_db, labor_cost: float,
                              regular_hours: float, overtime_hours: float,
                              job_id: str = None, entry_id: str = '') -> None:
        """Post labor cost journal entry to ERP GL (ISA-95 Level 3→4).
        Debit: Direct Labor (5100) or WIP (1310 if job-linked)
        Credit: Accrued Liabilities (2100)
        """
        if labor_cost <= 0:
            return

        try:
            from models.erp.financial import GLAccount
            from services.erp.financial_service import FinancialService

            # Look up accounts by number
            debit_acct_num = '1310' if job_id else '5100'  # WIP if job, else Direct Labor
            credit_acct_num = '2100'  # Accrued Liabilities

            debit_acct = self.session.query(GLAccount).filter(
                GLAccount.account_number == debit_acct_num
            ).first()
            credit_acct = self.session.query(GLAccount).filter(
                GLAccount.account_number == credit_acct_num
            ).first()

            if not debit_acct or not credit_acct:
                return  # GL accounts not seeded yet — skip silently

            fs = FinancialService(self.session)
            je = fs.create_journal_entry({
                'description': f"Labor cost: {worker_db.employee_id} ({regular_hours:.1f}h + {overtime_hours:.1f}h OT)",
                'source_type': 'time_clock',
                'source_id': entry_id,
                'created_by': 'mes_timeclock',
                'lines': [
                    {
                        'account_id': debit_acct.id,
                        'debit_amount': round(labor_cost, 2),
                        'credit_amount': 0,
                        'description': f"Labor: {worker_db.employee_id}",
                        'department': worker_db.department,
                    },
                    {
                        'account_id': credit_acct.id,
                        'debit_amount': 0,
                        'credit_amount': round(labor_cost, 2),
                        'description': f"Payroll accrual: {worker_db.employee_id}",
                    },
                ],
            })

            # Auto-post the journal entry
            if je and je.get('journal_number'):
                fs.post_journal_entry(je['journal_number'], user_id='mes_timeclock')

        except Exception:
            # Don't let GL posting failures break clock-out
            pass

    def get_active_workers(self) -> List[Dict[str, Any]]:
        """Get list of currently clocked-in workers from DB."""
        from models.mes.labor import ActiveClockSession
        from sqlalchemy.orm import joinedload

        sessions = self.session.query(ActiveClockSession).options(
            joinedload(ActiveClockSession.worker)
        ).all()

        result = []
        now = datetime.utcnow()
        for s in sessions:
            hours = (now - s.clock_in).total_seconds() / 3600
            name = f"{s.worker.first_name} {s.worker.last_name}".strip() if s.worker else s.employee_id
            breaks = s.breaks or []
            on_break = bool(breaks and breaks[-1].get('end') is None)

            result.append({
                'worker_id': s.employee_id,
                'worker_name': name,
                'clock_in': s.clock_in.isoformat(),
                'hours_so_far': round(hours, 2),
                'machine_id': s.machine_id,
                'job_id': s.job_id,
                'skill_id': s.skill_id,
                'on_break': on_break,
            })
        return result

    # =========================================================================
    # Timesheet & Reports
    # =========================================================================

    def get_timesheet(self, worker_id: str, start_date: date = None,
                      end_date: date = None) -> Dict[str, Any]:
        """Get timesheet for a worker."""
        start_date = self._parse_date(start_date) if start_date else (date.today() - timedelta(days=7))
        end_date = self._parse_date(end_date) if end_date else date.today()

        from models.mes.labor import Worker as WorkerModel, TimeEntry as TimeEntryModel

        worker = self.session.query(WorkerModel).filter(
            WorkerModel.employee_id == worker_id
        ).first()

        if not worker:
            return {
                'worker_id': worker_id,
                'period': {'start': str(start_date), 'end': str(end_date)},
                'total_regular_hours': 0,
                'total_overtime_hours': 0,
                'total_hours': 0,
                'total_labor_cost': 0,
                'entry_count': 0,
                'daily_breakdown': {},
            }

        entries = self.session.query(TimeEntryModel).filter(
            TimeEntryModel.worker_id == worker.id,
            TimeEntryModel.clock_in >= datetime.combine(start_date, datetime.min.time()),
            TimeEntryModel.clock_in <= datetime.combine(end_date, datetime.max.time()),
        ).all()

        hourly_rate = worker.hourly_rate if worker.hourly_rate else 25.0

        total_regular = sum(e.regular_hours or 0 for e in entries)
        total_overtime = sum(e.overtime_hours or 0 for e in entries)
        total_cost = sum(
            (e.regular_hours or 0) * hourly_rate +
            (e.overtime_hours or 0) * hourly_rate * self._overtime_rules['overtime_multiplier']
            for e in entries
        )

        daily_breakdown = defaultdict(lambda: {'regular': 0, 'overtime': 0, 'entries': []})
        for e in entries:
            day = e.clock_in.date().isoformat()
            daily_breakdown[day]['regular'] += e.regular_hours or 0
            daily_breakdown[day]['overtime'] += e.overtime_hours or 0

            # Extract job_id from notes if stored there
            job_id = None
            if e.notes and e.notes.startswith('job:'):
                job_id = e.notes.split('job:')[1].split(' |')[0].strip() or None

            daily_breakdown[day]['entries'].append({
                'entry_id': str(e.id),
                'clock_in': e.clock_in.isoformat(),
                'clock_out': e.clock_out.isoformat() if e.clock_out else None,
                'machine_id': None,
                'job_id': job_id,
            })

        return {
            'worker_id': worker_id,
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_regular_hours': round(total_regular, 2),
            'total_overtime_hours': round(total_overtime, 2),
            'total_hours': round(total_regular + total_overtime, 2),
            'total_labor_cost': round(total_cost, 2),
            'entry_count': len(entries),
            'daily_breakdown': dict(daily_breakdown),
        }

    def calculate_overtime(self, worker_id: str, week_start: date = None) -> Dict[str, Any]:
        """Calculate overtime for a worker's week."""
        week_start = self._parse_date(week_start) if week_start else (date.today() - timedelta(days=date.today().weekday()))
        week_end = week_start + timedelta(days=6)

        from models.mes.labor import Worker as WorkerModel, TimeEntry as TimeEntryModel

        worker = self.session.query(WorkerModel).filter(
            WorkerModel.employee_id == worker_id
        ).first()

        if not worker:
            return {
                'worker_id': worker_id,
                'week_start': str(week_start),
                'week_end': str(week_end),
                'total_hours': 0,
                'weekly_threshold': self._overtime_rules['weekly_threshold'],
                'regular_hours': 0,
                'overtime_hours': 0,
                'overtime_rate': self._overtime_rules['overtime_multiplier'],
            }

        entries = self.session.query(TimeEntryModel).filter(
            TimeEntryModel.worker_id == worker.id,
            TimeEntryModel.clock_in >= datetime.combine(week_start, datetime.min.time()),
            TimeEntryModel.clock_in <= datetime.combine(week_end, datetime.max.time()),
        ).all()

        total_hours = sum((e.regular_hours or 0) + (e.overtime_hours or 0) for e in entries)
        weekly_threshold = self._overtime_rules['weekly_threshold']

        if total_hours <= weekly_threshold:
            weekly_regular = total_hours
            weekly_overtime = 0
        else:
            weekly_regular = weekly_threshold
            weekly_overtime = total_hours - weekly_threshold

        return {
            'worker_id': worker_id,
            'week_start': str(week_start),
            'week_end': str(week_end),
            'total_hours': round(total_hours, 2),
            'weekly_threshold': weekly_threshold,
            'regular_hours': round(weekly_regular, 2),
            'overtime_hours': round(weekly_overtime, 2),
            'overtime_rate': self._overtime_rules['overtime_multiplier'],
        }

    def allocate_labor_cost(self, job_id: str, hourly_rate: float = None) -> Dict[str, Any]:
        """Allocate labor cost to a job. Uses eager-loaded worker data (no N+1)."""
        from models.mes.labor import TimeEntry as TimeEntryModel, ActiveClockSession
        from sqlalchemy.orm import joinedload

        # Query DB entries where notes contain the job_id string, with worker eager-loaded
        entries = self.session.query(TimeEntryModel).options(
            joinedload(TimeEntryModel.worker)
        ).filter(
            TimeEntryModel.notes.contains(job_id)
        ).all()

        total_hours = 0
        total_cost = 0
        by_worker: Dict[str, Dict[str, float]] = defaultdict(lambda: {'hours': 0, 'cost': 0})

        for e in entries:
            hours = (e.regular_hours or 0) + (e.overtime_hours or 0)
            worker = e.worker
            emp_id = worker.employee_id if worker else str(e.worker_id)
            rate = hourly_rate or (worker.hourly_rate if worker and worker.hourly_rate else 25.0)
            cost = (e.regular_hours or 0) * rate + (e.overtime_hours or 0) * rate * self._overtime_rules['overtime_multiplier']

            total_hours += hours
            total_cost += cost
            by_worker[emp_id]['hours'] += hours
            by_worker[emp_id]['cost'] += cost

        # Also include currently active workers on this job (from DB sessions)
        active_hours = 0
        active_sessions = self.session.query(ActiveClockSession).options(
            joinedload(ActiveClockSession.worker)
        ).filter(
            ActiveClockSession.job_id == job_id
        ).all()

        for s in active_sessions:
            hours = (datetime.utcnow() - s.clock_in).total_seconds() / 3600
            active_hours += hours
            rate = hourly_rate or (s.worker.hourly_rate if s.worker and s.worker.hourly_rate else 25.0)
            by_worker[s.employee_id]['hours'] += hours
            by_worker[s.employee_id]['cost'] += hours * rate

        return {
            'job_id': job_id,
            'completed_entries': len(entries),
            'total_labor_hours': round(total_hours + active_hours, 2),
            'total_labor_cost': round(total_cost + active_hours * (hourly_rate or 25.0), 2),
            'by_worker': {k: {'hours': round(v['hours'], 2), 'cost': round(v['cost'], 2)}
                          for k, v in by_worker.items()},
        }

    # =========================================================================
    # Skill Matrix & Certifications
    # =========================================================================

    def register_worker(self, worker_id: str, name: str, department: str,
                        hire_date: date, hourly_rate: float,
                        primary_machines: List[str] = None) -> WorkerProfile:
        """Register a new worker profile."""
        from models.mes.labor import Worker as WorkerModel

        # Create or update DB Worker
        worker = self.session.query(WorkerModel).filter(
            WorkerModel.employee_id == worker_id
        ).first()
        if not worker:
            worker = WorkerModel(
                employee_id=worker_id,
                first_name=name.split()[0] if name else worker_id,
                last_name=' '.join(name.split()[1:]) if name and len(name.split()) > 1 else '',
                department=department,
                hire_date=hire_date,
                hourly_rate=hourly_rate,
            )
            self.session.add(worker)
            self.session.flush()
        else:
            worker.first_name = name.split()[0] if name else worker_id
            worker.last_name = ' '.join(name.split()[1:]) if name and len(name.split()) > 1 else ''
            worker.department = department
            worker.hire_date = hire_date
            worker.hourly_rate = hourly_rate
            self.session.flush()

        return WorkerProfile(
            worker_id=worker_id,
            name=name,
            department=department,
            hire_date=hire_date,
            hourly_rate=hourly_rate,
            primary_machines=primary_machines or [],
        )

    def get_worker_profile(self, worker_id: str) -> Optional[WorkerProfile]:
        """Get a worker's profile. Checks DB first, falls back to in-memory."""
        from models.mes.labor import Worker as WorkerModel

        worker = self.session.query(WorkerModel).filter(
            WorkerModel.employee_id == worker_id
        ).first()

        if worker:
            return WorkerProfile(
                worker_id=worker.employee_id,
                name=f"{worker.first_name} {worker.last_name}".strip(),
                department=worker.department or 'Unknown',
                hire_date=worker.hire_date or date.today(),
                hourly_rate=worker.hourly_rate or 25.0,
            )

        return None

    def add_skill(self, worker_id: str, skill_id: str, skill_name: str,
                  level: int, required_for_machines: List[str] = None) -> WorkerSkill:
        """Add or update a skill for a worker. Persists to DB."""
        from models.mes.labor import Worker as WorkerModel, Skill as SkillModel, worker_skills as ws_table
        from models.mes.labor import SkillLevel as DBSkillLevel

        # Map int level to DB SkillLevel enum
        level_map = {1: DBSkillLevel.TRAINEE, 2: DBSkillLevel.BASIC, 3: DBSkillLevel.INTERMEDIATE,
                     4: DBSkillLevel.ADVANCED, 5: DBSkillLevel.EXPERT}
        db_level = level_map.get(level, DBSkillLevel.BASIC)

        # Find or create the Skill row
        skill_row = self.session.query(SkillModel).filter(
            SkillModel.skill_code == skill_id
        ).first()
        if not skill_row:
            skill_row = SkillModel(
                skill_code=skill_id,
                name=skill_name,
                category='manufacturing',
                equipment_types=required_for_machines or [],
            )
            self.session.add(skill_row)
            self.session.flush()

        # Find the worker
        worker_db = self._resolve_worker(worker_id)

        # Upsert into worker_skills association table
        existing = self.session.execute(
            ws_table.select().where(
                (ws_table.c.worker_id == worker_db.id) &
                (ws_table.c.skill_id == skill_row.id)
            )
        ).first()

        if existing:
            self.session.execute(
                ws_table.update().where(
                    (ws_table.c.worker_id == worker_db.id) &
                    (ws_table.c.skill_id == skill_row.id)
                ).values(level=db_level, certified_date=date.today())
            )
        else:
            self.session.execute(
                ws_table.insert().values(
                    worker_id=worker_db.id,
                    skill_id=skill_row.id,
                    level=db_level,
                    certified_date=date.today(),
                )
            )
        self.session.flush()

        # Return the in-memory dataclass for backward compat
        skill = WorkerSkill(
            worker_id=worker_id,
            skill_id=skill_id,
            skill_name=skill_name,
            level=SkillLevel(level),
            acquired_date=date.today(),
            required_for_machines=required_for_machines or [],
        )

        return skill

    def get_skill_matrix(self, department: str = None) -> Dict[str, Any]:
        """Get skill matrix for workers from DB."""
        from models.mes.labor import Worker as WorkerModel, Skill as SkillModel, worker_skills
        from sqlalchemy.orm import joinedload

        query = self.session.query(WorkerModel).options(joinedload(WorkerModel.skills))
        if department:
            query = query.filter(WorkerModel.department == department)
        workers = query.all()

        all_skills: Set[str] = set()
        for w in workers:
            for s in w.skills:
                all_skills.add(s.skill_code)

        matrix = []
        for w in workers:
            worker_skill_codes = {s.skill_code for s in w.skills}
            row = {
                'worker_id': w.employee_id,
                'name': f"{w.first_name} {w.last_name}",
                'department': w.department,
                'skills': {},
            }
            for skill_code in all_skills:
                row['skills'][skill_code] = 1 if skill_code in worker_skill_codes else 0
            matrix.append(row)

        return {
            'skill_columns': sorted(list(all_skills)),
            'workers': matrix,
            'department_filter': department,
        }

    def add_certification(self, worker_id: str, certification_type: str,
                          certification_name: str, issued_date: date,
                          expiry_date: date, issuing_authority: str,
                          credential_number: str = '') -> Certification:
        """Add a certification for a worker. Persists to Worker.certifications JSON."""
        cert = Certification(
            cert_id=f"CERT-{uuid.uuid4().hex[:8].upper()}",
            worker_id=worker_id,
            certification_type=certification_type,
            certification_name=certification_name,
            issued_date=issued_date,
            expiry_date=expiry_date,
            issuing_authority=issuing_authority,
            credential_number=credential_number,
        )

        if cert.is_expired():
            cert.status = CertificationStatus.EXPIRED
        elif cert.is_expiring_soon():
            cert.status = CertificationStatus.EXPIRING_SOON

        # Persist to Worker.certifications JSON column
        worker_db = self._resolve_worker(worker_id)
        certs = list(worker_db.certifications or [])
        # Remove existing cert with same cert_id if updating
        certs = [c for c in certs if c.get('cert_id') != cert.cert_id]
        certs.append({
            'cert_id': cert.cert_id,
            'certification_type': certification_type,
            'certification_name': certification_name,
            'issued_date': str(issued_date),
            'expiry_date': str(expiry_date),
            'issuing_authority': issuing_authority,
            'credential_number': credential_number,
            'status': cert.status.value,
        })
        worker_db.certifications = certs
        self.session.flush()

        return cert

    def _load_certifications_from_db(self) -> List[tuple]:
        """Load all certifications from Worker.certifications JSON columns.
        Returns list of (worker, cert_dict) tuples."""
        from models.mes.labor import Worker as WorkerModel
        workers = self.session.query(WorkerModel).filter(
            WorkerModel.certifications != None
        ).all()
        results = []
        for w in workers:
            for c in (w.certifications or []):
                results.append((w, c))
        return results

    def get_expiring_certifications(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get certifications expiring within specified days."""
        expiring = []
        today = date.today()

        for worker, c in self._load_certifications_from_db():
            exp_date = self._parse_date(c.get('expiry_date', '2099-12-31'))
            days_until = (exp_date - today).days
            if days_until <= days:
                status = 'expired' if days_until < 0 else ('expiring_soon' if days_until <= 30 else 'active')
                expiring.append({
                    'cert_id': c.get('cert_id', ''),
                    'worker_id': worker.employee_id,
                    'worker_name': f"{worker.first_name} {worker.last_name}".strip(),
                    'certification_type': c.get('certification_type', ''),
                    'certification_name': c.get('certification_name', ''),
                    'expiry_date': str(exp_date),
                    'days_until_expiry': days_until,
                    'status': status,
                    'issuing_authority': c.get('issuing_authority', ''),
                })

        return sorted(expiring, key=lambda x: x['days_until_expiry'])

    def get_training_alerts(self) -> List[Dict[str, Any]]:
        """Get training requirement alerts for expiring certifications."""
        alerts = []
        today = date.today()

        for worker, c in self._load_certifications_from_db():
            exp_date = self._parse_date(c.get('expiry_date', '2099-12-31'))
            days_remaining = (exp_date - today).days
            if days_remaining <= 60:
                urgency = 'critical' if days_remaining <= 14 else (
                    'high' if days_remaining <= 30 else 'medium'
                )
                cert_name = c.get('certification_name', '')
                alerts.append({
                    'alert_type': 'certification_expiring',
                    'urgency': urgency,
                    'worker_id': worker.employee_id,
                    'worker_name': f"{worker.first_name} {worker.last_name}".strip(),
                    'certification': cert_name,
                    'expiry_date': str(exp_date),
                    'days_remaining': days_remaining,
                    'action_required': f'Schedule recertification for {cert_name}',
                })

        return sorted(alerts, key=lambda x: (
            0 if x['urgency'] == 'critical' else (1 if x['urgency'] == 'high' else 2)
        ))

    # =========================================================================
    # Labor Efficiency
    # =========================================================================

    def calculate_labor_efficiency(self, worker_id: str, skill_id: str = None,
                                    days: int = 30) -> LaborEfficiency:
        """Calculate labor efficiency for a worker."""
        from models.mes.labor import Worker as WorkerModel, TimeEntry as TimeEntryModel

        start_date = date.today() - timedelta(days=days)

        worker = self.session.query(WorkerModel).filter(
            WorkerModel.employee_id == worker_id
        ).first()

        total_hours = 0
        if worker:
            entries = self.session.query(TimeEntryModel).filter(
                TimeEntryModel.worker_id == worker.id,
                TimeEntryModel.clock_in >= datetime.combine(start_date, datetime.min.time()),
            ).all()
            total_hours = sum((e.regular_hours or 0) + (e.overtime_hours or 0) for e in entries)

        productive_hours = total_hours * 0.85  # Assume 85% productive
        efficiency_pct = (productive_hours / total_hours * 100) if total_hours > 0 else 0

        return LaborEfficiency(
            worker_id=worker_id,
            skill_id=skill_id or 'all',
            period_start=start_date,
            period_end=date.today(),
            total_hours=round(total_hours, 2),
            productive_hours=round(productive_hours, 2),
            efficiency_pct=round(efficiency_pct, 1),
            units_produced=0,  # Would come from production data
            units_per_hour=0,
            quality_score=0,
            benchmark_comparison=1.0,
        )

    def get_efficiency_by_skill(self, skill_id: str, days: int = 30) -> Dict[str, Any]:
        """Get efficiency comparison across workers for a skill."""
        from models.mes.labor import Worker as WorkerModel, Skill as SkillModel, worker_skills
        from sqlalchemy.orm import joinedload

        # Find workers who have this skill
        workers_with_skill = (
            self.session.query(WorkerModel)
            .join(worker_skills, WorkerModel.id == worker_skills.c.worker_id)
            .join(SkillModel, SkillModel.id == worker_skills.c.skill_id)
            .filter(SkillModel.skill_code == skill_id)
            .all()
        )

        efficiencies = []
        for w in workers_with_skill:
            eff = self.calculate_labor_efficiency(w.employee_id, skill_id, days)
            efficiencies.append({
                'worker_id': w.employee_id,
                'worker_name': f"{w.first_name} {w.last_name}",
                'skill_level': 3,  # Default intermediate
                'total_hours': eff.total_hours,
                'efficiency_pct': eff.efficiency_pct,
            })

        avg_efficiency = (statistics.mean(e['efficiency_pct'] for e in efficiencies)
                          if efficiencies else 0)

        return {
            'skill_id': skill_id,
            'period_days': days,
            'workers': sorted(efficiencies, key=lambda x: x['efficiency_pct'], reverse=True),
            'average_efficiency': round(avg_efficiency, 1),
            'top_performer': efficiencies[0]['worker_id'] if efficiencies else None,
        }

    # =========================================================================
    # Cross-Training Recommendations
    # =========================================================================

    def set_skill_requirement(self, machine_id: str, required_skills: List[str]):
        """Set skill requirements for a machine."""
        self._skill_requirements[machine_id] = required_skills

    def get_cross_training_recommendations(self, department: str = None,
                                            max_recommendations: int = 10) -> List[CrossTrainingRecommendation]:
        """Generate cross-training recommendations based on skill coverage gaps."""
        from models.mes.labor import Worker as WorkerModel
        from sqlalchemy.orm import joinedload

        recommendations = []

        query = self.session.query(WorkerModel).options(joinedload(WorkerModel.skills))
        if department:
            query = query.filter(WorkerModel.department == department)
        workers = query.all()

        # Build skill coverage map: skill_code -> [employee_ids]
        skill_coverage = defaultdict(list)
        for w in workers:
            for s in w.skills:
                skill_coverage[s.skill_code].append(w.employee_id)

        # Find single-point-of-failure skills
        for skill_code, worker_ids in skill_coverage.items():
            if len(worker_ids) == 1:
                single_point = worker_ids[0]
                single_worker = next(w for w in workers if w.employee_id == single_point)
                candidates = [
                    w for w in workers
                    if w.employee_id != single_point
                    and w.department == single_worker.department
                ]

                if candidates:
                    skill_name = self._get_skill_name(skill_code)
                    recommendations.append(CrossTrainingRecommendation(
                        worker_id=candidates[0].employee_id,
                        skill_id=skill_code,
                        skill_name=skill_name,
                        priority=2,
                        reason=f'Single point of failure - only {single_point} has this skill',
                        estimated_training_hours=24,
                        business_impact='medium',
                        prerequisite_skills=[],
                    ))

        # Check machine skill requirements
        for machine_id, required_skills in self._skill_requirements.items():
            for skill_id in required_skills:
                qualified_workers = skill_coverage.get(skill_id, [])
                if len(qualified_workers) < 2:
                    candidates = [
                        w for w in workers
                        if w.employee_id not in qualified_workers
                    ]
                    for candidate in candidates[:2]:
                        skill_name = self._get_skill_name(skill_id)
                        recommendations.append(CrossTrainingRecommendation(
                            worker_id=candidate.employee_id,
                            skill_id=skill_id,
                            skill_name=skill_name,
                            priority=1 if len(qualified_workers) == 0 else 2,
                            reason=f'Only {len(qualified_workers)} worker(s) qualified for {machine_id}',
                            estimated_training_hours=40,
                            business_impact='high' if len(qualified_workers) == 0 else 'medium',
                            prerequisite_skills=[],
                        ))

        return sorted(recommendations, key=lambda x: x.priority)[:max_recommendations]

    def _get_skill_name(self, skill_id: str) -> str:
        """Get skill name from ID. Checks DB first."""
        from models.mes.labor import Skill as SkillModel
        skill_row = self.session.query(SkillModel).filter(
            SkillModel.skill_code == skill_id
        ).first()
        if skill_row:
            return skill_row.name
        return skill_id

    def get_skill_gap_analysis(self, machine_id: str) -> Dict[str, Any]:
        """Analyze skill gaps for a machine."""
        from models.mes.labor import Worker as WorkerModel, Skill as SkillModel, worker_skills

        required_skills = self._skill_requirements.get(machine_id, [])

        gaps = []
        for skill_id in required_skills:
            # Find workers who have this skill
            qualified_workers = (
                self.session.query(WorkerModel)
                .join(worker_skills, WorkerModel.id == worker_skills.c.worker_id)
                .join(SkillModel, SkillModel.id == worker_skills.c.skill_id)
                .filter(SkillModel.skill_code == skill_id)
                .all()
            )

            qualified = [
                {
                    'worker_id': w.employee_id,
                    'name': f"{w.first_name} {w.last_name}",
                    'level': 3,  # Default intermediate
                }
                for w in qualified_workers
            ]

            gaps.append({
                'skill_id': skill_id,
                'skill_name': self._get_skill_name(skill_id),
                'required_level': SkillLevel.INTERMEDIATE.value,
                'qualified_count': len(qualified),
                'qualified_workers': qualified,
                'is_gap': len(qualified) < 2,
                'gap_severity': 'critical' if len(qualified) == 0 else (
                    'high' if len(qualified) == 1 else 'none'
                ),
            })

        return {
            'machine_id': machine_id,
            'required_skills': required_skills,
            'skill_gaps': gaps,
            'total_gaps': len([g for g in gaps if g['is_gap']]),
            'critical_gaps': len([g for g in gaps if g['gap_severity'] == 'critical']),
        }

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_labor_summary(self, start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Get labor summary report. Uses eager-loaded worker data (no N+1)."""
        start_date = self._parse_date(start_date) if start_date else (date.today() - timedelta(days=7))
        end_date = self._parse_date(end_date) if end_date else date.today()

        from models.mes.labor import TimeEntry as TimeEntryModel
        from sqlalchemy.orm import joinedload

        entries = self.session.query(TimeEntryModel).options(
            joinedload(TimeEntryModel.worker)
        ).filter(
            TimeEntryModel.clock_in >= datetime.combine(start_date, datetime.min.time()),
            TimeEntryModel.clock_in <= datetime.combine(end_date, datetime.max.time()),
        ).all()

        total_regular = sum(e.regular_hours or 0 for e in entries)
        total_overtime = sum(e.overtime_hours or 0 for e in entries)

        by_department: Dict[str, Dict[str, Any]] = defaultdict(lambda: {'hours': 0, 'cost': 0, 'workers': set()})
        total_cost = 0

        for entry in entries:
            worker = entry.worker
            dept = worker.department if worker and worker.department else 'Unknown'
            emp_id = worker.employee_id if worker else str(entry.worker_id)
            rate = worker.hourly_rate if worker and worker.hourly_rate else 25.0

            entry_cost = (
                (entry.regular_hours or 0) * rate +
                (entry.overtime_hours or 0) * rate * self._overtime_rules['overtime_multiplier']
            )
            total_cost += entry_cost

            hours = (entry.regular_hours or 0) + (entry.overtime_hours or 0)
            by_department[dept]['hours'] += hours
            by_department[dept]['cost'] += entry_cost
            by_department[dept]['workers'].add(emp_id)

        unique_workers = set()
        for dept_data in by_department.values():
            unique_workers.update(dept_data['workers'])

        return {
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_regular_hours': round(total_regular, 2),
            'total_overtime_hours': round(total_overtime, 2),
            'total_hours': round(total_regular + total_overtime, 2),
            'total_labor_cost': round(total_cost, 2),
            'entry_count': len(entries),
            'unique_workers': len(unique_workers),
            'overtime_pct': round(total_overtime / (total_regular + total_overtime) * 100, 1)
            if (total_regular + total_overtime) > 0 else 0,
            'by_department': {
                k: {'hours': round(v['hours'], 2), 'cost': round(v['cost'], 2), 'workers': len(v['workers'])}
                for k, v in by_department.items()
            },
        }
