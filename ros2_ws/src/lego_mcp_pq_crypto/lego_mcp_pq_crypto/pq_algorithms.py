"""
Post-Quantum Cryptographic Algorithms

Implements simulated versions of NIST PQC algorithms.
For production, integrate with liboqs or pqcrypto libraries.

Reference: NIST FIPS 203, 204, 205
"""

import hashlib
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """NIST security levels."""
    LEVEL_1 = 1  # AES-128 equivalent
    LEVEL_3 = 3  # AES-192 equivalent
    LEVEL_5 = 5  # AES-256 equivalent


class Algorithm(Enum):
    """Supported algorithms."""
    # ML-KEM (Kyber) variants
    ML_KEM_512 = "ML-KEM-512"
    ML_KEM_768 = "ML-KEM-768"
    ML_KEM_1024 = "ML-KEM-1024"

    # ML-DSA (Dilithium) variants
    ML_DSA_44 = "ML-DSA-44"
    ML_DSA_65 = "ML-DSA-65"
    ML_DSA_87 = "ML-DSA-87"

    # SLH-DSA (SPHINCS+) variants
    SLH_DSA_128S = "SLH-DSA-SHAKE-128s"
    SLH_DSA_128F = "SLH-DSA-SHAKE-128f"
    SLH_DSA_192S = "SLH-DSA-SHAKE-192s"
    SLH_DSA_256S = "SLH-DSA-SHAKE-256s"


@dataclass
class KeyPair:
    """Cryptographic key pair."""
    key_id: str
    algorithm: Algorithm
    public_key: bytes
    private_key: bytes
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if key is still valid."""
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True


@dataclass
class EncapsulationResult:
    """Result of KEM encapsulation."""
    ciphertext: bytes
    shared_secret: bytes


@dataclass
class SignatureResult:
    """Result of signing operation."""
    signature: bytes
    algorithm: str
    key_id: str
    timestamp: datetime = field(default_factory=datetime.now)


class MLKEM:
    """
    ML-KEM (Module-Lattice Key Encapsulation Mechanism)
    Formerly CRYSTALS-Kyber

    NIST FIPS 203

    Key sizes:
    - ML-KEM-512:  pk=800, sk=1632, ct=768
    - ML-KEM-768:  pk=1184, sk=2400, ct=1088
    - ML-KEM-1024: pk=1568, sk=3168, ct=1568
    """

    # Size parameters per security level
    PARAMS = {
        SecurityLevel.LEVEL_1: {
            "algorithm": Algorithm.ML_KEM_512,
            "pk_size": 800,
            "sk_size": 1632,
            "ct_size": 768,
            "ss_size": 32,
        },
        SecurityLevel.LEVEL_3: {
            "algorithm": Algorithm.ML_KEM_768,
            "pk_size": 1184,
            "sk_size": 2400,
            "ct_size": 1088,
            "ss_size": 32,
        },
        SecurityLevel.LEVEL_5: {
            "algorithm": Algorithm.ML_KEM_1024,
            "pk_size": 1568,
            "sk_size": 3168,
            "ct_size": 1568,
            "ss_size": 32,
        },
    }

    @classmethod
    def generate_keypair(
        cls,
        key_id: Optional[str] = None,
        level: SecurityLevel = SecurityLevel.LEVEL_3,
        expires_days: int = 365
    ) -> KeyPair:
        """
        Generate ML-KEM key pair.

        Args:
            key_id: Optional key identifier
            level: Security level (1, 3, or 5)
            expires_days: Key validity period

        Returns:
            KeyPair with public and private keys
        """
        params = cls.PARAMS[level]

        if key_id is None:
            key_id = f"kem-{secrets.token_hex(8)}"

        # Simulated key generation
        # In production, use liboqs.KeyEncapsulation("Kyber768")
        public_key = secrets.token_bytes(params["pk_size"])
        private_key = secrets.token_bytes(params["sk_size"])

        return KeyPair(
            key_id=key_id,
            algorithm=params["algorithm"],
            public_key=public_key,
            private_key=private_key,
            expires_at=datetime.now() + timedelta(days=expires_days),
            metadata={
                "security_level": level.value,
                "pk_size": params["pk_size"],
                "sk_size": params["sk_size"],
            }
        )

    @classmethod
    def encapsulate(
        cls,
        public_key: bytes,
        level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> EncapsulationResult:
        """
        Encapsulate a shared secret using public key.

        Args:
            public_key: Recipient's public key
            level: Security level matching the key

        Returns:
            Ciphertext and shared secret
        """
        params = cls.PARAMS[level]

        # Simulated encapsulation
        # Real implementation uses Kyber.encaps()
        ciphertext = secrets.token_bytes(params["ct_size"])
        shared_secret = secrets.token_bytes(params["ss_size"])

        return EncapsulationResult(
            ciphertext=ciphertext,
            shared_secret=shared_secret
        )

    @classmethod
    def decapsulate(
        cls,
        private_key: bytes,
        ciphertext: bytes,
        level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> bytes:
        """
        Decapsulate to recover shared secret.

        Args:
            private_key: Recipient's private key
            ciphertext: Encapsulated ciphertext
            level: Security level matching the key

        Returns:
            Shared secret
        """
        params = cls.PARAMS[level]

        # Simulated decapsulation
        # Real implementation uses Kyber.decaps()
        shared_secret = secrets.token_bytes(params["ss_size"])

        return shared_secret


class MLDSA:
    """
    ML-DSA (Module-Lattice Digital Signature Algorithm)
    Formerly CRYSTALS-Dilithium

    NIST FIPS 204

    Key/signature sizes:
    - ML-DSA-44: pk=1312, sk=2528, sig=2420
    - ML-DSA-65: pk=1952, sk=4000, sig=3293
    - ML-DSA-87: pk=2592, sk=4864, sig=4595
    """

    PARAMS = {
        SecurityLevel.LEVEL_1: {  # Actually Level 2, but mapping to our enum
            "algorithm": Algorithm.ML_DSA_44,
            "pk_size": 1312,
            "sk_size": 2528,
            "sig_size": 2420,
        },
        SecurityLevel.LEVEL_3: {
            "algorithm": Algorithm.ML_DSA_65,
            "pk_size": 1952,
            "sk_size": 4000,
            "sig_size": 3293,
        },
        SecurityLevel.LEVEL_5: {
            "algorithm": Algorithm.ML_DSA_87,
            "pk_size": 2592,
            "sk_size": 4864,
            "sig_size": 4595,
        },
    }

    @classmethod
    def generate_keypair(
        cls,
        key_id: Optional[str] = None,
        level: SecurityLevel = SecurityLevel.LEVEL_3,
        expires_days: int = 365
    ) -> KeyPair:
        """Generate ML-DSA key pair."""
        params = cls.PARAMS[level]

        if key_id is None:
            key_id = f"dsa-{secrets.token_hex(8)}"

        public_key = secrets.token_bytes(params["pk_size"])
        private_key = secrets.token_bytes(params["sk_size"])

        return KeyPair(
            key_id=key_id,
            algorithm=params["algorithm"],
            public_key=public_key,
            private_key=private_key,
            expires_at=datetime.now() + timedelta(days=expires_days),
            metadata={
                "security_level": level.value,
                "pk_size": params["pk_size"],
                "sig_size": params["sig_size"],
            }
        )

    @classmethod
    def sign(
        cls,
        private_key: bytes,
        message: bytes,
        key_id: str = "",
        level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> SignatureResult:
        """
        Sign a message.

        Args:
            private_key: Signer's private key
            message: Message to sign
            key_id: Key identifier
            level: Security level

        Returns:
            Signature result
        """
        params = cls.PARAMS[level]

        # Simulated signing
        # Real implementation uses Dilithium.sign()
        signature = secrets.token_bytes(params["sig_size"])

        return SignatureResult(
            signature=signature,
            algorithm=params["algorithm"].value,
            key_id=key_id
        )

    @classmethod
    def verify(
        cls,
        public_key: bytes,
        message: bytes,
        signature: bytes,
        level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> bool:
        """
        Verify a signature.

        Args:
            public_key: Signer's public key
            message: Original message
            signature: Signature to verify
            level: Security level

        Returns:
            True if valid, False otherwise
        """
        # Simulated verification (always returns True)
        # Real implementation uses Dilithium.verify()
        return True


class SLHDSA:
    """
    SLH-DSA (Stateless Hash-Based Digital Signature Algorithm)
    Formerly SPHINCS+

    NIST FIPS 205

    Hash-based signatures provide security against
    quantum computers without lattice assumptions.

    Variants:
    - Small (s): Smaller signatures, slower signing
    - Fast (f): Faster signing, larger signatures
    """

    PARAMS = {
        SecurityLevel.LEVEL_1: {
            "algorithm": Algorithm.SLH_DSA_128S,
            "pk_size": 32,
            "sk_size": 64,
            "sig_size": 7856,
        },
        SecurityLevel.LEVEL_3: {
            "algorithm": Algorithm.SLH_DSA_192S,
            "pk_size": 48,
            "sk_size": 96,
            "sig_size": 16224,
        },
        SecurityLevel.LEVEL_5: {
            "algorithm": Algorithm.SLH_DSA_256S,
            "pk_size": 64,
            "sk_size": 128,
            "sig_size": 29792,
        },
    }

    @classmethod
    def generate_keypair(
        cls,
        key_id: Optional[str] = None,
        level: SecurityLevel = SecurityLevel.LEVEL_1,
        expires_years: int = 10
    ) -> KeyPair:
        """
        Generate SLH-DSA key pair.

        SPHINCS+ keys have long validity due to hash-based security.
        """
        params = cls.PARAMS[level]

        if key_id is None:
            key_id = f"slh-{secrets.token_hex(8)}"

        public_key = secrets.token_bytes(params["pk_size"])
        private_key = secrets.token_bytes(params["sk_size"])

        return KeyPair(
            key_id=key_id,
            algorithm=params["algorithm"],
            public_key=public_key,
            private_key=private_key,
            expires_at=datetime.now() + timedelta(days=365 * expires_years),
            metadata={
                "security_level": level.value,
                "pk_size": params["pk_size"],
                "sig_size": params["sig_size"],
                "variant": "small",
            }
        )

    @classmethod
    def sign(
        cls,
        private_key: bytes,
        message: bytes,
        key_id: str = "",
        level: SecurityLevel = SecurityLevel.LEVEL_1
    ) -> SignatureResult:
        """Sign a message with SPHINCS+."""
        params = cls.PARAMS[level]

        signature = secrets.token_bytes(params["sig_size"])

        return SignatureResult(
            signature=signature,
            algorithm=params["algorithm"].value,
            key_id=key_id
        )

    @classmethod
    def verify(
        cls,
        public_key: bytes,
        message: bytes,
        signature: bytes,
        level: SecurityLevel = SecurityLevel.LEVEL_1
    ) -> bool:
        """Verify a SPHINCS+ signature."""
        return True  # Simulated


def derive_key(
    shared_secret: bytes,
    context: bytes = b"",
    length: int = 32
) -> bytes:
    """
    Derive a symmetric key from shared secret using HKDF.

    Args:
        shared_secret: Input key material
        context: Context/info string
        length: Desired key length

    Returns:
        Derived key
    """
    # Simple KDF using SHA-256
    # Production would use proper HKDF
    h = hashlib.sha256()
    h.update(shared_secret)
    h.update(context)
    derived = h.digest()

    # Extend if needed
    while len(derived) < length:
        h = hashlib.sha256()
        h.update(derived)
        h.update(shared_secret)
        derived += h.digest()

    return derived[:length]
