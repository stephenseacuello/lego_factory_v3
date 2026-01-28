"""
Certificate Authority for Manufacturing PKI

X.509 certificate management for IEC 62443 compliance:
- Device identity certificates
- Code signing certificates
- TLS/mTLS certificates
- Certificate lifecycle management

Reference: IEC 62443-3-3, NIST SP 800-57
"""

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime, timedelta
import base64

logger = logging.getLogger(__name__)


class CertificateType(Enum):
    """Types of certificates."""
    ROOT_CA = "root_ca"
    INTERMEDIATE_CA = "intermediate_ca"
    DEVICE_IDENTITY = "device_identity"
    CODE_SIGNING = "code_signing"
    TLS_SERVER = "tls_server"
    TLS_CLIENT = "tls_client"
    OPERATOR = "operator"


class CertificateState(Enum):
    """Certificate lifecycle state."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RevocationReason(Enum):
    """Certificate revocation reasons (RFC 5280)."""
    UNSPECIFIED = 0
    KEY_COMPROMISE = 1
    CA_COMPROMISE = 2
    AFFILIATION_CHANGED = 3
    SUPERSEDED = 4
    CESSATION_OF_OPERATION = 5
    CERTIFICATE_HOLD = 6
    PRIVILEGE_WITHDRAWN = 9


@dataclass
class SubjectInfo:
    """Certificate subject information."""
    common_name: str
    organization: str = "LEGO MCP Manufacturing"
    organizational_unit: str = ""
    country: str = "US"
    state: str = ""
    locality: str = ""
    email: str = ""


@dataclass
class CertificateInfo:
    """
    Certificate information.

    Attributes:
        serial_number: Unique serial number
        subject: Subject information
        issuer: Issuer information
        cert_type: Certificate type
        state: Lifecycle state
        not_before: Validity start
        not_after: Validity end
        public_key_hash: Hash of public key
    """
    serial_number: str
    subject: SubjectInfo
    issuer: Optional[SubjectInfo]
    cert_type: CertificateType
    state: CertificateState = CertificateState.PENDING
    not_before: float = field(default_factory=time.time)
    not_after: float = field(default_factory=lambda: time.time() + 365 * 86400)
    public_key_hash: str = ""
    key_usage: List[str] = field(default_factory=list)
    extended_key_usage: List[str] = field(default_factory=list)
    san: List[str] = field(default_factory=list)  # Subject Alternative Names
    issuer_serial: Optional[str] = None
    revocation_date: Optional[float] = None
    revocation_reason: Optional[RevocationReason] = None


@dataclass
class CAConfig:
    """
    Certificate Authority configuration.

    Attributes:
        ca_name: CA name
        default_validity_days: Default certificate validity
        max_validity_days: Maximum allowed validity
        crl_update_interval: CRL update interval in seconds
        ocsp_enabled: Enable OCSP responder
    """
    ca_name: str = "LEGO MCP Manufacturing CA"
    default_validity_days: int = 365
    max_validity_days: int = 1825  # 5 years
    crl_update_interval: int = 3600  # 1 hour
    ocsp_enabled: bool = True
    require_csr: bool = True
    audit_enabled: bool = True


class CertificateAuthority:
    """
    Manufacturing PKI Certificate Authority.

    Features:
    - Certificate issuance
    - Certificate revocation
    - CRL generation
    - Certificate validation
    - Audit logging

    Usage:
        >>> ca = CertificateAuthority(config)
        >>> cert = ca.issue_certificate(subject, CertificateType.DEVICE_IDENTITY)
        >>> ca.verify_certificate(cert.serial_number)
    """

    def __init__(
        self,
        config: Optional[CAConfig] = None,
        key_manager: Optional[Any] = None
    ):
        """
        Initialize Certificate Authority.

        Args:
            config: CA configuration
            key_manager: Key manager for CA keys
        """
        self.config = config or CAConfig()
        self.key_manager = key_manager

        # Certificate storage
        self._certificates: Dict[str, CertificateInfo] = {}
        self._crl: List[str] = []  # Revoked serial numbers
        self._crl_updated: float = 0

        # CA certificate (would be loaded from secure storage in production)
        self._ca_cert: Optional[CertificateInfo] = None
        self._ca_key_id: Optional[str] = None

        # Serial number counter
        self._serial_counter: int = int(time.time() * 1000)

        logger.info(f"CertificateAuthority initialized: {self.config.ca_name}")

    def initialize_ca(
        self,
        subject: Optional[SubjectInfo] = None,
        validity_days: int = 3650  # 10 years
    ) -> CertificateInfo:
        """
        Initialize the CA with a self-signed root certificate.

        Args:
            subject: CA subject information
            validity_days: CA certificate validity

        Returns:
            CA certificate information
        """
        if subject is None:
            subject = SubjectInfo(
                common_name=self.config.ca_name,
                organizational_unit="Certificate Authority"
            )

        # Generate serial number
        serial = self._generate_serial()

        # Create CA certificate
        now = time.time()
        self._ca_cert = CertificateInfo(
            serial_number=serial,
            subject=subject,
            issuer=subject,  # Self-signed
            cert_type=CertificateType.ROOT_CA,
            state=CertificateState.ACTIVE,
            not_before=now,
            not_after=now + (validity_days * 86400),
            key_usage=["keyCertSign", "cRLSign", "digitalSignature"],
            public_key_hash=self._generate_key_hash()
        )

        self._certificates[serial] = self._ca_cert

        # Generate CA key pair (would use HSM in production)
        if self.key_manager:
            from .key_manager import KeyType, KeyUsage
            self._ca_key_id = self.key_manager.generate_key(
                KeyType.ASYMMETRIC_RSA_4096,
                [KeyUsage.SIGN],
                owner="CA",
                activate_immediately=True
            )

        logger.info(f"CA initialized with serial {serial}")
        return self._ca_cert

    def issue_certificate(
        self,
        subject: SubjectInfo,
        cert_type: CertificateType,
        validity_days: Optional[int] = None,
        san: Optional[List[str]] = None,
        key_usage: Optional[List[str]] = None
    ) -> CertificateInfo:
        """
        Issue a new certificate.

        Args:
            subject: Certificate subject
            cert_type: Type of certificate
            validity_days: Validity period
            san: Subject Alternative Names
            key_usage: Key usage extensions

        Returns:
            Issued certificate information
        """
        if not self._ca_cert:
            raise RuntimeError("CA not initialized")

        # Validate validity period
        validity = validity_days or self.config.default_validity_days
        if validity > self.config.max_validity_days:
            validity = self.config.max_validity_days

        # Generate serial number
        serial = self._generate_serial()

        # Determine key usage based on certificate type
        if key_usage is None:
            key_usage = self._default_key_usage(cert_type)

        # Create certificate
        now = time.time()
        cert = CertificateInfo(
            serial_number=serial,
            subject=subject,
            issuer=self._ca_cert.subject,
            cert_type=cert_type,
            state=CertificateState.ACTIVE,
            not_before=now,
            not_after=now + (validity * 86400),
            key_usage=key_usage,
            extended_key_usage=self._default_eku(cert_type),
            san=san or [],
            issuer_serial=self._ca_cert.serial_number,
            public_key_hash=self._generate_key_hash()
        )

        self._certificates[serial] = cert
        self._audit("certificate_issued", cert)

        logger.info(f"Issued {cert_type.value} certificate {serial} for {subject.common_name}")
        return cert

    def revoke_certificate(
        self,
        serial_number: str,
        reason: RevocationReason = RevocationReason.UNSPECIFIED
    ) -> bool:
        """
        Revoke a certificate.

        Args:
            serial_number: Certificate serial number
            reason: Revocation reason

        Returns:
            True if revoked successfully
        """
        if serial_number not in self._certificates:
            logger.warning(f"Certificate not found: {serial_number}")
            return False

        cert = self._certificates[serial_number]

        if cert.state == CertificateState.REVOKED:
            logger.warning(f"Certificate already revoked: {serial_number}")
            return False

        cert.state = CertificateState.REVOKED
        cert.revocation_date = time.time()
        cert.revocation_reason = reason

        self._crl.append(serial_number)
        self._audit("certificate_revoked", cert, {"reason": reason.name})

        logger.info(f"Revoked certificate {serial_number}: {reason.name}")
        return True

    def verify_certificate(self, serial_number: str) -> Tuple[bool, str]:
        """
        Verify a certificate.

        Args:
            serial_number: Certificate serial number

        Returns:
            Tuple of (is_valid, reason)
        """
        if serial_number not in self._certificates:
            return False, "Certificate not found"

        cert = self._certificates[serial_number]

        # Check state
        if cert.state == CertificateState.REVOKED:
            return False, f"Certificate revoked: {cert.revocation_reason.name if cert.revocation_reason else 'unknown'}"

        if cert.state != CertificateState.ACTIVE:
            return False, f"Certificate not active: {cert.state.value}"

        # Check validity period
        now = time.time()
        if now < cert.not_before:
            return False, "Certificate not yet valid"

        if now > cert.not_after:
            cert.state = CertificateState.EXPIRED
            return False, "Certificate expired"

        # Verify issuer
        if cert.issuer_serial and cert.issuer_serial not in self._certificates:
            return False, "Issuer certificate not found"

        return True, "Certificate valid"

    def get_certificate(self, serial_number: str) -> Optional[CertificateInfo]:
        """Get certificate by serial number."""
        return self._certificates.get(serial_number)

    def list_certificates(
        self,
        cert_type: Optional[CertificateType] = None,
        state: Optional[CertificateState] = None
    ) -> List[CertificateInfo]:
        """List certificates matching criteria."""
        results = []
        for cert in self._certificates.values():
            if cert_type and cert.cert_type != cert_type:
                continue
            if state and cert.state != state:
                continue
            results.append(cert)
        return results

    def generate_crl(self) -> Dict[str, Any]:
        """
        Generate Certificate Revocation List.

        Returns:
            CRL data
        """
        now = time.time()

        revoked_certs = []
        for serial in self._crl:
            if serial in self._certificates:
                cert = self._certificates[serial]
                revoked_certs.append({
                    "serial": serial,
                    "revocation_date": cert.revocation_date,
                    "reason": cert.revocation_reason.value if cert.revocation_reason else 0
                })

        crl = {
            "issuer": self._ca_cert.subject.common_name if self._ca_cert else "",
            "this_update": datetime.now().isoformat(),
            "next_update": datetime.fromtimestamp(now + self.config.crl_update_interval).isoformat(),
            "revoked_certificates": revoked_certs,
            "crl_number": int(now)
        }

        self._crl_updated = now
        return crl

    def check_ocsp(self, serial_number: str) -> Dict[str, Any]:
        """
        OCSP status check.

        Args:
            serial_number: Certificate serial number

        Returns:
            OCSP response
        """
        if not self.config.ocsp_enabled:
            return {"error": "OCSP not enabled"}

        is_valid, reason = self.verify_certificate(serial_number)

        return {
            "serial_number": serial_number,
            "status": "good" if is_valid else "revoked",
            "reason": reason,
            "this_update": datetime.now().isoformat(),
            "next_update": datetime.fromtimestamp(
                time.time() + 3600
            ).isoformat()
        }

    def renew_certificate(self, serial_number: str) -> Optional[CertificateInfo]:
        """
        Renew a certificate.

        Args:
            serial_number: Certificate to renew

        Returns:
            New certificate or None
        """
        if serial_number not in self._certificates:
            return None

        old_cert = self._certificates[serial_number]

        if old_cert.state == CertificateState.REVOKED:
            logger.warning(f"Cannot renew revoked certificate: {serial_number}")
            return None

        # Issue new certificate with same parameters
        new_cert = self.issue_certificate(
            subject=old_cert.subject,
            cert_type=old_cert.cert_type,
            san=old_cert.san,
            key_usage=old_cert.key_usage
        )

        # Revoke old certificate
        self.revoke_certificate(serial_number, RevocationReason.SUPERSEDED)

        self._audit("certificate_renewed", new_cert, {"old_serial": serial_number})
        return new_cert

    def _generate_serial(self) -> str:
        """Generate unique serial number."""
        self._serial_counter += 1
        random_part = secrets.token_hex(8)
        return f"{self._serial_counter:016x}{random_part}"

    def _generate_key_hash(self) -> str:
        """Generate key hash (placeholder for actual public key hash)."""
        return hashlib.sha256(secrets.token_bytes(32)).hexdigest()

    def _default_key_usage(self, cert_type: CertificateType) -> List[str]:
        """Get default key usage for certificate type."""
        usage_map = {
            CertificateType.ROOT_CA: ["keyCertSign", "cRLSign"],
            CertificateType.INTERMEDIATE_CA: ["keyCertSign", "cRLSign"],
            CertificateType.DEVICE_IDENTITY: ["digitalSignature", "keyEncipherment"],
            CertificateType.CODE_SIGNING: ["digitalSignature"],
            CertificateType.TLS_SERVER: ["digitalSignature", "keyEncipherment"],
            CertificateType.TLS_CLIENT: ["digitalSignature", "keyEncipherment"],
            CertificateType.OPERATOR: ["digitalSignature", "keyEncipherment"],
        }
        return usage_map.get(cert_type, ["digitalSignature"])

    def _default_eku(self, cert_type: CertificateType) -> List[str]:
        """Get default Extended Key Usage for certificate type."""
        eku_map = {
            CertificateType.TLS_SERVER: ["serverAuth"],
            CertificateType.TLS_CLIENT: ["clientAuth"],
            CertificateType.CODE_SIGNING: ["codeSigning"],
            CertificateType.OPERATOR: ["clientAuth", "emailProtection"],
        }
        return eku_map.get(cert_type, [])

    def _audit(
        self,
        event: str,
        cert: CertificateInfo,
        extra: Optional[Dict] = None
    ) -> None:
        """Log audit event."""
        if not self.config.audit_enabled:
            return

        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "serial": cert.serial_number,
            "subject": cert.subject.common_name,
            "type": cert.cert_type.value,
            "state": cert.state.value,
            **(extra or {})
        }

        logger.info(f"CA Audit: {audit_entry}")

    def get_ca_certificate(self) -> Optional[CertificateInfo]:
        """Get the CA's own certificate."""
        return self._ca_cert

    def get_certificate_chain(self, serial_number: str) -> List[CertificateInfo]:
        """Get certificate chain up to root."""
        chain = []
        current = self.get_certificate(serial_number)

        while current:
            chain.append(current)
            if current.issuer_serial:
                current = self.get_certificate(current.issuer_serial)
            else:
                break

        return chain
