"""
Access Control for DoD/Federal Compliance

Implements multi-level access control with clearance levels,
need-to-know, and ITAR/export control requirements.

Reference: NIST 800-171 3.1, ITAR 22 CFR 120-130, EAR 15 CFR 730-774
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class ClearanceLevel(Enum):
    """Security clearance levels."""
    UNCLEARED = 0
    CONFIDENTIAL = 1
    SECRET = 2
    TOP_SECRET = 3
    TOP_SECRET_SCI = 4


class NeedToKnow(Enum):
    """Need-to-know access basis."""
    NONE = "none"
    PROJECT = "project"
    PROGRAM = "program"
    COMPARTMENT = "compartment"
    SPECIAL_ACCESS = "special_access"


class ExportControlRegime(Enum):
    """Export control regulatory regime."""
    ITAR = "ITAR"           # International Traffic in Arms Regulations
    EAR = "EAR"             # Export Administration Regulations
    MTCR = "MTCR"           # Missile Technology Control Regime
    NONE = "NONE"


class CitizenshipStatus(Enum):
    """Citizenship/person status for export control."""
    US_CITIZEN = "us_citizen"
    US_PERMANENT_RESIDENT = "us_permanent_resident"
    US_PROTECTED_PERSON = "us_protected_person"  # Asylee/Refugee
    FOREIGN_NATIONAL = "foreign_national"
    DUAL_CITIZEN = "dual_citizen"


@dataclass
class UserCredentials:
    """User security credentials and authorizations."""
    user_id: str
    clearance: ClearanceLevel = ClearanceLevel.UNCLEARED
    citizenship: CitizenshipStatus = CitizenshipStatus.FOREIGN_NATIONAL
    nationality: str = ""
    cleared_date: Optional[str] = None
    clearance_sponsor: str = ""
    
    # Need-to-know authorizations
    authorized_projects: List[str] = field(default_factory=list)
    authorized_programs: List[str] = field(default_factory=list)
    authorized_compartments: List[str] = field(default_factory=list)
    
    # Export control authorizations
    itar_authorized: bool = False
    itar_categories: List[str] = field(default_factory=list)
    ear_authorized: bool = False
    ear_eccns: List[str] = field(default_factory=list)
    
    # Training/certifications
    cui_training_date: Optional[str] = None
    itar_training_date: Optional[str] = None
    security_training_date: Optional[str] = None
    
    # Status
    active: bool = True
    last_verification: Optional[str] = None

    def is_us_person(self) -> bool:
        """Check if user qualifies as US Person per ITAR."""
        return self.citizenship in (
            CitizenshipStatus.US_CITIZEN,
            CitizenshipStatus.US_PERMANENT_RESIDENT,
            CitizenshipStatus.US_PROTECTED_PERSON
        )

    def has_valid_clearance(self) -> bool:
        """Check if clearance is valid and current."""
        if self.clearance == ClearanceLevel.UNCLEARED:
            return False
        if not self.cleared_date:
            return False
        # Could add expiration check here
        return self.active


@dataclass
class ResourceClassification:
    """Classification and access requirements for a resource."""
    resource_id: str
    resource_type: str
    classification: ClearanceLevel = ClearanceLevel.UNCLEARED
    
    # Access requirements
    required_projects: List[str] = field(default_factory=list)
    required_programs: List[str] = field(default_factory=list)
    required_compartments: List[str] = field(default_factory=list)
    
    # Export control
    export_controlled: bool = False
    export_regime: ExportControlRegime = ExportControlRegime.NONE
    itar_categories: List[str] = field(default_factory=list)
    ear_eccn: Optional[str] = None
    us_person_required: bool = False
    
    # CUI marking
    cui_categories: List[str] = field(default_factory=list)
    dissemination_controls: List[str] = field(default_factory=list)


@dataclass
class AccessDecision:
    """Access control decision result."""
    allowed: bool
    reason: str
    user_id: str
    resource_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    clearance_checked: bool = False
    ntk_checked: bool = False
    export_checked: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class AccessController:
    """
    Multi-Level Access Controller.

    Implements comprehensive access control for:
    - Security clearance verification
    - Need-to-know determination
    - ITAR/EAR export control compliance
    - CUI access authorization

    Reference: NIST 800-171 3.1, ITAR, EAR

    Usage:
        >>> controller = AccessController()
        >>> controller.register_user(user_creds)
        >>> decision = controller.check_access(user_id, resource)
    """

    # ITAR Categories (USML)
    ITAR_CATEGORIES = {
        "I": "Firearms",
        "II": "Guns and Armament",
        "III": "Ammunition/Ordnance",
        "IV": "Launch Vehicles, Guided Missiles",
        "V": "Explosives",
        "VI": "Surface Vessels of War",
        "VII": "Ground Vehicles",
        "VIII": "Aircraft",
        "IX": "Military Training Equipment",
        "X": "Personal Protective Equipment",
        "XI": "Military Electronics",
        "XII": "Fire Control, Optics",
        "XIII": "Materials",
        "XIV": "Toxicological Agents",
        "XV": "Spacecraft Systems",
        "XVI": "Nuclear Weapons",
        "XVII": "Classified Articles",
        "XVIII": "Directed Energy Weapons",
        "XIX": "Gas Turbine Engines",
        "XX": "Submersible Vessels",
        "XXI": "Technical Data",
    }

    # EAR Control classifications
    EAR_CONTROLS = {
        "0": "Nuclear Materials",
        "1": "Materials, Chemicals",
        "2": "Materials Processing",
        "3": "Electronics",
        "4": "Computers",
        "5": "Telecommunications",
        "6": "Sensors and Lasers",
        "7": "Navigation and Avionics",
        "8": "Marine",
        "9": "Aerospace and Propulsion",
    }

    def __init__(self):
        self.users: Dict[str, UserCredentials] = {}
        self.resources: Dict[str, ResourceClassification] = {}
        self.access_log: List[AccessDecision] = []
        self._decision_handlers: List[Callable[[AccessDecision], None]] = []
        logger.info("AccessController initialized")

    def register_user(self, credentials: UserCredentials) -> bool:
        """Register user credentials."""
        self.users[credentials.user_id] = credentials
        logger.info(
            f"User registered: {credentials.user_id}, "
            f"clearance={credentials.clearance.name}, "
            f"us_person={credentials.is_us_person()}"
        )
        return True

    def register_resource(self, resource: ResourceClassification) -> bool:
        """Register resource classification."""
        self.resources[resource.resource_id] = resource
        logger.info(
            f"Resource registered: {resource.resource_id}, "
            f"classification={resource.classification.name}, "
            f"export_controlled={resource.export_controlled}"
        )
        return True

    def check_access(
        self,
        user_id: str,
        resource_id: str,
        action: str = "read"
    ) -> AccessDecision:
        """
        Comprehensive access check.

        Evaluates:
        1. User registration and status
        2. Security clearance level
        3. Need-to-know authorization
        4. Export control compliance (ITAR/EAR)
        5. CUI handling authorization
        """
        decision = AccessDecision(
            allowed=False,
            reason="",
            user_id=user_id,
            resource_id=resource_id
        )

        # Check user exists and is active
        if user_id not in self.users:
            decision.reason = "User not registered"
            self._log_decision(decision)
            return decision

        user = self.users[user_id]
        if not user.active:
            decision.reason = "User account inactive"
            self._log_decision(decision)
            return decision

        # Check resource exists
        if resource_id not in self.resources:
            decision.reason = "Resource not registered"
            self._log_decision(decision)
            return decision

        resource = self.resources[resource_id]

        # 1. Check clearance level
        decision.clearance_checked = True
        if user.clearance.value < resource.classification.value:
            decision.reason = (
                f"Insufficient clearance: has {user.clearance.name}, "
                f"requires {resource.classification.name}"
            )
            decision.details["clearance_gap"] = (
                resource.classification.value - user.clearance.value
            )
            self._log_decision(decision)
            return decision

        # 2. Check need-to-know
        decision.ntk_checked = True
        ntk_result = self._check_need_to_know(user, resource)
        if not ntk_result[0]:
            decision.reason = ntk_result[1]
            self._log_decision(decision)
            return decision

        # 3. Check export control
        decision.export_checked = True
        if resource.export_controlled:
            export_result = self._check_export_control(user, resource)
            if not export_result[0]:
                decision.reason = export_result[1]
                decision.details["export_violation"] = True
                self._log_decision(decision)
                return decision

        # All checks passed
        decision.allowed = True
        decision.reason = "Access authorized"
        decision.details = {
            "clearance": user.clearance.name,
            "resource_classification": resource.classification.name,
            "export_regime": resource.export_regime.value if resource.export_controlled else None
        }
        self._log_decision(decision)
        return decision

    def _check_need_to_know(
        self,
        user: UserCredentials,
        resource: ResourceClassification
    ) -> Tuple[bool, str]:
        """Check need-to-know authorization."""
        # Check compartment access
        for compartment in resource.required_compartments:
            if compartment not in user.authorized_compartments:
                return False, f"Missing compartment access: {compartment}"

        # Check program access
        for program in resource.required_programs:
            if program not in user.authorized_programs:
                return False, f"Missing program access: {program}"

        # Check project access
        for project in resource.required_projects:
            if project not in user.authorized_projects:
                return False, f"Missing project access: {project}"

        return True, "Need-to-know verified"

    def _check_export_control(
        self,
        user: UserCredentials,
        resource: ResourceClassification
    ) -> Tuple[bool, str]:
        """Check export control compliance."""
        # Check US Person requirement
        if resource.us_person_required and not user.is_us_person():
            return False, (
                f"US Person required for {resource.export_regime.value} "
                f"controlled data (user is {user.citizenship.value})"
            )

        # Check ITAR
        if resource.export_regime == ExportControlRegime.ITAR:
            if not user.itar_authorized:
                return False, "User not ITAR authorized"

            # Check specific ITAR categories
            for category in resource.itar_categories:
                if category not in user.itar_categories:
                    return False, f"Missing ITAR category authorization: Category {category}"

            # Check ITAR training
            if not user.itar_training_date:
                return False, "ITAR training not completed"

        # Check EAR
        if resource.export_regime == ExportControlRegime.EAR:
            if not user.ear_authorized:
                return False, "User not EAR authorized"

            # Check ECCN authorization
            if resource.ear_eccn and resource.ear_eccn not in user.ear_eccns:
                return False, f"Missing ECCN authorization: {resource.ear_eccn}"

        return True, "Export control verified"

    def check_itar_export(
        self,
        user_id: str,
        categories: List[str],
        destination_country: str
    ) -> AccessDecision:
        """
        Check ITAR export authorization.

        Implements ITAR 22 CFR 120-130 requirements.
        """
        decision = AccessDecision(
            allowed=False,
            reason="",
            user_id=user_id,
            resource_id=f"ITAR_EXPORT_{destination_country}"
        )

        if user_id not in self.users:
            decision.reason = "User not registered"
            return decision

        user = self.users[user_id]

        # Embargoed countries (simplified list)
        EMBARGOED = {"KP", "IR", "CU", "SY", "BY", "RU", "VE", "MM"}
        if destination_country in EMBARGOED:
            decision.reason = f"Export prohibited to {destination_country} (ITAR embargo)"
            return decision

        # Check US Person
        if not user.is_us_person():
            decision.reason = "ITAR export requires US Person"
            return decision

        # Check ITAR authorization
        if not user.itar_authorized:
            decision.reason = "User not ITAR authorized"
            return decision

        # Check categories
        for cat in categories:
            if cat not in user.itar_categories:
                decision.reason = f"Not authorized for ITAR Category {cat}"
                return decision

        # Check for required licenses
        decision.allowed = True
        decision.reason = (
            f"ITAR export may proceed with appropriate license to {destination_country}"
        )
        decision.details = {
            "categories": categories,
            "destination": destination_country,
            "license_required": True,
            "warning": "Verify DSP-5 or TAA is in place before actual export"
        }
        return decision

    def _log_decision(self, decision: AccessDecision) -> None:
        """Log access decision."""
        self.access_log.append(decision)
        
        log_level = logging.INFO if decision.allowed else logging.WARNING
        logger.log(
            log_level,
            f"Access decision: user={decision.user_id}, "
            f"resource={decision.resource_id}, "
            f"allowed={decision.allowed}, "
            f"reason={decision.reason}"
        )

        # Trigger handlers
        for handler in self._decision_handlers:
            try:
                handler(decision)
            except Exception as e:
                logger.error(f"Decision handler failed: {e}")

    def register_decision_handler(
        self,
        handler: Callable[[AccessDecision], None]
    ) -> None:
        """Register handler for access decisions."""
        self._decision_handlers.append(handler)

    def grant_project_access(
        self,
        user_id: str,
        project_id: str,
        grantor_id: str
    ) -> bool:
        """Grant project-level need-to-know."""
        if user_id not in self.users:
            return False

        user = self.users[user_id]
        if project_id not in user.authorized_projects:
            user.authorized_projects.append(project_id)
            logger.info(f"Project access granted: {user_id} -> {project_id} by {grantor_id}")
        return True

    def revoke_project_access(
        self,
        user_id: str,
        project_id: str,
        revoker_id: str
    ) -> bool:
        """Revoke project-level need-to-know."""
        if user_id not in self.users:
            return False

        user = self.users[user_id]
        if project_id in user.authorized_projects:
            user.authorized_projects.remove(project_id)
            logger.info(f"Project access revoked: {user_id} -X- {project_id} by {revoker_id}")
        return True

    def verify_clearance(
        self,
        user_id: str,
        verifier_id: str
    ) -> Dict[str, Any]:
        """Verify and update user clearance status."""
        if user_id not in self.users:
            return {"verified": False, "reason": "User not found"}

        user = self.users[user_id]
        user.last_verification = datetime.utcnow().isoformat() + "Z"

        return {
            "verified": True,
            "user_id": user_id,
            "clearance": user.clearance.name,
            "is_us_person": user.is_us_person(),
            "itar_authorized": user.itar_authorized,
            "verified_by": verifier_id,
            "verified_at": user.last_verification
        }

    def generate_access_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate access control audit report."""
        decisions = self.access_log

        if start_date:
            decisions = [d for d in decisions if d.timestamp >= start_date]
        if end_date:
            decisions = [d for d in decisions if d.timestamp <= end_date]

        denied = [d for d in decisions if not d.allowed]
        export_violations = [d for d in denied if d.details.get("export_violation")]

        return {
            "report_type": "Access Control Audit",
            "generated": datetime.utcnow().isoformat() + "Z",
            "period": {
                "start": start_date or "beginning",
                "end": end_date or "present"
            },
            "summary": {
                "total_decisions": len(decisions),
                "access_granted": len(decisions) - len(denied),
                "access_denied": len(denied),
                "export_violations": len(export_violations),
                "clearance_checks": sum(1 for d in decisions if d.clearance_checked),
                "ntk_checks": sum(1 for d in decisions if d.ntk_checked),
                "export_checks": sum(1 for d in decisions if d.export_checked)
            },
            "denial_reasons": self._aggregate_denial_reasons(denied),
            "export_violations_detail": [
                {
                    "user_id": d.user_id,
                    "resource_id": d.resource_id,
                    "timestamp": d.timestamp,
                    "reason": d.reason
                }
                for d in export_violations
            ]
        }

    def _aggregate_denial_reasons(
        self,
        denied: List[AccessDecision]
    ) -> Dict[str, int]:
        """Aggregate denial reasons."""
        reasons: Dict[str, int] = {}
        for d in denied:
            key = d.reason.split(":")[0] if ":" in d.reason else d.reason
            reasons[key] = reasons.get(key, 0) + 1
        return reasons


# Factory functions for common configurations
def create_manufacturing_user(
    user_id: str,
    clearance: ClearanceLevel = ClearanceLevel.UNCLEARED,
    is_us_citizen: bool = True,
    projects: Optional[List[str]] = None
) -> UserCredentials:
    """Create user credentials for manufacturing personnel."""
    return UserCredentials(
        user_id=user_id,
        clearance=clearance,
        citizenship=CitizenshipStatus.US_CITIZEN if is_us_citizen else CitizenshipStatus.FOREIGN_NATIONAL,
        authorized_projects=projects or [],
        cui_training_date=datetime.utcnow().isoformat() + "Z"
    )


def create_defense_resource(
    resource_id: str,
    classification: ClearanceLevel,
    itar_categories: Optional[List[str]] = None,
    programs: Optional[List[str]] = None
) -> ResourceClassification:
    """Create resource classification for defense manufacturing."""
    return ResourceClassification(
        resource_id=resource_id,
        resource_type="manufacturing_data",
        classification=classification,
        export_controlled=bool(itar_categories),
        export_regime=ExportControlRegime.ITAR if itar_categories else ExportControlRegime.NONE,
        itar_categories=itar_categories or [],
        us_person_required=bool(itar_categories),
        required_programs=programs or []
    )
