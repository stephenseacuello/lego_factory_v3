"""
LEGO Factory v3 - Labor Service
================================
MESA-11 Labor Management service with skill validation.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from services.websocket import emit_event


class SkillLevel(str, Enum):
    """Worker skill proficiency levels."""
    TRAINEE = 'trainee'
    BASIC = 'basic'
    INTERMEDIATE = 'intermediate'
    ADVANCED = 'advanced'
    EXPERT = 'expert'


# Skill level numeric values for comparison
SKILL_LEVEL_VALUES = {
    SkillLevel.TRAINEE: 1,
    SkillLevel.BASIC: 2,
    SkillLevel.INTERMEDIATE: 3,
    SkillLevel.ADVANCED: 4,
    SkillLevel.EXPERT: 5,
}


class LaborService:
    """Labor management service with skill validation."""

    def __init__(self, session: Session):
        self.session = session
        self._workers = self._load_workers()
        self._skills = self._load_skills()
        self._shifts = self._load_shifts()

    def _load_workers(self) -> Dict[str, Dict[str, Any]]:
        """Load worker data (from database or config)."""
        # In production, this would load from database
        # For now, using sample data
        return {
            'W001': {
                'id': 'W001',
                'name': 'John Smith',
                'department': 'Production',
                'role': 'Operator',
                'hire_date': '2022-01-15',
                'skills': {
                    'fdm_printing': {'level': SkillLevel.EXPERT, 'certified_date': '2022-03-01', 'expiry_date': '2025-03-01'},
                    'sla_printing': {'level': SkillLevel.ADVANCED, 'certified_date': '2022-06-15', 'expiry_date': '2025-06-15'},
                    'cnc_milling': {'level': SkillLevel.BASIC, 'certified_date': '2023-01-10', 'expiry_date': '2026-01-10'},
                    'quality_inspection': {'level': SkillLevel.INTERMEDIATE, 'certified_date': '2022-09-01', 'expiry_date': '2025-09-01'},
                },
                'shift': 'day',
                'active': True,
            },
            'W002': {
                'id': 'W002',
                'name': 'Sarah Johnson',
                'department': 'Production',
                'role': 'Senior Operator',
                'hire_date': '2020-05-20',
                'skills': {
                    'fdm_printing': {'level': SkillLevel.EXPERT, 'certified_date': '2020-08-01', 'expiry_date': '2025-08-01'},
                    'sla_printing': {'level': SkillLevel.EXPERT, 'certified_date': '2020-10-15', 'expiry_date': '2025-10-15'},
                    'cnc_milling': {'level': SkillLevel.ADVANCED, 'certified_date': '2021-03-01', 'expiry_date': '2024-03-01'},
                    'laser_cutting': {'level': SkillLevel.INTERMEDIATE, 'certified_date': '2022-01-15', 'expiry_date': '2025-01-15'},
                    'assembly': {'level': SkillLevel.EXPERT, 'certified_date': '2020-07-01', 'expiry_date': '2025-07-01'},
                },
                'shift': 'day',
                'active': True,
            },
            'W003': {
                'id': 'W003',
                'name': 'Mike Chen',
                'department': 'Production',
                'role': 'Operator',
                'hire_date': '2023-03-10',
                'skills': {
                    'fdm_printing': {'level': SkillLevel.INTERMEDIATE, 'certified_date': '2023-06-01', 'expiry_date': '2026-06-01'},
                    'assembly': {'level': SkillLevel.BASIC, 'certified_date': '2023-04-15', 'expiry_date': '2026-04-15'},
                },
                'shift': 'evening',
                'active': True,
            },
            'W004': {
                'id': 'W004',
                'name': 'Emily Davis',
                'department': 'Quality',
                'role': 'Quality Inspector',
                'hire_date': '2021-08-01',
                'skills': {
                    'quality_inspection': {'level': SkillLevel.EXPERT, 'certified_date': '2021-11-01', 'expiry_date': '2024-11-01'},
                    'spc_analysis': {'level': SkillLevel.ADVANCED, 'certified_date': '2022-02-01', 'expiry_date': '2025-02-01'},
                    'metrology': {'level': SkillLevel.EXPERT, 'certified_date': '2021-12-01', 'expiry_date': '2024-12-01'},
                },
                'shift': 'day',
                'active': True,
            },
            'W005': {
                'id': 'W005',
                'name': 'Tom Wilson',
                'department': 'Maintenance',
                'role': 'Maintenance Technician',
                'hire_date': '2019-11-15',
                'skills': {
                    'machine_maintenance': {'level': SkillLevel.EXPERT, 'certified_date': '2020-02-01', 'expiry_date': '2025-02-01'},
                    'electrical_systems': {'level': SkillLevel.ADVANCED, 'certified_date': '2020-04-01', 'expiry_date': '2025-04-01'},
                    'calibration': {'level': SkillLevel.INTERMEDIATE, 'certified_date': '2021-01-15', 'expiry_date': '2024-01-15'},
                },
                'shift': 'day',
                'active': True,
            },
            'W006': {
                'id': 'W006',
                'name': 'Lisa Brown',
                'department': 'Production',
                'role': 'Operator',
                'hire_date': '2022-09-01',
                'skills': {
                    'fdm_printing': {'level': SkillLevel.BASIC, 'certified_date': '2022-12-01', 'expiry_date': '2025-12-01'},
                    'laser_cutting': {'level': SkillLevel.TRAINEE, 'certified_date': '2023-06-01', 'expiry_date': '2026-06-01'},
                },
                'shift': 'evening',
                'active': True,
            },
            'W007': {
                'id': 'W007',
                'name': 'James Lee',
                'department': 'Production',
                'role': 'CNC Specialist',
                'hire_date': '2018-06-01',
                'skills': {
                    'cnc_milling': {'level': SkillLevel.EXPERT, 'certified_date': '2018-09-01', 'expiry_date': '2025-09-01'},
                    'cnc_programming': {'level': SkillLevel.EXPERT, 'certified_date': '2019-01-01', 'expiry_date': '2025-01-01'},
                    'quality_inspection': {'level': SkillLevel.INTERMEDIATE, 'certified_date': '2020-03-01', 'expiry_date': '2025-03-01'},
                },
                'shift': 'night',
                'active': True,
            },
            'W008': {
                'id': 'W008',
                'name': 'Anna Martinez',
                'department': 'Production',
                'role': 'Shift Supervisor',
                'hire_date': '2017-02-15',
                'skills': {
                    'fdm_printing': {'level': SkillLevel.EXPERT, 'certified_date': '2017-05-01', 'expiry_date': '2025-05-01'},
                    'sla_printing': {'level': SkillLevel.ADVANCED, 'certified_date': '2018-01-01', 'expiry_date': '2025-01-01'},
                    'cnc_milling': {'level': SkillLevel.INTERMEDIATE, 'certified_date': '2019-06-01', 'expiry_date': '2025-06-01'},
                    'supervision': {'level': SkillLevel.EXPERT, 'certified_date': '2019-01-01', 'expiry_date': None},
                },
                'shift': 'day',
                'active': True,
            },
        }

    def _load_skills(self) -> Dict[str, Dict[str, Any]]:
        """Load skill definitions."""
        return {
            'fdm_printing': {
                'name': 'FDM 3D Printing',
                'category': 'Manufacturing',
                'description': 'Operation of FDM printers (Prusa, Bambu)',
                'training_hours': 16,
                'certification_validity_months': 36,
            },
            'sla_printing': {
                'name': 'SLA 3D Printing',
                'category': 'Manufacturing',
                'description': 'Operation of SLA printers (Formlabs)',
                'training_hours': 24,
                'certification_validity_months': 36,
            },
            'cnc_milling': {
                'name': 'CNC Milling',
                'category': 'Manufacturing',
                'description': 'CNC mill operation (Bantam, Nomad)',
                'training_hours': 40,
                'certification_validity_months': 36,
            },
            'cnc_programming': {
                'name': 'CNC Programming',
                'category': 'Manufacturing',
                'description': 'G-code programming and CAM',
                'training_hours': 80,
                'certification_validity_months': 36,
            },
            'laser_cutting': {
                'name': 'Laser Cutting',
                'category': 'Manufacturing',
                'description': 'Laser cutter operation (K40, Emblaser)',
                'training_hours': 20,
                'certification_validity_months': 36,
            },
            'assembly': {
                'name': 'Assembly Operations',
                'category': 'Manufacturing',
                'description': 'Manual assembly and packaging',
                'training_hours': 8,
                'certification_validity_months': 36,
            },
            'quality_inspection': {
                'name': 'Quality Inspection',
                'category': 'Quality',
                'description': 'Product inspection and measurement',
                'training_hours': 24,
                'certification_validity_months': 36,
            },
            'spc_analysis': {
                'name': 'SPC Analysis',
                'category': 'Quality',
                'description': 'Statistical process control',
                'training_hours': 16,
                'certification_validity_months': 36,
            },
            'metrology': {
                'name': 'Metrology',
                'category': 'Quality',
                'description': 'Precision measurement techniques',
                'training_hours': 32,
                'certification_validity_months': 36,
            },
            'machine_maintenance': {
                'name': 'Machine Maintenance',
                'category': 'Maintenance',
                'description': 'Equipment maintenance and repair',
                'training_hours': 40,
                'certification_validity_months': 36,
            },
            'electrical_systems': {
                'name': 'Electrical Systems',
                'category': 'Maintenance',
                'description': 'Electrical troubleshooting',
                'training_hours': 48,
                'certification_validity_months': 36,
            },
            'calibration': {
                'name': 'Calibration',
                'category': 'Quality',
                'description': 'Equipment calibration',
                'training_hours': 24,
                'certification_validity_months': 36,
            },
            'supervision': {
                'name': 'Supervision',
                'category': 'Management',
                'description': 'Shift supervision',
                'training_hours': 40,
                'certification_validity_months': None,
            },
        }

    def _load_shifts(self) -> Dict[str, Dict[str, Any]]:
        """Load shift definitions."""
        return {
            'day': {
                'name': 'Day Shift',
                'start': '06:00',
                'end': '14:00',
                'hours': 8,
            },
            'evening': {
                'name': 'Evening Shift',
                'start': '14:00',
                'end': '22:00',
                'hours': 8,
            },
            'night': {
                'name': 'Night Shift',
                'start': '22:00',
                'end': '06:00',
                'hours': 8,
            },
        }

    # Operation skill requirements mapping
    OPERATION_SKILL_REQUIREMENTS = {
        'fdm_print': {'skill': 'fdm_printing', 'min_level': SkillLevel.BASIC},
        'sla_print': {'skill': 'sla_printing', 'min_level': SkillLevel.BASIC},
        'cnc_mill': {'skill': 'cnc_milling', 'min_level': SkillLevel.INTERMEDIATE},
        'laser_cut': {'skill': 'laser_cutting', 'min_level': SkillLevel.BASIC},
        'assembly': {'skill': 'assembly', 'min_level': SkillLevel.BASIC},
        'inspection': {'skill': 'quality_inspection', 'min_level': SkillLevel.INTERMEDIATE},
    }

    def assign_worker(
        self,
        worker_id: str,
        job_id: str,
        operation_type: str = None,
        required_skills: List[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate and assign a worker to a job.

        Args:
            worker_id: Worker ID
            job_id: Job ID
            operation_type: Type of operation requiring assignment
            required_skills: List of required skill IDs

        Returns:
            Tuple of (success, rejection_reason)
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return False, f"Worker {worker_id} not found"

        if not worker['active']:
            return False, f"Worker {worker_id} is not active"

        # Check shift coverage
        current_shift = self._get_current_shift()
        if worker['shift'] != current_shift:
            return False, f"Worker {worker_id} is not on current shift ({current_shift})"

        # Check skill requirements
        if operation_type:
            req = self.OPERATION_SKILL_REQUIREMENTS.get(operation_type)
            if req:
                skill_check = self._check_worker_skill(
                    worker,
                    req['skill'],
                    req['min_level'],
                )
                if not skill_check[0]:
                    return False, skill_check[1]

        if required_skills:
            for skill_id in required_skills:
                skill_check = self._check_worker_skill(worker, skill_id)
                if not skill_check[0]:
                    return False, skill_check[1]

        # Emit assignment event
        emit_event('worker_assigned', {
            'worker_id': worker_id,
            'worker_name': worker['name'],
            'job_id': job_id,
            'operation_type': operation_type,
        }, namespace='/mes')

        return True, None

    def _check_worker_skill(
        self,
        worker: Dict[str, Any],
        skill_id: str,
        min_level: SkillLevel = SkillLevel.BASIC,
    ) -> Tuple[bool, Optional[str]]:
        """Check if worker has required skill at required level."""
        worker_skills = worker.get('skills', {})

        if skill_id not in worker_skills:
            return False, f"Worker lacks required skill: {skill_id}"

        skill = worker_skills[skill_id]
        skill_level = skill.get('level')

        # Check level
        if SKILL_LEVEL_VALUES.get(skill_level, 0) < SKILL_LEVEL_VALUES.get(min_level, 0):
            return False, f"Worker skill level ({skill_level.value}) below required ({min_level.value})"

        # Check certification expiry
        expiry_date = skill.get('expiry_date')
        if expiry_date:
            expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            if expiry < date.today():
                return False, f"Worker certification for {skill_id} expired on {expiry_date}"

        return True, None

    def _get_current_shift(self) -> str:
        """Determine current shift based on time."""
        now = datetime.now().time()

        for shift_id, shift in self._shifts.items():
            start = datetime.strptime(shift['start'], '%H:%M').time()
            end = datetime.strptime(shift['end'], '%H:%M').time()

            if start < end:
                if start <= now < end:
                    return shift_id
            else:  # Night shift crosses midnight
                if now >= start or now < end:
                    return shift_id

        return 'day'  # Default

    def get_skill_matrix(self) -> Dict[str, Any]:
        """
        Get workers × skills matrix with proficiency levels.

        Returns:
            Skill matrix data for visualization
        """
        workers_list = []
        skills_list = list(self._skills.keys())

        for worker_id, worker in self._workers.items():
            if not worker['active']:
                continue

            worker_skills = {}
            for skill_id in skills_list:
                worker_skill = worker.get('skills', {}).get(skill_id)
                if worker_skill:
                    # Check if expired
                    expiry = worker_skill.get('expiry_date')
                    is_expired = False
                    if expiry:
                        expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                        is_expired = expiry_date < date.today()

                    worker_skills[skill_id] = {
                        'level': worker_skill['level'].value,
                        'level_value': SKILL_LEVEL_VALUES[worker_skill['level']],
                        'expiry_date': expiry,
                        'is_expired': is_expired,
                    }
                else:
                    worker_skills[skill_id] = None

            workers_list.append({
                'id': worker_id,
                'name': worker['name'],
                'department': worker['department'],
                'skills': worker_skills,
            })

        return {
            'workers': workers_list,
            'skills': [
                {
                    'id': skill_id,
                    'name': skill['name'],
                    'category': skill['category'],
                }
                for skill_id, skill in self._skills.items()
            ],
            'levels': [
                {'id': level.value, 'value': value}
                for level, value in SKILL_LEVEL_VALUES.items()
            ],
        }

    def calculate_labor_efficiency(
        self,
        worker_id: str = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate labor efficiency (actual hours / standard hours).

        This would integrate with actual job completion data in production.
        """
        # Sample efficiency data
        efficiencies = {
            'W001': {'actual_hours': 156, 'standard_hours': 160, 'efficiency': 97.5},
            'W002': {'actual_hours': 158, 'standard_hours': 160, 'efficiency': 98.8},
            'W003': {'actual_hours': 144, 'standard_hours': 160, 'efficiency': 90.0},
            'W004': {'actual_hours': 152, 'standard_hours': 160, 'efficiency': 95.0},
            'W005': {'actual_hours': 160, 'standard_hours': 160, 'efficiency': 100.0},
            'W006': {'actual_hours': 140, 'standard_hours': 160, 'efficiency': 87.5},
            'W007': {'actual_hours': 155, 'standard_hours': 160, 'efficiency': 96.9},
            'W008': {'actual_hours': 162, 'standard_hours': 160, 'efficiency': 101.3},
        }

        if worker_id:
            worker = self._workers.get(worker_id)
            eff = efficiencies.get(worker_id, {})
            return {
                'worker_id': worker_id,
                'worker_name': worker['name'] if worker else 'Unknown',
                **eff,
            }

        result = []
        for wid, eff in efficiencies.items():
            worker = self._workers.get(wid)
            if worker and worker['active']:
                result.append({
                    'worker_id': wid,
                    'worker_name': worker['name'],
                    **eff,
                })

        avg_efficiency = sum(e['efficiency'] for e in result) / len(result) if result else 0

        return {
            'workers': result,
            'average_efficiency': round(avg_efficiency, 1),
            'period_days': days,
        }

    def get_shift_coverage(
        self,
        target_date: date = None,
        shift: str = None,
    ) -> Dict[str, Any]:
        """
        Get shift coverage - workers available vs required per work center.

        Args:
            target_date: Date to check (defaults to today)
            shift: Specific shift to check (defaults to current)

        Returns:
            Coverage analysis
        """
        if target_date is None:
            target_date = date.today()
        if shift is None:
            shift = self._get_current_shift()

        # Work center requirements
        work_center_requirements = {
            'fdm_printing': {'required': 2, 'skill': 'fdm_printing'},
            'sla_printing': {'required': 1, 'skill': 'sla_printing'},
            'cnc_milling': {'required': 1, 'skill': 'cnc_milling'},
            'laser_cutting': {'required': 1, 'skill': 'laser_cutting'},
            'assembly': {'required': 2, 'skill': 'assembly'},
            'quality': {'required': 1, 'skill': 'quality_inspection'},
        }

        # Get available workers for shift
        available_workers = [
            w for w in self._workers.values()
            if w['active'] and w['shift'] == shift
        ]

        coverage = {}
        for wc_id, req in work_center_requirements.items():
            qualified_workers = []
            for worker in available_workers:
                skill_check = self._check_worker_skill(worker, req['skill'])
                if skill_check[0]:
                    qualified_workers.append({
                        'id': worker['id'],
                        'name': worker['name'],
                        'skill_level': worker['skills'][req['skill']]['level'].value,
                    })

            coverage[wc_id] = {
                'required': req['required'],
                'available': len(qualified_workers),
                'coverage_percent': min(100, len(qualified_workers) / req['required'] * 100) if req['required'] > 0 else 100,
                'workers': qualified_workers,
                'understaffed': len(qualified_workers) < req['required'],
            }

        total_required = sum(wc['required'] for wc in coverage.values())
        total_available = sum(min(wc['available'], wc['required']) for wc in coverage.values())

        return {
            'date': target_date.isoformat(),
            'shift': shift,
            'shift_name': self._shifts[shift]['name'],
            'work_centers': coverage,
            'total_workers_on_shift': len(available_workers),
            'overall_coverage_percent': (total_available / total_required * 100) if total_required > 0 else 100,
            'has_gaps': any(wc['understaffed'] for wc in coverage.values()),
        }

    def track_training_gap(
        self,
        worker_id: str = None,
    ) -> Dict[str, Any]:
        """
        Identify skills needed but not certified or expiring soon.

        Args:
            worker_id: Specific worker (or all if None)

        Returns:
            Training gap analysis
        """
        gaps = []
        expiring_soon = []
        today = date.today()
        warning_date = today + timedelta(days=90)

        workers_to_check = [self._workers[worker_id]] if worker_id else self._workers.values()

        for worker in workers_to_check:
            if not worker['active']:
                continue

            worker_gaps = []
            worker_expiring = []

            for skill_id, skill in worker.get('skills', {}).items():
                expiry = skill.get('expiry_date')
                if expiry:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()

                    if expiry_date < today:
                        worker_gaps.append({
                            'skill_id': skill_id,
                            'skill_name': self._skills[skill_id]['name'],
                            'expired_date': expiry,
                            'days_expired': (today - expiry_date).days,
                        })
                    elif expiry_date < warning_date:
                        worker_expiring.append({
                            'skill_id': skill_id,
                            'skill_name': self._skills[skill_id]['name'],
                            'expiry_date': expiry,
                            'days_until_expiry': (expiry_date - today).days,
                        })

            if worker_gaps or worker_expiring:
                gaps.append({
                    'worker_id': worker['id'],
                    'worker_name': worker['name'],
                    'expired_certifications': worker_gaps,
                    'expiring_soon': worker_expiring,
                })

        # Sort by urgency
        gaps.sort(key=lambda x: len(x['expired_certifications']), reverse=True)

        return {
            'workers_with_gaps': len(gaps),
            'total_expired': sum(len(g['expired_certifications']) for g in gaps),
            'total_expiring_soon': sum(len(g['expiring_soon']) for g in gaps),
            'details': gaps,
        }

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get worker details."""
        worker = self._workers.get(worker_id)
        if not worker:
            return None

        return {
            **worker,
            'skills': {
                skill_id: {
                    **skill,
                    'skill_name': self._skills.get(skill_id, {}).get('name', skill_id),
                    'level': skill['level'].value,
                }
                for skill_id, skill in worker.get('skills', {}).items()
            },
        }

    def get_all_workers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all workers."""
        workers = []
        for worker_id, worker in self._workers.items():
            if active_only and not worker['active']:
                continue
            workers.append(self.get_worker(worker_id))
        return workers


# Export convenience function
def create_labor_service(session: Session) -> LaborService:
    """Create a labor service instance."""
    return LaborService(session)
