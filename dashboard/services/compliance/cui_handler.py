"""
CUI (Controlled Unclassified Information) Handler

Implements CUI marking, handling, and protection requirements
per 32 CFR Part 2002 and NIST SP 800-171.

Reference: CUI Registry, NARA CUI Program, DFARS 252.204-7012
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
import hashlib
import re
import json

logger = logging.getLogger(__name__)


class CUICategory(Enum):
    """CUI Categories per NARA Registry."""
    # Defense Categories
    CTI = "Controlled Technical Information"
    NNPI = "Naval Nuclear Propulsion Information"
    UCNI = "Unclassified Controlled Nuclear Information"
    EXPT = "Export Controlled"
    
    # Critical Infrastructure
    CRIT = "Critical Infrastructure"
    PCII = "Protected Critical Infrastructure Information"
    
    # Privacy
    PRVCY = "Privacy"
    HLTH = "Health Information"
    
    # Procurement & Acquisition
    PROPIN = "Proprietary Business Information"
    SINFO = "Source Selection Information"
    
    # Legal
    PRIV = "Privileged"
    INTEL = "Intelligence"
    
    # Manufacturing-specific
    ITAR = "ITAR Controlled"
    EAR = "Export Administration Regulations"


class DisseminationControl(Enum):
    """CUI Dissemination Controls."""
    NOFORN = "Not Releasable to Foreign Nationals"
    FEDCON = "Federal Contractors Only"
    NOCON = "No Contractors"
    DL_ONLY = "Dissemination List Only"
    REL_TO = "Authorized for Release To"
    DISPLAY_ONLY = "For Display Only"


class CUIMarking(Enum):
    """CUI Banner/Portion Marking Indicators."""
    CUI = "CUI"
    CUI_BASIC = "CUI//BASIC"
    CUI_SPECIFIED = "CUI//SP"
    CONTROLLED = "CONTROLLED"


@dataclass
class CUIDocument:
    """Represents a CUI-marked document or data asset."""
    document_id: str
    title: str
    categories: List[CUICategory]
    marking: CUIMarking
    dissemination_controls: List[DisseminationControl] = field(default_factory=list)
    authorized_holders: List[str] = field(default_factory=list)
    decontrol_date: Optional[str] = None
    originator: str = ""
    created_date: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_accessed: Optional[str] = None
    access_log: List[Dict[str, Any]] = field(default_factory=list)
    hash_value: Optional[str] = None

    def get_banner_marking(self) -> str:
        """Generate full banner marking string."""
        parts = [self.marking.value]
        
        # Add category abbreviations
        if self.categories:
            cat_abbrevs = [c.name for c in self.categories]
            parts.append("-".join(cat_abbrevs))
        
        # Add dissemination controls
        if self.dissemination_controls:
            ctrl_abbrevs = [d.name for d in self.dissemination_controls]
            parts.append("//" + "/".join(ctrl_abbrevs))
        
        return "".join(parts)

    def get_portion_marking(self) -> str:
        """Generate portion marking (for inline use)."""
        if self.marking == CUIMarking.CUI_SPECIFIED:
            return f"(CUI//{'-'.join(c.name for c in self.categories[:2])})"
        return "(CUI)"


@dataclass
class AccessDecision:
    """Result of an access control decision."""
    allowed: bool
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    user_id: str = ""
    document_id: str = ""
    categories_checked: List[str] = field(default_factory=list)
    dissemination_checked: List[str] = field(default_factory=list)


class CUIHandler:
    """
    CUI Handling and Protection Manager.

    Implements CUI marking, access control, and handling
    requirements per federal regulations.

    Usage:
        >>> handler = CUIHandler()
        >>> doc = handler.create_cui_document(
        ...     title="Design Specs",
        ...     categories=[CUICategory.CTI],
        ...     marking=CUIMarking.CUI_SPECIFIED
        ... )
        >>> handler.check_access(doc, user_id="user123")
    """

    # Category to required clearance/access mapping
    CATEGORY_REQUIREMENTS = {
        CUICategory.CTI: {"need_to_know": True, "clearance": None, "training": "CUI-CTI"},
        CUICategory.NNPI: {"need_to_know": True, "clearance": "SECRET", "training": "NNPI"},
        CUICategory.ITAR: {"need_to_know": True, "clearance": None, "training": "ITAR", "us_person": True},
        CUICategory.EAR: {"need_to_know": True, "clearance": None, "training": "EAR"},
        CUICategory.PRVCY: {"need_to_know": True, "clearance": None, "training": "Privacy"},
        CUICategory.PROPIN: {"need_to_know": True, "clearance": None, "training": "CUI-Basic"},
        CUICategory.SINFO: {"need_to_know": True, "clearance": None, "training": "Procurement"},
        CUICategory.CRIT: {"need_to_know": True, "clearance": None, "training": "CI"},
    }

    def __init__(self):
        self.documents: Dict[str, CUIDocument] = {}
        self.user_authorizations: Dict[str, Dict[str, Any]] = {}
        self.access_log: List[AccessDecision] = []
        logger.info("CUIHandler initialized")

    def register_user_authorization(
        self,
        user_id: str,
        categories: List[CUICategory],
        clearance: Optional[str] = None,
        training_completed: List[str] = None,
        is_us_person: bool = True,
        need_to_know_projects: List[str] = None
    ) -> None:
        """Register user's CUI access authorizations."""
        self.user_authorizations[user_id] = {
            "categories": [c.name for c in categories],
            "clearance": clearance,
            "training": training_completed or [],
            "us_person": is_us_person,
            "need_to_know": need_to_know_projects or [],
            "registered_date": datetime.utcnow().isoformat() + "Z"
        }
        logger.info(f"User {user_id} registered for CUI access")

    def create_cui_document(
        self,
        title: str,
        categories: List[CUICategory],
        marking: CUIMarking,
        content: Optional[bytes] = None,
        dissemination_controls: List[DisseminationControl] = None,
        authorized_holders: List[str] = None,
        originator: str = "",
        decontrol_date: Optional[str] = None
    ) -> CUIDocument:
        """Create and register a new CUI document."""
        doc_id = hashlib.sha256(
            f"{title}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        # Calculate content hash if provided
        content_hash = None
        if content:
            content_hash = hashlib.sha256(content).hexdigest()

        document = CUIDocument(
            document_id=doc_id,
            title=title,
            categories=categories,
            marking=marking,
            dissemination_controls=dissemination_controls or [],
            authorized_holders=authorized_holders or [],
            originator=originator,
            decontrol_date=decontrol_date,
            hash_value=content_hash
        )

        self.documents[doc_id] = document
        logger.info(
            f"CUI document created: {doc_id} "
            f"[{document.get_banner_marking()}]"
        )

        return document

    def check_access(
        self,
        document: CUIDocument,
        user_id: str,
        project_id: Optional[str] = None,
        access_type: str = "read"
    ) -> AccessDecision:
        """
        Check if user is authorized to access CUI document.

        Implements multi-layer access control:
        1. User registration check
        2. Category authorization
        3. Dissemination control verification
        4. Need-to-know validation
        5. Training requirements
        6. US Person requirement (ITAR)
        """
        decision = AccessDecision(
            allowed=False,
            reason="",
            user_id=user_id,
            document_id=document.document_id
        )

        # Check if user is registered
        if user_id not in self.user_authorizations:
            decision.reason = "User not registered for CUI access"
            self._log_access(decision)
            return decision

        user_auth = self.user_authorizations[user_id]

        # Check category authorization
        for category in document.categories:
            decision.categories_checked.append(category.name)
            
            if category.name not in user_auth["categories"]:
                decision.reason = f"User not authorized for category: {category.name}"
                self._log_access(decision)
                return decision

            # Check category-specific requirements
            requirements = self.CATEGORY_REQUIREMENTS.get(category, {})

            # Check US Person requirement
            if requirements.get("us_person") and not user_auth.get("us_person"):
                decision.reason = f"US Person required for {category.name}"
                self._log_access(decision)
                return decision

            # Check clearance
            if requirements.get("clearance"):
                if user_auth.get("clearance") != requirements["clearance"]:
                    decision.reason = f"Clearance {requirements['clearance']} required"
                    self._log_access(decision)
                    return decision

            # Check training
            if requirements.get("training"):
                if requirements["training"] not in user_auth.get("training", []):
                    decision.reason = f"Training required: {requirements['training']}"
                    self._log_access(decision)
                    return decision

        # Check dissemination controls
        for control in document.dissemination_controls:
            decision.dissemination_checked.append(control.name)

            if control == DisseminationControl.NOFORN:
                if not user_auth.get("us_person"):
                    decision.reason = "NOFORN: Not releasable to foreign nationals"
                    self._log_access(decision)
                    return decision

            elif control == DisseminationControl.NOCON:
                # Check if user is a contractor
                if user_auth.get("contractor"):
                    decision.reason = "NOCON: Not releasable to contractors"
                    self._log_access(decision)
                    return decision

            elif control == DisseminationControl.DL_ONLY:
                if user_id not in document.authorized_holders:
                    decision.reason = "DL_ONLY: Not on dissemination list"
                    self._log_access(decision)
                    return decision

        # Check need-to-know
        if project_id:
            if project_id not in user_auth.get("need_to_know", []):
                decision.reason = "Need-to-know not established for project"
                self._log_access(decision)
                return decision

        # All checks passed
        decision.allowed = True
        decision.reason = "Access authorized"
        self._log_access(decision)

        # Update document access record
        document.last_accessed = datetime.utcnow().isoformat() + "Z"
        document.access_log.append({
            "user_id": user_id,
            "access_type": access_type,
            "timestamp": decision.timestamp
        })

        return decision

    def _log_access(self, decision: AccessDecision) -> None:
        """Log access decision for audit."""
        self.access_log.append(decision)
        log_level = logging.INFO if decision.allowed else logging.WARNING
        logger.log(
            log_level,
            f"CUI Access: user={decision.user_id}, "
            f"doc={decision.document_id}, "
            f"allowed={decision.allowed}, "
            f"reason={decision.reason}"
        )

    def generate_marking_string(
        self,
        categories: List[CUICategory],
        specified: bool = True,
        controls: List[DisseminationControl] = None
    ) -> str:
        """Generate proper CUI marking string."""
        if not categories:
            return "CUI"

        parts = ["CUI"]

        if specified:
            parts.append("//SP")
            cat_abbrevs = "-".join(c.name for c in categories[:3])
            parts.append(f"-{cat_abbrevs}")

        if controls:
            ctrl_str = "/".join(c.name for c in controls)
            parts.append(f"//{ctrl_str}")

        return "".join(parts)

    def apply_document_marking(
        self,
        content: str,
        document: CUIDocument
    ) -> str:
        """Apply CUI markings to document content."""
        banner = document.get_banner_marking()
        portion = document.get_portion_marking()

        # Header/Footer marking
        header = f"""
{'=' * 60}
{banner}
{'=' * 60}
"""
        footer = f"""
{'=' * 60}
{banner}
Controlled by: {document.originator or 'LEGO MCP Manufacturing'}
CUI Category: {', '.join(c.value for c in document.categories)}
{'Decontrol Date: ' + document.decontrol_date if document.decontrol_date else ''}
{'=' * 60}
"""
        return header + content + footer

    def sanitize_for_export(
        self,
        document: CUIDocument,
        target_classification: str = "UNCLASSIFIED"
    ) -> Dict[str, Any]:
        """
        Prepare document metadata for external transmission.
        
        Removes sensitive handling details while preserving
        necessary classification markings.
        """
        return {
            "document_id": document.document_id,
            "classification": target_classification,
            "cui_marking": document.get_banner_marking(),
            "categories": [c.name for c in document.categories],
            "handling_required": True,
            "export_controlled": any(
                c in (CUICategory.ITAR, CUICategory.EAR, CUICategory.EXPT)
                for c in document.categories
            ),
            "sanitized_date": datetime.utcnow().isoformat() + "Z",
            "warning": "This document contains CUI. Handle IAW CUI Program requirements."
        }

    def get_handling_instructions(
        self,
        categories: List[CUICategory]
    ) -> Dict[str, Any]:
        """Get handling instructions for CUI categories."""
        instructions = {
            "storage": [],
            "transmission": [],
            "destruction": [],
            "marking": [],
            "reporting": []
        }

        for category in categories:
            if category in (CUICategory.CTI, CUICategory.ITAR):
                instructions["storage"].extend([
                    "Store in locked container when not in use",
                    "Encrypt at rest using FIPS 140-2 validated module",
                    "Access controlled facility required"
                ])
                instructions["transmission"].extend([
                    "Encrypt in transit using approved methods",
                    "No transmission to foreign nationals without authorization"
                ])
                instructions["destruction"].extend([
                    "Cross-cut shred (NSA/CSS EPL-listed device)",
                    "Degauss and physically destroy electronic media"
                ])

            if category == CUICategory.ITAR:
                instructions["marking"].append(
                    "Include ITAR warning: 'This document contains ITAR-controlled data'"
                )
                instructions["reporting"].append(
                    "Report unauthorized disclosures to DDTC"
                )

            if category == CUICategory.PRVCY:
                instructions["storage"].append(
                    "Minimize retention per Privacy Act requirements"
                )
                instructions["transmission"].append(
                    "PII protection required per NIST 800-122"
                )

        # Deduplicate
        for key in instructions:
            instructions[key] = list(set(instructions[key]))

        return instructions

    def generate_audit_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate CUI access audit report."""
        filtered_log = self.access_log

        if start_date:
            filtered_log = [
                d for d in filtered_log
                if d.timestamp >= start_date
            ]
        if end_date:
            filtered_log = [
                d for d in filtered_log
                if d.timestamp <= end_date
            ]

        denied_access = [d for d in filtered_log if not d.allowed]
        
        return {
            "report_type": "CUI Access Audit",
            "generated": datetime.utcnow().isoformat() + "Z",
            "period": {
                "start": start_date or "beginning",
                "end": end_date or "present"
            },
            "total_access_attempts": len(filtered_log),
            "successful_access": len(filtered_log) - len(denied_access),
            "denied_access": len(denied_access),
            "denial_reasons": self._aggregate_denial_reasons(denied_access),
            "documents_accessed": len(set(d.document_id for d in filtered_log)),
            "unique_users": len(set(d.user_id for d in filtered_log)),
            "denied_attempts": [
                {
                    "user_id": d.user_id,
                    "document_id": d.document_id,
                    "timestamp": d.timestamp,
                    "reason": d.reason
                }
                for d in denied_access
            ]
        }

    def _aggregate_denial_reasons(
        self,
        denied: List[AccessDecision]
    ) -> Dict[str, int]:
        """Aggregate denial reasons for reporting."""
        reasons: Dict[str, int] = {}
        for d in denied:
            reason_key = d.reason.split(":")[0] if ":" in d.reason else d.reason
            reasons[reason_key] = reasons.get(reason_key, 0) + 1
        return reasons
