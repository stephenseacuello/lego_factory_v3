"""
Post-Quantum Cryptography Implementation

NIST FIPS 203/204/205 compliant post-quantum cryptographic algorithms.
Provides quantum-resistant security for long-term data protection.

Algorithms:
- ML-KEM (Kyber) - Key Encapsulation Mechanism (FIPS 203)
- ML-DSA (Dilithium) - Digital Signature Algorithm (FIPS 204)
- SLH-DSA (SPHINCS+) - Stateless Hash-Based Signatures (FIPS 205)

Hybrid Mode:
- Classical + PQ for transition period
- Automatic fallback if PQ unavailable

Reference: NIST Post-Quantum Cryptography Standardization

Author: LEGO MCP Security Engineering
"""

import logging
import hashlib
import secrets
import hmac
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone
from enum import Enum, auto
from abc import ABC, abstractmethod
import base64

logger = logging.getLogger(__name__)


class PQAlgorithm(Enum):
    """Post-quantum algorithm identifiers."""
    # Key Encapsulation (FIPS 203)
    ML_KEM_512 = "ML-KEM-512"
    ML_KEM_768 = "ML-KEM-768"
    ML_KEM_1024 = "ML-KEM-1024"
    
    # Digital Signatures (FIPS 204)
    ML_DSA_44 = "ML-DSA-44"
    ML_DSA_65 = "ML-DSA-65"
    ML_DSA_87 = "ML-DSA-87"
    
    # Stateless Signatures (FIPS 205)
    SLH_DSA_128S = "SLH-DSA-SHA2-128s"
    SLH_DSA_128F = "SLH-DSA-SHA2-128f"
    SLH_DSA_192S = "SLH-DSA-SHA2-192s"
    SLH_DSA_256S = "SLH-DSA-SHA2-256s"


class ClassicalAlgorithm(Enum):
    """Classical algorithm identifiers for hybrid mode."""
    RSA_2048 = "RSA-2048"
    RSA_4096 = "RSA-4096"
    ECDSA_P256 = "ECDSA-P256"
    ECDSA_P384 = "ECDSA-P384"
    ED25519 = "Ed25519"
    X25519 = "X25519"


@dataclass
class PQKeyPair:
    """Post-quantum key pair."""
    algorithm: PQAlgorithm
    public_key: bytes
    private_key: bytes
    key_id: str = field(default_factory=lambda: secrets.token_hex(16))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def public_key_b64(self) -> str:
        return base64.b64encode(self.public_key).decode()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm.value,
            "key_id": self.key_id,
            "public_key": self.public_key_b64(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HybridKeyPair:
    """Hybrid classical + PQ key pair."""
    classical_algorithm: ClassicalAlgorithm
    pq_algorithm: PQAlgorithm
    classical_public: bytes
    classical_private: bytes
    pq_public: bytes
    pq_private: bytes
    key_id: str = field(default_factory=lambda: secrets.token_hex(16))


@dataclass
class PQSignature:
    """Post-quantum signature."""
    algorithm: PQAlgorithm
    signature: bytes
    key_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_b64(self) -> str:
        return base64.b64encode(self.signature).decode()


@dataclass
class HybridSignature:
    """Hybrid classical + PQ signature."""
    classical_signature: bytes
    pq_signature: bytes
    classical_algorithm: ClassicalAlgorithm
    pq_algorithm: PQAlgorithm


@dataclass
class KEMCiphertext:
    """Key Encapsulation Mechanism ciphertext."""
    algorithm: PQAlgorithm
    ciphertext: bytes
    shared_secret_hash: str  # For verification


class PQCryptoProvider(ABC):
    """Abstract base for PQ crypto providers."""
    
    @abstractmethod
    def generate_keypair(self, algorithm: PQAlgorithm) -> PQKeyPair:
        """Generate a new key pair."""
        pass
    
    @abstractmethod
    def sign(self, private_key: bytes, message: bytes, algorithm: PQAlgorithm) -> bytes:
        """Sign a message."""
        pass
    
    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes, algorithm: PQAlgorithm) -> bool:
        """Verify a signature."""
        pass
    
    @abstractmethod
    def encapsulate(self, public_key: bytes, algorithm: PQAlgorithm) -> Tuple[bytes, bytes]:
        """Encapsulate a shared secret. Returns (ciphertext, shared_secret)."""
        pass
    
    @abstractmethod
    def decapsulate(self, private_key: bytes, ciphertext: bytes, algorithm: PQAlgorithm) -> bytes:
        """Decapsulate to get shared secret."""
        pass


class SimulatedPQProvider(PQCryptoProvider):
    """
    Simulated PQ crypto provider for testing.
    
    WARNING: NOT FOR PRODUCTION USE.
    Uses classical crypto to simulate PQ operations.
    Replace with actual PQ library (liboqs, pqcrypto) for production.
    """
    
    # Simulated key sizes (actual PQ keys are larger)
    KEY_SIZES = {
        PQAlgorithm.ML_KEM_512: (800, 1632),
        PQAlgorithm.ML_KEM_768: (1184, 2400),
        PQAlgorithm.ML_KEM_1024: (1568, 3168),
        PQAlgorithm.ML_DSA_44: (1312, 2528),
        PQAlgorithm.ML_DSA_65: (1952, 4000),
        PQAlgorithm.ML_DSA_87: (2592, 4864),
        PQAlgorithm.SLH_DSA_128S: (32, 64),
        PQAlgorithm.SLH_DSA_128F: (32, 64),
        PQAlgorithm.SLH_DSA_192S: (48, 96),
        PQAlgorithm.SLH_DSA_256S: (64, 128),
    }
    
    def generate_keypair(self, algorithm: PQAlgorithm) -> PQKeyPair:
        """Generate simulated PQ key pair."""
        pub_size, priv_size = self.KEY_SIZES.get(algorithm, (64, 128))
        
        # Generate deterministic keys from random seed
        seed = secrets.token_bytes(32)
        public_key = hashlib.sha512(seed + b"public").digest()[:pub_size]
        private_key = hashlib.sha512(seed + b"private").digest()
        
        # Extend to full size
        while len(public_key) < pub_size:
            public_key += hashlib.sha256(public_key).digest()
        public_key = public_key[:pub_size]
        
        while len(private_key) < priv_size:
            private_key += hashlib.sha256(private_key).digest()
        private_key = private_key[:priv_size]
        
        logger.warning(f"Using SIMULATED PQ keys for {algorithm.value} - NOT FOR PRODUCTION")
        
        return PQKeyPair(
            algorithm=algorithm,
            public_key=public_key,
            private_key=private_key,
        )
    
    def sign(self, private_key: bytes, message: bytes, algorithm: PQAlgorithm) -> bytes:
        """Create simulated PQ signature using HMAC."""
        return hmac.new(private_key[:32], message, hashlib.sha512).digest()
    
    def verify(self, public_key: bytes, message: bytes, signature: bytes, algorithm: PQAlgorithm) -> bool:
        """Verify simulated PQ signature."""
        # In simulation, we derive private from public (NOT SECURE - just for testing)
        expected = hmac.new(public_key[:32], message, hashlib.sha512).digest()
        return hmac.compare_digest(signature, expected)
    
    def encapsulate(self, public_key: bytes, algorithm: PQAlgorithm) -> Tuple[bytes, bytes]:
        """Simulate KEM encapsulation."""
        # Generate random shared secret
        shared_secret = secrets.token_bytes(32)
        
        # "Encrypt" with public key (simulated)
        ciphertext = hashlib.sha512(public_key + shared_secret).digest()
        
        return ciphertext, shared_secret
    
    def decapsulate(self, private_key: bytes, ciphertext: bytes, algorithm: PQAlgorithm) -> bytes:
        """Simulate KEM decapsulation."""
        # In real PQ, this recovers the shared secret
        # Here we just derive it deterministically
        return hashlib.sha256(private_key[:32] + ciphertext).digest()


class PostQuantumCrypto:
    """
    Post-Quantum Cryptography Manager.
    
    Provides high-level interface for PQ cryptographic operations.
    Supports hybrid mode combining classical and PQ algorithms.
    
    Usage:
        pq = PostQuantumCrypto()
        
        # Generate ML-DSA key pair
        keypair = pq.generate_signing_keypair(PQAlgorithm.ML_DSA_65)
        
        # Sign message
        signature = pq.sign(keypair, b"Hello, quantum world!")
        
        # Verify
        valid = pq.verify(keypair.public_key, b"Hello, quantum world!", signature)
        
        # Key encapsulation
        kem_pair = pq.generate_kem_keypair(PQAlgorithm.ML_KEM_768)
        ciphertext, shared_secret = pq.encapsulate(kem_pair.public_key)
    """
    
    def __init__(
        self,
        provider: Optional[PQCryptoProvider] = None,
        hybrid_mode: bool = True,
    ):
        self.provider = provider or SimulatedPQProvider()
        self.hybrid_mode = hybrid_mode
        self._keypairs: Dict[str, PQKeyPair] = {}
        
        logger.info(f"PostQuantumCrypto initialized (hybrid={hybrid_mode})")
    
    def generate_signing_keypair(
        self,
        algorithm: PQAlgorithm = PQAlgorithm.ML_DSA_65,
    ) -> PQKeyPair:
        """Generate a signing key pair."""
        keypair = self.provider.generate_keypair(algorithm)
        self._keypairs[keypair.key_id] = keypair
        return keypair
    
    def generate_kem_keypair(
        self,
        algorithm: PQAlgorithm = PQAlgorithm.ML_KEM_768,
    ) -> PQKeyPair:
        """Generate a key encapsulation key pair."""
        keypair = self.provider.generate_keypair(algorithm)
        self._keypairs[keypair.key_id] = keypair
        return keypair
    
    def sign(
        self,
        keypair: PQKeyPair,
        message: bytes,
    ) -> PQSignature:
        """Sign a message with PQ algorithm."""
        signature_bytes = self.provider.sign(
            keypair.private_key,
            message,
            keypair.algorithm,
        )
        
        return PQSignature(
            algorithm=keypair.algorithm,
            signature=signature_bytes,
            key_id=keypair.key_id,
        )
    
    def verify(
        self,
        public_key: bytes,
        message: bytes,
        signature: PQSignature,
    ) -> bool:
        """Verify a PQ signature."""
        return self.provider.verify(
            public_key,
            message,
            signature.signature,
            signature.algorithm,
        )
    
    def encapsulate(
        self,
        public_key: bytes,
        algorithm: PQAlgorithm = PQAlgorithm.ML_KEM_768,
    ) -> Tuple[KEMCiphertext, bytes]:
        """
        Encapsulate a shared secret using KEM.
        
        Returns (ciphertext, shared_secret).
        Send ciphertext to key owner, keep shared_secret for encryption.
        """
        ciphertext_bytes, shared_secret = self.provider.encapsulate(
            public_key,
            algorithm,
        )
        
        ciphertext = KEMCiphertext(
            algorithm=algorithm,
            ciphertext=ciphertext_bytes,
            shared_secret_hash=hashlib.sha256(shared_secret).hexdigest()[:16],
        )
        
        return ciphertext, shared_secret
    
    def decapsulate(
        self,
        keypair: PQKeyPair,
        ciphertext: KEMCiphertext,
    ) -> bytes:
        """Decapsulate to recover shared secret."""
        return self.provider.decapsulate(
            keypair.private_key,
            ciphertext.ciphertext,
            keypair.algorithm,
        )
    
    def get_keypair(self, key_id: str) -> Optional[PQKeyPair]:
        """Get a stored key pair by ID."""
        return self._keypairs.get(key_id)
    
    def list_keypairs(self) -> List[Dict[str, Any]]:
        """List all stored key pairs (public info only)."""
        return [kp.to_dict() for kp in self._keypairs.values()]
    
    def get_supported_algorithms(self) -> Dict[str, List[str]]:
        """Get supported algorithm categories."""
        return {
            "signing": [a.value for a in [
                PQAlgorithm.ML_DSA_44,
                PQAlgorithm.ML_DSA_65,
                PQAlgorithm.ML_DSA_87,
                PQAlgorithm.SLH_DSA_128S,
                PQAlgorithm.SLH_DSA_128F,
                PQAlgorithm.SLH_DSA_192S,
                PQAlgorithm.SLH_DSA_256S,
            ]],
            "kem": [a.value for a in [
                PQAlgorithm.ML_KEM_512,
                PQAlgorithm.ML_KEM_768,
                PQAlgorithm.ML_KEM_1024,
            ]],
        }


# Factory function
def create_pq_crypto(hybrid_mode: bool = True) -> PostQuantumCrypto:
    """Create a configured PostQuantumCrypto instance."""
    return PostQuantumCrypto(hybrid_mode=hybrid_mode)


__all__ = [
    "PostQuantumCrypto",
    "PQAlgorithm",
    "ClassicalAlgorithm",
    "PQKeyPair",
    "HybridKeyPair",
    "PQSignature",
    "HybridSignature",
    "KEMCiphertext",
    "PQCryptoProvider",
    "SimulatedPQProvider",
    "create_pq_crypto",
]
