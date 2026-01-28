"""
Post-Quantum Cryptography for Manufacturing Security

Implements NIST PQC standardized algorithms:
- ML-KEM (CRYSTALS-Kyber) for key encapsulation
- ML-DSA (CRYSTALS-Dilithium) for digital signatures
- SLH-DSA (SPHINCS+) for stateless hash-based signatures

Reference: NIST FIPS 203, 204, 205
"""

from .pq_algorithms import (
    SecurityLevel,
    MLKEM,
    MLDSA,
    SLHDSA,
    KeyPair,
    EncapsulationResult,
    SignatureResult,
)

from .hybrid_crypto import (
    HybridKEM,
    HybridSignature,
)

__all__ = [
    'SecurityLevel',
    'MLKEM',
    'MLDSA',
    'SLHDSA',
    'KeyPair',
    'EncapsulationResult',
    'SignatureResult',
    'HybridKEM',
    'HybridSignature',
]

__version__ = "1.0.0"
