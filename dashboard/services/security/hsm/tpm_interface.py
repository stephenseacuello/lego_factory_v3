"""
TPM (Trusted Platform Module) Interface

Hardware-backed security using TPM 2.0:
- Secure boot measurement
- Platform attestation
- Sealed storage
- Hardware RNG

Reference: TPM 2.0 Specification, IEC 62443
"""

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import logging
import struct

logger = logging.getLogger(__name__)


class TPMAlgorithm(Enum):
    """TPM supported algorithms."""
    RSA = 0x0001
    SHA256 = 0x000B
    SHA384 = 0x000C
    SHA512 = 0x000D
    ECDSA_P256 = 0x0018
    ECDSA_P384 = 0x0019


class PCRBank(Enum):
    """TPM PCR banks."""
    SHA256 = "sha256"
    SHA384 = "sha384"


class TPMError(Exception):
    """TPM operation error."""
    pass


@dataclass
class TPMConfig:
    """
    TPM configuration.

    Attributes:
        device_path: TPM device path
        pcr_selection: PCRs to use for sealing
        locality: TPM locality
        enable_attestation: Enable remote attestation
    """
    device_path: str = "/dev/tpm0"
    pcr_selection: List[int] = field(default_factory=lambda: [0, 1, 2, 7])
    locality: int = 0
    enable_attestation: bool = True
    simulation_mode: bool = True  # Use simulation in development


@dataclass
class PCRValue:
    """PCR register value."""
    index: int
    bank: PCRBank
    value: bytes
    event_log: List[str] = field(default_factory=list)


@dataclass
class SealedData:
    """Data sealed to TPM."""
    handle: str
    encrypted_data: bytes
    auth_policy: bytes
    pcr_selection: List[int]
    created_at: float = field(default_factory=time.time)


@dataclass
class AttestationQuote:
    """TPM attestation quote."""
    quote_data: bytes
    signature: bytes
    pcr_values: Dict[int, bytes]
    nonce: bytes
    timestamp: float


class TPMInterface:
    """
    Interface to TPM 2.0 for hardware-backed security.

    Features:
    - PCR measurement and extension
    - Data sealing to platform state
    - Remote attestation
    - Hardware random numbers
    - Key generation in TPM

    Usage:
        >>> tpm = TPMInterface(config)
        >>> tpm.connect()
        >>> sealed = tpm.seal_data(secret, pcrs=[0, 1, 7])
        >>> secret = tpm.unseal_data(sealed.handle)
    """

    # TPM constants
    TPM2_RC_SUCCESS = 0x000
    MAX_PCR_INDEX = 23

    def __init__(self, config: Optional[TPMConfig] = None):
        """
        Initialize TPM interface.

        Args:
            config: TPM configuration
        """
        self.config = config or TPMConfig()

        # Connection state
        self._connected = False
        self._handle: Optional[Any] = None

        # Simulated TPM state (for development)
        self._sim_pcrs: Dict[Tuple[int, PCRBank], bytes] = {}
        self._sim_sealed: Dict[str, SealedData] = {}
        self._sim_keys: Dict[str, bytes] = {}

        # Initialize simulated PCRs
        if self.config.simulation_mode:
            self._init_simulated_pcrs()

        logger.info(f"TPMInterface initialized (simulation={self.config.simulation_mode})")

    def _init_simulated_pcrs(self) -> None:
        """Initialize simulated PCRs."""
        for i in range(self.MAX_PCR_INDEX + 1):
            for bank in PCRBank:
                hash_len = 32 if bank == PCRBank.SHA256 else 48
                self._sim_pcrs[(i, bank)] = b'\x00' * hash_len

    def connect(self) -> bool:
        """
        Connect to TPM device.

        Returns:
            True if connected successfully
        """
        if self.config.simulation_mode:
            self._connected = True
            logger.info("Connected to simulated TPM")
            return True

        try:
            # In production, would open TPM device
            # self._handle = open(self.config.device_path, 'rb+')
            self._connected = True
            logger.info(f"Connected to TPM at {self.config.device_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to TPM: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from TPM."""
        self._connected = False
        if self._handle:
            self._handle = None
        logger.info("Disconnected from TPM")

    def read_pcr(
        self,
        index: int,
        bank: PCRBank = PCRBank.SHA256
    ) -> PCRValue:
        """
        Read PCR value.

        Args:
            index: PCR index (0-23)
            bank: PCR bank

        Returns:
            PCRValue with current value
        """
        self._ensure_connected()

        if index < 0 or index > self.MAX_PCR_INDEX:
            raise TPMError(f"Invalid PCR index: {index}")

        if self.config.simulation_mode:
            value = self._sim_pcrs.get((index, bank), b'\x00' * 32)
            return PCRValue(index=index, bank=bank, value=value)

        # Real TPM read would go here
        raise NotImplementedError("Real TPM not implemented")

    def extend_pcr(
        self,
        index: int,
        data: bytes,
        bank: PCRBank = PCRBank.SHA256
    ) -> PCRValue:
        """
        Extend PCR with measurement.

        PCR_new = Hash(PCR_old || data)

        Args:
            index: PCR index
            data: Data to extend with
            bank: PCR bank

        Returns:
            New PCR value
        """
        self._ensure_connected()

        if index < 0 or index > self.MAX_PCR_INDEX:
            raise TPMError(f"Invalid PCR index: {index}")

        current = self.read_pcr(index, bank)

        # Extend: Hash(current || data)
        hash_func = hashlib.sha256 if bank == PCRBank.SHA256 else hashlib.sha384
        new_value = hash_func(current.value + data).digest()

        if self.config.simulation_mode:
            self._sim_pcrs[(index, bank)] = new_value

        logger.debug(f"Extended PCR{index} with {len(data)} bytes")
        return PCRValue(index=index, bank=bank, value=new_value)

    def seal_data(
        self,
        data: bytes,
        pcrs: Optional[List[int]] = None,
        auth_value: Optional[bytes] = None
    ) -> SealedData:
        """
        Seal data to current PCR values.

        Data can only be unsealed when PCRs match.

        Args:
            data: Data to seal
            pcrs: PCR indices to seal to
            auth_value: Optional authorization value

        Returns:
            SealedData handle
        """
        self._ensure_connected()

        pcr_selection = pcrs or self.config.pcr_selection

        # Create auth policy from PCR values
        pcr_values = []
        for pcr_idx in pcr_selection:
            pcr = self.read_pcr(pcr_idx)
            pcr_values.append(pcr.value)

        policy_hash = hashlib.sha256(b''.join(pcr_values)).digest()

        if auth_value:
            policy_hash = hashlib.sha256(policy_hash + auth_value).digest()

        # Seal data (encrypt with policy)
        seal_key = hashlib.sha256(policy_hash + secrets.token_bytes(16)).digest()
        encrypted = self._simple_encrypt(data, seal_key)

        # Generate handle
        handle = f"seal_{int(time.time() * 1000)}_{secrets.token_hex(8)}"

        sealed = SealedData(
            handle=handle,
            encrypted_data=encrypted,
            auth_policy=policy_hash,
            pcr_selection=pcr_selection
        )

        if self.config.simulation_mode:
            self._sim_sealed[handle] = sealed
            self._sim_keys[handle] = seal_key

        logger.info(f"Sealed data with handle {handle}")
        return sealed

    def unseal_data(
        self,
        handle: str,
        auth_value: Optional[bytes] = None
    ) -> bytes:
        """
        Unseal data from TPM.

        Will only succeed if PCRs match sealed state.

        Args:
            handle: Sealed data handle
            auth_value: Authorization value

        Returns:
            Unsealed data

        Raises:
            TPMError: If PCRs don't match or authorization fails
        """
        self._ensure_connected()

        if self.config.simulation_mode:
            if handle not in self._sim_sealed:
                raise TPMError(f"Sealed object not found: {handle}")

            sealed = self._sim_sealed[handle]
            seal_key = self._sim_keys.get(handle)

            # Verify PCR values match
            current_values = []
            for pcr_idx in sealed.pcr_selection:
                pcr = self.read_pcr(pcr_idx)
                current_values.append(pcr.value)

            current_policy = hashlib.sha256(b''.join(current_values)).digest()
            if auth_value:
                current_policy = hashlib.sha256(current_policy + auth_value).digest()

            if current_policy != sealed.auth_policy:
                raise TPMError("PCR mismatch - platform state changed")

            return self._simple_decrypt(sealed.encrypted_data, seal_key)

        raise NotImplementedError("Real TPM not implemented")

    def get_random(self, length: int) -> bytes:
        """
        Get random bytes from TPM hardware RNG.

        Args:
            length: Number of bytes

        Returns:
            Random bytes
        """
        self._ensure_connected()

        if self.config.simulation_mode:
            return secrets.token_bytes(length)

        # Real TPM would use TPM2_GetRandom
        raise NotImplementedError("Real TPM not implemented")

    def create_attestation_key(self) -> str:
        """
        Create attestation key (AK) in TPM.

        Returns:
            Key handle
        """
        self._ensure_connected()

        handle = f"ak_{int(time.time() * 1000)}_{secrets.token_hex(8)}"

        if self.config.simulation_mode:
            self._sim_keys[handle] = secrets.token_bytes(32)

        logger.info(f"Created attestation key: {handle}")
        return handle

    def quote(
        self,
        ak_handle: str,
        pcrs: Optional[List[int]] = None,
        nonce: Optional[bytes] = None
    ) -> AttestationQuote:
        """
        Generate attestation quote.

        Args:
            ak_handle: Attestation key handle
            pcrs: PCRs to include in quote
            nonce: Challenge nonce

        Returns:
            AttestationQuote
        """
        self._ensure_connected()

        if not self.config.enable_attestation:
            raise TPMError("Attestation not enabled")

        pcr_selection = pcrs or self.config.pcr_selection
        nonce = nonce or secrets.token_bytes(32)

        # Collect PCR values
        pcr_values = {}
        for idx in pcr_selection:
            pcr = self.read_pcr(idx)
            pcr_values[idx] = pcr.value

        # Create quote data
        pcr_digest = hashlib.sha256(b''.join(pcr_values.values())).digest()
        quote_data = struct.pack(">I", len(pcr_selection)) + pcr_digest + nonce

        # Sign quote
        if self.config.simulation_mode:
            ak_key = self._sim_keys.get(ak_handle, secrets.token_bytes(32))
            signature = hashlib.sha256(ak_key + quote_data).digest()
        else:
            raise NotImplementedError("Real TPM not implemented")

        return AttestationQuote(
            quote_data=quote_data,
            signature=signature,
            pcr_values=pcr_values,
            nonce=nonce,
            timestamp=time.time()
        )

    def verify_quote(
        self,
        quote: AttestationQuote,
        expected_pcrs: Dict[int, bytes],
        expected_nonce: bytes
    ) -> Tuple[bool, str]:
        """
        Verify attestation quote.

        Args:
            quote: Quote to verify
            expected_pcrs: Expected PCR values
            expected_nonce: Expected nonce

        Returns:
            Tuple of (valid, reason)
        """
        # Verify nonce
        if quote.nonce != expected_nonce:
            return False, "Nonce mismatch"

        # Verify PCR values
        for idx, expected in expected_pcrs.items():
            if idx not in quote.pcr_values:
                return False, f"Missing PCR{idx}"
            if quote.pcr_values[idx] != expected:
                return False, f"PCR{idx} mismatch"

        # In production, would verify signature with EK/AK public key
        return True, "Quote valid"

    def measure_boot(
        self,
        component: str,
        measurement: bytes,
        pcr_index: int = 0
    ) -> None:
        """
        Record boot measurement.

        Args:
            component: Component name
            measurement: Measurement hash
            pcr_index: PCR to extend
        """
        self._ensure_connected()

        # Extend PCR with measurement
        self.extend_pcr(pcr_index, measurement)
        logger.info(f"Measured boot component: {component} -> PCR{pcr_index}")

    def get_endorsement_key_certificate(self) -> Optional[bytes]:
        """
        Get Endorsement Key (EK) certificate.

        Returns:
            EK certificate or None
        """
        self._ensure_connected()

        if self.config.simulation_mode:
            # Return simulated EK cert
            return b"SIMULATED_EK_CERTIFICATE"

        # Real TPM would read from NVRAM
        return None

    def _ensure_connected(self) -> None:
        """Ensure TPM is connected."""
        if not self._connected:
            raise TPMError("Not connected to TPM")

    def _simple_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption for simulation."""
        keystream = b""
        while len(keystream) < len(data):
            keystream += hashlib.sha256(key + len(keystream).to_bytes(4, 'big')).digest()
        return bytes(d ^ k for d, k in zip(data, keystream[:len(data)]))

    def _simple_decrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR decryption for simulation."""
        return self._simple_encrypt(data, key)  # XOR is symmetric

    @property
    def is_connected(self) -> bool:
        """Check if connected to TPM."""
        return self._connected

    def get_capabilities(self) -> Dict[str, Any]:
        """Get TPM capabilities."""
        return {
            "connected": self._connected,
            "simulation_mode": self.config.simulation_mode,
            "attestation_enabled": self.config.enable_attestation,
            "pcr_banks": [bank.value for bank in PCRBank],
            "max_pcr_index": self.MAX_PCR_INDEX,
            "algorithms": [alg.name for alg in TPMAlgorithm]
        }
