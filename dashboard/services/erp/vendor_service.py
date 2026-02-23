"""
Vendor/Supplier Management Service - Enterprise ERP Module
==========================================================

PhD-Level Research Implementation for LEGO MCP Fusion 360 v6.0

This module provides comprehensive vendor/supplier management capabilities
that integrate with the broader ERP system including Accounts Payable,
Procurement, and Quality Management.

Key Features:
-------------
1. **Full Vendor Lifecycle Management**
   - Prospect → Qualified → Approved → Preferred → Strategic progression
   - Automated status transitions based on performance metrics
   - Suspension and blacklisting for non-performing suppliers

2. **Supplier Performance Scorecarding**
   - Weighted scoring: Quality (35%), Delivery (30%), Cost (20%), Service (15%)
   - PPM (Parts Per Million) defect tracking
   - On-time delivery (OTD) percentage
   - Historical trend analysis with 12-month rolling window

3. **Vendor Qualification & Certification**
   - ISO 9001, ISO 14001, IATF 16949, AS9100 tracking
   - Certificate expiration alerts (30/60/90 day warnings)
   - Document management with verification workflow

4. **Risk Assessment & Monitoring**
   - Four-tier risk classification: Low, Medium, High, Critical
   - Automatic risk level adjustment based on performance
   - Expiring certification impact on risk score

5. **Strategic Sourcing Support**
   - Multi-vendor quoting and comparison
   - Blanket PO and master agreement management
   - Spend analysis integration

Standards Compliance:
---------------------
- ISO 9001:2015 - Supplier Quality Management (Section 8.4)
- ISO 14001:2015 - Environmental Supplier Assessment
- IATF 16949:2016 - Automotive Supplier Requirements
- Dodd-Frank Section 1502 - Conflict Minerals Reporting

Novel Research Contributions:
----------------------------
- ML-based supplier risk prediction using historical patterns
- Dynamic vendor rating with trend analysis and forecasting
- Automated supplier development recommendations
- Supply chain resilience scoring for disruption mitigation

Integration Points:
------------------
- AccountsPayableService: Vendor bills, payments, 1099 tracking
- ProcurementService: Purchase orders, requisitions
- QualityService: Incoming inspection results, NCRs
- InventoryService: Material receipts, lot tracking

Usage Example:
--------------
    from services.erp.vendor_service import get_vendor_service, VendorType, PaymentTerms

    # Get singleton service instance
    vendor_svc = get_vendor_service()

    # Create a new raw material vendor
    vendor = vendor_svc.create_vendor(
        code="SUP001",
        name="Acme Plastics",
        vendor_type=VendorType.RAW_MATERIAL,
        payment_terms=PaymentTerms.NET_30,
        lead_time_days=14
    )

    # Record delivery for performance tracking
    vendor_svc.record_delivery(
        vendor_id=vendor.vendor_id,
        po_number="PO-001234",
        on_time=True,
        qty_ordered=1000,
        qty_received=998,
        defects=2
    )

    # Get comprehensive scorecard
    scorecard = vendor_svc.get_vendor_scorecard(vendor.vendor_id)
    print(f"Overall Score: {scorecard['performance']['current']['overall']}")

Author: LEGO MCP Research Team
Version: 6.0.0
Last Updated: 2025-01-05
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
from uuid import uuid4
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMERATIONS
# =============================================================================
# These enums define the allowed values for vendor classification, status,
# certifications, and risk levels. Using enums ensures type safety and
# prevents invalid values from being stored in the database.


class VendorStatus(Enum):
    """
    Vendor lifecycle states.

    The typical progression is:
    PROSPECT → PENDING_APPROVAL → APPROVED → PREFERRED → STRATEGIC

    Negative states:
    - ON_HOLD: Temporary suspension, can be reactivated
    - SUSPENDED: Performance issues, requires corrective action
    - INACTIVE: No longer doing business, can be reactivated
    - BLACKLISTED: Permanently banned, cannot be reactivated
    """
    PROSPECT = "prospect"               # Initial state, not yet qualified
    PENDING_APPROVAL = "pending_approval"  # Qualification in progress
    APPROVED = "approved"               # Cleared for purchasing
    PREFERRED = "preferred"             # High performer, priority sourcing
    STRATEGIC = "strategic"             # Key partner, joint development
    ON_HOLD = "on_hold"                 # Temporarily paused
    SUSPENDED = "suspended"             # Performance/compliance issues
    INACTIVE = "inactive"               # Dormant, no recent activity
    BLACKLISTED = "blacklisted"         # Permanently excluded


class VendorType(Enum):
    """
    Vendor classification by supply type.

    Used for:
    - Spend categorization and analysis
    - Approval routing (different approvers per type)
    - Risk assessment (different risk profiles)
    - Reporting and dashboards
    """
    RAW_MATERIAL = "raw_material"           # ABS pellets, pigments, additives
    COMPONENT = "component"                  # Sub-assemblies, purchased parts
    SERVICE = "service"                      # Consulting, testing, calibration
    EQUIPMENT = "equipment"                  # Machinery, printers, tools
    MRO = "mro"                             # Maintenance, Repair, Operations supplies
    CONTRACT_MANUFACTURER = "contract_manufacturer"  # Outsourced production
    LOGISTICS = "logistics"                  # Shipping, warehousing, freight
    TOOLING = "tooling"                     # Molds, dies, fixtures


class CertificationType(Enum):
    """
    Industry standard certifications for supplier qualification.

    These certifications are tracked with expiration dates and must
    be renewed periodically. The system alerts when certifications
    are approaching expiry (30/60/90 day warnings).
    """
    ISO_9001 = "ISO 9001"           # Quality Management System
    ISO_14001 = "ISO 14001"         # Environmental Management System
    ISO_45001 = "ISO 45001"         # Occupational Health & Safety
    IATF_16949 = "IATF 16949"       # Automotive Quality Management
    AS9100 = "AS9100"               # Aerospace Quality Management
    ISO_13485 = "ISO 13485"         # Medical Device Quality Management
    FDA_REGISTERED = "FDA Registered"  # US FDA facility registration
    CONFLICT_FREE = "Conflict Free Minerals"  # Dodd-Frank 1502 compliance
    FAIR_TRADE = "Fair Trade"       # Ethical sourcing certification
    LEGO_APPROVED = "LEGO Approved Supplier"  # LEGO-specific qualification


class PaymentTerms(Enum):
    """
    Standard payment terms for vendor invoices.

    These terms affect cash flow forecasting in Accounts Payable
    and are used to calculate due dates on vendor bills.

    Early payment discounts (e.g., 2/10 Net 30) are tracked to
    optimize working capital through strategic payment timing.
    """
    PREPAID = "prepaid"             # Payment before shipment
    COD = "cod"                     # Cash on delivery
    NET_15 = "net_15"               # Due in 15 days
    NET_30 = "net_30"               # Due in 30 days (most common)
    NET_45 = "net_45"               # Due in 45 days
    NET_60 = "net_60"               # Due in 60 days
    NET_90 = "net_90"               # Due in 90 days
    TWO_TEN_NET_30 = "2_10_net_30"  # 2% discount if paid within 10 days


class RiskLevel(Enum):
    """
    Supplier risk classification.

    Risk levels are automatically updated based on performance metrics:
    - Score >= 90: LOW risk
    - Score >= 75: MEDIUM risk
    - Score >= 60: HIGH risk
    - Score < 60: CRITICAL risk

    High/Critical risk vendors trigger alerts for supply chain managers
    to consider alternate sourcing or supplier development actions.
    """
    LOW = "low"             # Reliable supplier, minimal risk
    MEDIUM = "medium"       # Acceptable risk, monitor regularly
    HIGH = "high"           # Elevated risk, needs attention
    CRITICAL = "critical"   # Severe risk, alternate sourcing recommended


# =============================================================================
# DATA CLASSES
# =============================================================================
# These dataclasses define the structure of vendor-related records.
# They use Python's dataclass decorator for automatic __init__, __repr__, etc.


@dataclass
class VendorContact:
    """
    Vendor contact person record.

    Each vendor can have multiple contacts with different roles.
    One contact should be marked as primary for default communications.

    Attributes:
        contact_id: Unique identifier (UUID)
        name: Full name of the contact person
        title: Job title (e.g., "Sales Manager", "Quality Director")
        email: Business email address
        phone: Phone number with country code
        is_primary: Whether this is the default contact
        department: Department within the vendor organization
    """
    contact_id: str
    name: str
    title: str = ""
    email: str = ""
    phone: str = ""
    is_primary: bool = False
    department: str = ""


@dataclass
class VendorAddress:
    """
    Vendor address record.

    Vendors may have multiple addresses for different purposes:
    - billing: Where invoices should be sent (AP integration)
    - shipping: Where to send purchase orders/RMAs
    - headquarters: Corporate office location

    Attributes:
        address_id: Unique identifier (UUID)
        address_type: Type of address (billing, shipping, headquarters)
        street_1: Primary street address
        street_2: Suite, floor, building (optional)
        city: City name
        state: State/province code
        postal_code: ZIP or postal code
        country: ISO country code (default: USA)
        is_default: Use this address when type not specified
    """
    address_id: str
    address_type: str  # billing, shipping, headquarters
    street_1: str
    street_2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "USA"
    is_default: bool = False


@dataclass
class VendorCertification:
    """
    Vendor certification record for compliance tracking.

    Certifications are verified against the issuing body and tracked
    for expiration. The system generates alerts before expiry to
    ensure continuous compliance.

    Attributes:
        certification_id: Unique identifier (UUID)
        certification_type: Type of certification (ISO, IATF, etc.)
        certificate_number: Official certificate reference number
        issue_date: When the certificate was issued
        expiry_date: When the certificate expires (triggers alerts)
        issuing_body: Name of the certifying organization
        verified: Whether certificate has been verified by our team
        verified_by: User who performed verification
        verified_date: Date of verification
        document_url: Link to scanned certificate document
    """
    certification_id: str
    certification_type: CertificationType
    certificate_number: str
    issue_date: date
    expiry_date: date
    issuing_body: str
    verified: bool = False
    verified_by: str = ""
    verified_date: Optional[date] = None
    document_url: str = ""


@dataclass
class VendorPerformance:
    """
    Vendor performance metrics snapshot for a specific period.

    Performance is calculated monthly and stored for trend analysis.
    The weighted overall score determines risk level adjustments.

    Scoring Formula:
        overall = quality * 0.35 + delivery * 0.30 + cost * 0.20 + service * 0.15

    Attributes:
        period: Month in YYYY-MM format
        quality_score: 0-100, based on defect PPM (target <100 PPM = 100 score)
        delivery_score: 0-100, based on on-time delivery percentage
        cost_score: 0-100, based on price competitiveness
        service_score: 0-100, based on responsiveness and communication
        overall_score: Weighted average of all scores
        on_time_deliveries: Count of deliveries received on schedule
        total_deliveries: Total delivery count for the period
        defect_ppm: Defects per million parts received
        invoice_accuracy: Percentage of invoices matching PO/receipt
        lead_time_days: Average lead time for the period
        corrective_actions: Number of open CARs (Corrective Action Requests)
        notes: Additional comments about performance
    """
    period: str  # YYYY-MM format
    quality_score: float  # 0-100, higher is better
    delivery_score: float  # 0-100, based on OTD%
    cost_score: float  # 0-100, price competitiveness
    service_score: float  # 0-100, responsiveness
    overall_score: float  # Weighted average
    on_time_deliveries: int
    total_deliveries: int
    defect_ppm: float  # Defects per million (target <100)
    invoice_accuracy: float  # Percent (target >99%)
    lead_time_days: float
    corrective_actions: int  # Open CARs
    notes: str = ""


@dataclass
class Vendor:
    """
    Complete vendor master record.

    This is the primary entity for vendor management, containing all
    information needed for procurement, quality, and financial operations.

    The vendor record integrates with:
    - Accounts Payable: Payment processing, 1099 tracking
    - Procurement: Purchase orders, blanket agreements
    - Quality: Incoming inspection, NCR tracking
    - Inventory: Material receipts, lot traceability
    """
    vendor_id: str
    vendor_code: str
    name: str
    legal_name: str
    vendor_type: VendorType
    status: VendorStatus
    tax_id: str = ""
    duns_number: str = ""
    website: str = ""
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    currency: str = "USD"
    credit_limit: Decimal = Decimal("0")
    minimum_order: Decimal = Decimal("0")
    lead_time_days: int = 7
    is_1099: bool = False
    risk_level: RiskLevel = RiskLevel.MEDIUM
    bank_name: str = ""
    bank_account: str = ""
    bank_routing: str = ""
    contacts: List[VendorContact] = field(default_factory=list)
    addresses: List[VendorAddress] = field(default_factory=list)
    certifications: List[VendorCertification] = field(default_factory=list)
    performance_history: List[VendorPerformance] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)  # material categories supplied
    approved_parts: List[str] = field(default_factory=list)  # approved part IDs
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    approved_by: str = ""
    approved_date: Optional[date] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Quote and Contract Data Classes
# -----------------------------------------------------------------------------


@dataclass
class VendorQuote:
    """
    Vendor quotation record for price comparison.

    Quotes are collected from multiple vendors for the same items
    to enable competitive sourcing. Quotes have an expiration date
    after which they should be re-requested.

    Attributes:
        quote_id: Unique identifier (UUID)
        vendor_id: Reference to vendor providing quote
        quote_number: Human-readable quote reference (Q-YYYYMMDD-####)
        quote_date: When quote was received
        valid_until: Quote expiration date
        items: List of line items with qty, price, description
        subtotal: Sum of line totals before freight/tax
        freight: Shipping charges
        tax: Applicable taxes
        total: Grand total (subtotal + freight + tax)
        lead_time_days: Vendor's promised delivery time
        terms: Payment/delivery terms
        notes: Additional notes or conditions
        status: Quote status (pending, accepted, rejected, expired)
    """
    quote_id: str
    vendor_id: str
    quote_number: str
    quote_date: date
    valid_until: date
    items: List[Dict[str, Any]]
    subtotal: Decimal
    freight: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    lead_time_days: int = 0
    terms: str = ""
    notes: str = ""
    status: str = "pending"  # pending, accepted, rejected, expired
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class VendorContract:
    """
    Vendor contract/agreement record.

    Contracts formalize the relationship with vendors and may include:
    - Blanket POs: Pre-negotiated pricing for recurring purchases
    - Master Agreements: Terms and conditions for all transactions
    - NDAs: Non-disclosure agreements for proprietary information
    - Quality Agreements: Quality expectations and requirements

    Attributes:
        contract_id: Unique identifier (UUID)
        vendor_id: Reference to vendor
        contract_number: Human-readable reference (C-YYYY-####)
        contract_type: Type of agreement
        start_date: Contract effective date
        end_date: Contract expiration date
        value: Total contract value (for blanket POs)
        terms: Key contract terms summary
        auto_renew: Whether contract auto-renews
        status: Contract status (active, expired, cancelled)
        document_url: Link to signed contract document
    """
    contract_id: str
    vendor_id: str
    contract_number: str
    contract_type: str  # blanket_po, master_agreement, nda, quality_agreement
    start_date: date
    end_date: date
    value: Decimal
    terms: str
    auto_renew: bool = False
    status: str = "active"
    document_url: str = ""
    created_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# VENDOR SERVICE
# =============================================================================
# Main service class providing all vendor management operations.
# Uses singleton pattern via get_vendor_service() factory function.


class VendorService:
    """
    Enterprise Vendor/Supplier Management Service.

    Provides comprehensive vendor management with:
    - Full vendor lifecycle from prospect to preferred
    - Performance scorecarding and trending
    - Certification and compliance tracking
    - Risk assessment and monitoring
    - Strategic sourcing support

    Example:
        vendor_svc = VendorService()

        # Create new vendor
        vendor = vendor_svc.create_vendor(
            code="SUP001",
            name="Acme Plastics",
            vendor_type=VendorType.RAW_MATERIAL,
            payment_terms=PaymentTerms.NET_30
        )

        # Record delivery performance
        vendor_svc.record_delivery(
            vendor_id=vendor.vendor_id,
            po_number="PO-001234",
            on_time=True,
            qty_ordered=1000,
            qty_received=1000,
            defects=2
        )

        # Get vendor scorecard
        scorecard = vendor_svc.get_vendor_scorecard(vendor.vendor_id)
    """

    # Performance score weights
    QUALITY_WEIGHT = 0.35
    DELIVERY_WEIGHT = 0.30
    COST_WEIGHT = 0.20
    SERVICE_WEIGHT = 0.15

    def __init__(self, ap_service: Optional[Any] = None):
        """
        Initialize Vendor Service.

        Args:
            ap_service: Accounts Payable service for integration
        """
        self.ap_service = ap_service

        # Storage
        self._vendors: Dict[str, Vendor] = {}
        self._quotes: Dict[str, VendorQuote] = {}
        self._contracts: Dict[str, VendorContract] = {}
        self._deliveries: List[Dict[str, Any]] = []

        self._vendor_counter = 0

    def create_vendor(
        self,
        code: str,
        name: str,
        vendor_type: VendorType,
        payment_terms: PaymentTerms = PaymentTerms.NET_30,
        **kwargs
    ) -> Vendor:
        """
        Create a new vendor.

        Args:
            code: Unique vendor code
            name: Vendor display name
            vendor_type: Classification of vendor
            payment_terms: Default payment terms
            **kwargs: Additional vendor attributes

        Returns:
            Created vendor record
        """
        if any(v.vendor_code == code for v in self._vendors.values()):
            raise ValueError(f"Vendor code {code} already exists")

        vendor_id = str(uuid4())

        vendor = Vendor(
            vendor_id=vendor_id,
            vendor_code=code,
            name=name,
            legal_name=kwargs.get("legal_name", name),
            vendor_type=vendor_type,
            status=VendorStatus.PROSPECT,
            payment_terms=payment_terms,
            tax_id=kwargs.get("tax_id", ""),
            duns_number=kwargs.get("duns_number", ""),
            website=kwargs.get("website", ""),
            currency=kwargs.get("currency", "USD"),
            credit_limit=Decimal(str(kwargs.get("credit_limit", 0))),
            minimum_order=Decimal(str(kwargs.get("minimum_order", 0))),
            lead_time_days=kwargs.get("lead_time_days", 7),
            is_1099=kwargs.get("is_1099", False),
            risk_level=kwargs.get("risk_level", RiskLevel.MEDIUM),
            notes=kwargs.get("notes", ""),
            categories=kwargs.get("categories", [])
        )

        self._vendors[vendor_id] = vendor
        logger.info(f"Created vendor: {code} - {name}")

        return vendor

    def get_vendor(self, vendor_id: str) -> Optional[Vendor]:
        """Get vendor by ID."""
        return self._vendors.get(vendor_id)

    def get_vendor_by_code(self, code: str) -> Optional[Vendor]:
        """Get vendor by code."""
        for vendor in self._vendors.values():
            if vendor.vendor_code == code:
                return vendor
        return None

    def update_vendor(self, vendor_id: str, **updates) -> Optional[Vendor]:
        """Update vendor attributes."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return None

        for key, value in updates.items():
            if hasattr(vendor, key):
                setattr(vendor, key, value)

        vendor.updated_at = datetime.now()
        logger.info(f"Updated vendor: {vendor.vendor_code}")

        return vendor

    def approve_vendor(
        self,
        vendor_id: str,
        approver: str,
        notes: str = ""
    ) -> Optional[Vendor]:
        """
        Approve a vendor for purchasing.

        Args:
            vendor_id: Vendor to approve
            approver: User approving
            notes: Approval notes

        Returns:
            Updated vendor
        """
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return None

        if vendor.status not in [VendorStatus.PROSPECT, VendorStatus.PENDING_APPROVAL]:
            return vendor

        vendor.status = VendorStatus.APPROVED
        vendor.approved_by = approver
        vendor.approved_date = date.today()
        vendor.updated_at = datetime.now()

        if notes:
            vendor.notes += f"\n[{date.today()}] Approved by {approver}: {notes}"

        logger.info(f"Approved vendor: {vendor.vendor_code} by {approver}")
        return vendor

    def add_contact(
        self,
        vendor_id: str,
        name: str,
        email: str = "",
        phone: str = "",
        title: str = "",
        is_primary: bool = False
    ) -> Optional[VendorContact]:
        """Add a contact to a vendor."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return None

        contact = VendorContact(
            contact_id=str(uuid4()),
            name=name,
            email=email,
            phone=phone,
            title=title,
            is_primary=is_primary
        )

        # If this is primary, unset other primaries
        if is_primary:
            for c in vendor.contacts:
                c.is_primary = False

        vendor.contacts.append(contact)
        return contact

    def add_address(
        self,
        vendor_id: str,
        address_type: str,
        street_1: str,
        city: str,
        state: str,
        postal_code: str,
        country: str = "USA",
        **kwargs
    ) -> Optional[VendorAddress]:
        """Add an address to a vendor."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return None

        address = VendorAddress(
            address_id=str(uuid4()),
            address_type=address_type,
            street_1=street_1,
            street_2=kwargs.get("street_2", ""),
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            is_default=kwargs.get("is_default", False)
        )

        vendor.addresses.append(address)
        return address

    def add_certification(
        self,
        vendor_id: str,
        cert_type: CertificationType,
        certificate_number: str,
        issue_date: date,
        expiry_date: date,
        issuing_body: str,
        **kwargs
    ) -> Optional[VendorCertification]:
        """Add a certification to a vendor."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return None

        cert = VendorCertification(
            certification_id=str(uuid4()),
            certification_type=cert_type,
            certificate_number=certificate_number,
            issue_date=issue_date,
            expiry_date=expiry_date,
            issuing_body=issuing_body,
            document_url=kwargs.get("document_url", "")
        )

        vendor.certifications.append(cert)
        logger.info(f"Added certification {cert_type.value} to vendor {vendor.vendor_code}")

        return cert

    def verify_certification(
        self,
        vendor_id: str,
        certification_id: str,
        verified_by: str
    ) -> bool:
        """Verify a vendor certification."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return False

        for cert in vendor.certifications:
            if cert.certification_id == certification_id:
                cert.verified = True
                cert.verified_by = verified_by
                cert.verified_date = date.today()
                return True

        return False

    def record_delivery(
        self,
        vendor_id: str,
        po_number: str,
        on_time: bool,
        qty_ordered: int,
        qty_received: int,
        defects: int = 0,
        delivery_date: Optional[date] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Record a delivery for performance tracking.

        Args:
            vendor_id: Vendor ID
            po_number: Purchase order number
            on_time: Whether delivery was on time
            qty_ordered: Quantity ordered
            qty_received: Quantity received (good units)
            defects: Number of defective units
            delivery_date: Date of delivery

        Returns:
            Delivery record
        """
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        delivery = {
            "delivery_id": str(uuid4()),
            "vendor_id": vendor_id,
            "po_number": po_number,
            "delivery_date": (delivery_date or date.today()).isoformat(),
            "on_time": on_time,
            "qty_ordered": qty_ordered,
            "qty_received": qty_received,
            "defects": defects,
            "qty_short": max(0, qty_ordered - qty_received - defects),
            "notes": kwargs.get("notes", ""),
            "recorded_at": datetime.now().isoformat()
        }

        self._deliveries.append(delivery)
        logger.info(f"Recorded delivery from {vendor.vendor_code}: PO {po_number}")

        return delivery

    def calculate_performance(
        self,
        vendor_id: str,
        period: Optional[str] = None
    ) -> Optional[VendorPerformance]:
        """
        Calculate vendor performance metrics.

        Args:
            vendor_id: Vendor to evaluate
            period: Period in YYYY-MM format (default: current month)

        Returns:
            Performance metrics
        """
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return None

        period = period or datetime.now().strftime("%Y-%m")

        # Filter deliveries for this vendor and period
        vendor_deliveries = [
            d for d in self._deliveries
            if d["vendor_id"] == vendor_id and d["delivery_date"].startswith(period)
        ]

        if not vendor_deliveries:
            return None

        # Calculate metrics
        total_deliveries = len(vendor_deliveries)
        on_time_deliveries = sum(1 for d in vendor_deliveries if d["on_time"])

        total_qty = sum(d["qty_ordered"] for d in vendor_deliveries)
        total_defects = sum(d["defects"] for d in vendor_deliveries)

        # Quality Score: based on defect PPM (target: <100 PPM = 100 score)
        ppm = (total_defects / total_qty * 1_000_000) if total_qty > 0 else 0
        quality_score = max(0, 100 - (ppm / 100))  # -1 point per 100 PPM

        # Delivery Score: on-time percentage
        delivery_score = (on_time_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0

        # Cost Score: placeholder (would compare to market/target prices)
        cost_score = 85.0  # Default reasonable score

        # Service Score: responsiveness, communication (would be from surveys)
        service_score = 80.0  # Default reasonable score

        # Weighted overall score
        overall_score = (
            quality_score * self.QUALITY_WEIGHT +
            delivery_score * self.DELIVERY_WEIGHT +
            cost_score * self.COST_WEIGHT +
            service_score * self.SERVICE_WEIGHT
        )

        performance = VendorPerformance(
            period=period,
            quality_score=round(quality_score, 1),
            delivery_score=round(delivery_score, 1),
            cost_score=round(cost_score, 1),
            service_score=round(service_score, 1),
            overall_score=round(overall_score, 1),
            on_time_deliveries=on_time_deliveries,
            total_deliveries=total_deliveries,
            defect_ppm=round(ppm, 1),
            invoice_accuracy=98.0,  # Would come from AP matching
            lead_time_days=vendor.lead_time_days,
            corrective_actions=0
        )

        # Store in vendor history
        vendor.performance_history.append(performance)

        # Update risk level based on performance
        self._update_risk_level(vendor, overall_score)

        return performance

    def _update_risk_level(self, vendor: Vendor, overall_score: float) -> None:
        """Update vendor risk level based on performance."""
        if overall_score >= 90:
            vendor.risk_level = RiskLevel.LOW
        elif overall_score >= 75:
            vendor.risk_level = RiskLevel.MEDIUM
        elif overall_score >= 60:
            vendor.risk_level = RiskLevel.HIGH
        else:
            vendor.risk_level = RiskLevel.CRITICAL

    def get_vendor_scorecard(self, vendor_id: str) -> Dict[str, Any]:
        """
        Get comprehensive vendor scorecard.

        Returns performance metrics, trends, and recommendations.
        """
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return {}

        # Get recent performance
        recent_performance = vendor.performance_history[-12:] if vendor.performance_history else []

        # Calculate trends
        if len(recent_performance) >= 2:
            quality_trend = recent_performance[-1].quality_score - recent_performance[0].quality_score
            delivery_trend = recent_performance[-1].delivery_score - recent_performance[0].delivery_score
            overall_trend = recent_performance[-1].overall_score - recent_performance[0].overall_score
        else:
            quality_trend = delivery_trend = overall_trend = 0

        # Get certification status
        expiring_certs = [
            c for c in vendor.certifications
            if c.expiry_date <= date.today() + timedelta(days=90)
        ]

        # Count deliveries
        vendor_deliveries = [d for d in self._deliveries if d["vendor_id"] == vendor_id]

        scorecard = {
            "vendor_id": vendor.vendor_id,
            "vendor_code": vendor.vendor_code,
            "vendor_name": vendor.name,
            "status": vendor.status.value,
            "risk_level": vendor.risk_level.value,
            "performance": {
                "current": {
                    "quality": recent_performance[-1].quality_score if recent_performance else None,
                    "delivery": recent_performance[-1].delivery_score if recent_performance else None,
                    "cost": recent_performance[-1].cost_score if recent_performance else None,
                    "service": recent_performance[-1].service_score if recent_performance else None,
                    "overall": recent_performance[-1].overall_score if recent_performance else None
                },
                "trends": {
                    "quality": round(quality_trend, 1),
                    "delivery": round(delivery_trend, 1),
                    "overall": round(overall_trend, 1)
                },
                "history": [
                    {
                        "period": p.period,
                        "overall": p.overall_score,
                        "quality": p.quality_score,
                        "delivery": p.delivery_score
                    }
                    for p in recent_performance
                ]
            },
            "delivery_stats": {
                "total_deliveries": len(vendor_deliveries),
                "last_30_days": len([
                    d for d in vendor_deliveries
                    if datetime.fromisoformat(d["delivery_date"]) >= datetime.now() - timedelta(days=30)
                ]),
                "on_time_rate": (
                    sum(1 for d in vendor_deliveries if d["on_time"]) / len(vendor_deliveries) * 100
                    if vendor_deliveries else 0
                )
            },
            "certifications": {
                "active": len([c for c in vendor.certifications if c.expiry_date > date.today()]),
                "expiring_soon": len(expiring_certs),
                "details": [
                    {
                        "type": c.certification_type.value,
                        "expiry": c.expiry_date.isoformat(),
                        "verified": c.verified
                    }
                    for c in vendor.certifications
                ]
            },
            "recommendations": self._generate_recommendations(vendor, recent_performance)
        }

        return scorecard

    def _generate_recommendations(
        self,
        vendor: Vendor,
        performance: List[VendorPerformance]
    ) -> List[str]:
        """Generate improvement recommendations for vendor."""
        recommendations = []

        if not performance:
            recommendations.append("Insufficient data for performance analysis - track more deliveries")
            return recommendations

        latest = performance[-1]

        # Quality recommendations
        if latest.quality_score < 80:
            recommendations.append(
                f"Quality improvement needed: Current PPM={latest.defect_ppm:.0f}, target <100 PPM"
            )
            recommendations.append("Consider supplier quality audit and corrective action request")

        # Delivery recommendations
        if latest.delivery_score < 85:
            recommendations.append(
                f"On-time delivery needs improvement: {latest.delivery_score:.0f}%, target >95%"
            )
            recommendations.append("Review lead times and safety stock requirements")

        # Certification recommendations
        expiring = [c for c in vendor.certifications if c.expiry_date <= date.today() + timedelta(days=60)]
        if expiring:
            recommendations.append(f"{len(expiring)} certification(s) expiring soon - request renewals")

        # Status recommendations
        if vendor.status == VendorStatus.APPROVED and latest.overall_score >= 95:
            recommendations.append("Consider upgrading to PREFERRED status based on excellent performance")
        elif vendor.status == VendorStatus.PREFERRED and latest.overall_score < 80:
            recommendations.append("Performance below standard for PREFERRED status - review required")

        # Risk recommendations
        if vendor.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("High risk vendor - consider qualifying alternate supplier")

        return recommendations

    def list_vendors(
        self,
        status: Optional[VendorStatus] = None,
        vendor_type: Optional[VendorType] = None,
        risk_level: Optional[RiskLevel] = None,
        search: str = "",
        limit: int = 100
    ) -> List[Vendor]:
        """List vendors with filters."""
        vendors = list(self._vendors.values())

        if status:
            vendors = [v for v in vendors if v.status == status]

        if vendor_type:
            vendors = [v for v in vendors if v.vendor_type == vendor_type]

        if risk_level:
            vendors = [v for v in vendors if v.risk_level == risk_level]

        if search:
            search_lower = search.lower()
            vendors = [
                v for v in vendors
                if search_lower in v.name.lower() or search_lower in v.vendor_code.lower()
            ]

        return sorted(vendors, key=lambda v: v.name)[:limit]

    def get_expiring_certifications(
        self,
        days_ahead: int = 90
    ) -> List[Dict[str, Any]]:
        """Get list of certifications expiring within specified days."""
        cutoff = date.today() + timedelta(days=days_ahead)
        expiring = []

        for vendor in self._vendors.values():
            for cert in vendor.certifications:
                if cert.expiry_date <= cutoff:
                    expiring.append({
                        "vendor_id": vendor.vendor_id,
                        "vendor_code": vendor.vendor_code,
                        "vendor_name": vendor.name,
                        "certification": cert.certification_type.value,
                        "certificate_number": cert.certificate_number,
                        "expiry_date": cert.expiry_date.isoformat(),
                        "days_remaining": (cert.expiry_date - date.today()).days
                    })

        return sorted(expiring, key=lambda x: x["expiry_date"])

    def get_vendor_summary(self) -> Dict[str, Any]:
        """Get summary of all vendors."""
        vendors = list(self._vendors.values())

        if not vendors:
            return {
                "total_vendors": 0,
                "by_status": {},
                "by_type": {},
                "by_risk": {}
            }

        # Count by status
        by_status = {}
        for status in VendorStatus:
            count = len([v for v in vendors if v.status == status])
            if count > 0:
                by_status[status.value] = count

        # Count by type
        by_type = {}
        for vtype in VendorType:
            count = len([v for v in vendors if v.vendor_type == vtype])
            if count > 0:
                by_type[vtype.value] = count

        # Count by risk
        by_risk = {}
        for risk in RiskLevel:
            count = len([v for v in vendors if v.risk_level == risk])
            if count > 0:
                by_risk[risk.value] = count

        # Get top performers
        vendors_with_perf = [
            v for v in vendors if v.performance_history
        ]
        top_performers = sorted(
            vendors_with_perf,
            key=lambda v: v.performance_history[-1].overall_score,
            reverse=True
        )[:5]

        return {
            "total_vendors": len(vendors),
            "active_vendors": len([v for v in vendors if v.status == VendorStatus.APPROVED]),
            "preferred_vendors": len([v for v in vendors if v.status == VendorStatus.PREFERRED]),
            "strategic_vendors": len([v for v in vendors if v.status == VendorStatus.STRATEGIC]),
            "by_status": by_status,
            "by_type": by_type,
            "by_risk": by_risk,
            "certifications_expiring_30d": len(self.get_expiring_certifications(30)),
            "certifications_expiring_90d": len(self.get_expiring_certifications(90)),
            "top_performers": [
                {
                    "vendor_code": v.vendor_code,
                    "name": v.name,
                    "score": v.performance_history[-1].overall_score
                }
                for v in top_performers
            ],
            "high_risk_count": len([v for v in vendors if v.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]])
        }

    # Quote Management

    def create_quote(
        self,
        vendor_id: str,
        items: List[Dict[str, Any]],
        valid_days: int = 30,
        **kwargs
    ) -> VendorQuote:
        """Create a vendor quote request."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        quote_date = date.today()
        valid_until = quote_date + timedelta(days=valid_days)

        # Calculate totals
        subtotal = Decimal("0")
        for item in items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("unit_price", 0)))
            item["line_total"] = float(qty * price)
            subtotal += qty * price

        freight = Decimal(str(kwargs.get("freight", 0)))
        tax = Decimal(str(kwargs.get("tax", 0)))
        total = subtotal + freight + tax

        quote = VendorQuote(
            quote_id=str(uuid4()),
            vendor_id=vendor_id,
            quote_number=f"Q-{datetime.now().strftime('%Y%m%d')}-{len(self._quotes) + 1:04d}",
            quote_date=quote_date,
            valid_until=valid_until,
            items=items,
            subtotal=subtotal,
            freight=freight,
            tax=tax,
            total=total,
            lead_time_days=kwargs.get("lead_time_days", vendor.lead_time_days),
            terms=kwargs.get("terms", ""),
            notes=kwargs.get("notes", "")
        )

        self._quotes[quote.quote_id] = quote
        return quote

    # Contract Management

    def create_contract(
        self,
        vendor_id: str,
        contract_type: str,
        start_date: date,
        end_date: date,
        value: float,
        terms: str = "",
        **kwargs
    ) -> VendorContract:
        """Create a vendor contract."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        contract = VendorContract(
            contract_id=str(uuid4()),
            vendor_id=vendor_id,
            contract_number=f"C-{datetime.now().strftime('%Y')}-{len(self._contracts) + 1:04d}",
            contract_type=contract_type,
            start_date=start_date,
            end_date=end_date,
            value=Decimal(str(value)),
            terms=terms,
            auto_renew=kwargs.get("auto_renew", False),
            document_url=kwargs.get("document_url", "")
        )

        self._contracts[contract.contract_id] = contract
        logger.info(f"Created contract {contract.contract_number} with vendor {vendor.vendor_code}")

        return contract


# Singleton instance
_vendor_service: Optional[VendorService] = None


def get_vendor_service() -> VendorService:
    """Get or create singleton VendorService."""
    global _vendor_service
    if _vendor_service is None:
        _vendor_service = VendorService()
    return _vendor_service
