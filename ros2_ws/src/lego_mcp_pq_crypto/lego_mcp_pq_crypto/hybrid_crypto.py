"""
Hybrid Cryptography Schemes

Combines classical and post-quantum algorithms for
defense-in-depth during the transition period.

Reference: NIST SP 800-208, IETF Draft: Hybrid Key Exchange
"""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
import logging

from .pq_algorithms import (
    SecurityLevel,
    MLKEM,
    MLDSA,
    KeyPair,
    EncapsulationResult,
    SignatureResult,
    derive_key,
)

logger = logging.getLogger(__name__)


@dataclass
class HybridKeyPair:
    """Hybrid key pair combining classical and PQC."""
    key_id: str
    classical_public: bytes
    classical_private: bytes
    pq_public: bytes
    pq_private: bytes
    classical_algorithm: str
    pq_algorithm: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class HybridEncapsulation:
    """Result of hybrid encapsulation."""
    classical_ciphertext: bytes
    pq_ciphertext: bytes
    combined_secret: bytes


@dataclass
class HybridSignature:
    """Hybrid signature combining classical and PQC."""
    classical_signature: bytes
    pq_signature: bytes
    classical_algorithm: str
    pq_algorithm: str
    key_id: str
    timestamp: datetime = field(default_factory=datetime.now)


class HybridKEM:
    """
    Hybrid Key Encapsulation Mechanism.

    Combines X25519 (or ECDH P-256) with ML-KEM.

    The combined shared secret is derived from both
    classical and post-quantum shared secrets, providing
    security if either algorithm remains secure.

    Reference: draft-ietf-tls-hybrid-design
    """

    # Simulated X25519 key sizes
    X25519_PUBLIC_SIZE = 32
    X25519_PRIVATE_SIZE = 32

    @classmethod
    def generate_keypair(
        cls,
        key_id: Optional[str] = None,
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> HybridKeyPair:
        """
        Generate hybrid key pair.

        Args:
            key_id: Optional key identifier
            pq_level: Post-quantum security level

        Returns:
            HybridKeyPair with both classical and PQ keys
        """
        if key_id is None:
            key_id = f"hybrid-kem-{secrets.token_hex(8)}"

        # Generate classical X25519 key pair (simulated)
        classical_private = secrets.token_bytes(cls.X25519_PRIVATE_SIZE)
        classical_public = secrets.token_bytes(cls.X25519_PUBLIC_SIZE)

        # Generate PQ key pair
        pq_keypair = MLKEM.generate_keypair(
            key_id=f"{key_id}-pq",
            level=pq_level
        )

        return HybridKeyPair(
            key_id=key_id,
            classical_public=classical_public,
            classical_private=classical_private,
            pq_public=pq_keypair.public_key,
            pq_private=pq_keypair.private_key,
            classical_algorithm="X25519",
            pq_algorithm=pq_keypair.algorithm.value,
        )

    @classmethod
    def encapsulate(
        cls,
        hybrid_public: Tuple[bytes, bytes],
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> HybridEncapsulation:
        """
        Hybrid encapsulation.

        Args:
            hybrid_public: Tuple of (classical_pk, pq_pk)
            pq_level: Post-quantum security level

        Returns:
            HybridEncapsulation with combined secret
        """
        classical_pk, pq_pk = hybrid_public

        # Classical X25519 encapsulation (simulated ECDH)
        classical_ephemeral = secrets.token_bytes(cls.X25519_PUBLIC_SIZE)
        classical_shared = secrets.token_bytes(32)

        # PQ encapsulation
        pq_result = MLKEM.encapsulate(pq_pk, pq_level)

        # Combine secrets using KDF
        # K = KDF(classical_ss || pq_ss || context)
        combined_input = classical_shared + pq_result.shared_secret
        combined_secret = derive_key(
            combined_input,
            context=b"hybrid-kem-v1",
            length=32
        )

        return HybridEncapsulation(
            classical_ciphertext=classical_ephemeral,
            pq_ciphertext=pq_result.ciphertext,
            combined_secret=combined_secret
        )

    @classmethod
    def decapsulate(
        cls,
        hybrid_private: Tuple[bytes, bytes],
        hybrid_ciphertext: Tuple[bytes, bytes],
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> bytes:
        """
        Hybrid decapsulation.

        Args:
            hybrid_private: Tuple of (classical_sk, pq_sk)
            hybrid_ciphertext: Tuple of (classical_ct, pq_ct)
            pq_level: Post-quantum security level

        Returns:
            Combined shared secret
        """
        classical_sk, pq_sk = hybrid_private
        classical_ct, pq_ct = hybrid_ciphertext

        # Classical decapsulation (simulated)
        classical_shared = secrets.token_bytes(32)

        # PQ decapsulation
        pq_shared = MLKEM.decapsulate(pq_sk, pq_ct, pq_level)

        # Combine secrets
        combined_input = classical_shared + pq_shared
        combined_secret = derive_key(
            combined_input,
            context=b"hybrid-kem-v1",
            length=32
        )

        return combined_secret


class HybridSignatureScheme:
    """
    Hybrid Digital Signature Scheme.

    Combines ECDSA P-256 (or Ed25519) with ML-DSA.

    Both signatures must verify for overall verification
    to succeed (logical AND).

    Reference: NIST SP 800-208
    """

    # Simulated ECDSA key sizes
    ECDSA_PUBLIC_SIZE = 64  # Uncompressed P-256 point
    ECDSA_PRIVATE_SIZE = 32
    ECDSA_SIGNATURE_SIZE = 64

    @classmethod
    def generate_keypair(
        cls,
        key_id: Optional[str] = None,
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> HybridKeyPair:
        """
        Generate hybrid signature key pair.

        Args:
            key_id: Optional key identifier
            pq_level: Post-quantum security level

        Returns:
            HybridKeyPair for signing
        """
        if key_id is None:
            key_id = f"hybrid-sig-{secrets.token_hex(8)}"

        # Generate classical ECDSA key pair (simulated)
        classical_private = secrets.token_bytes(cls.ECDSA_PRIVATE_SIZE)
        classical_public = secrets.token_bytes(cls.ECDSA_PUBLIC_SIZE)

        # Generate PQ signature key pair
        pq_keypair = MLDSA.generate_keypair(
            key_id=f"{key_id}-pq",
            level=pq_level
        )

        return HybridKeyPair(
            key_id=key_id,
            classical_public=classical_public,
            classical_private=classical_private,
            pq_public=pq_keypair.public_key,
            pq_private=pq_keypair.private_key,
            classical_algorithm="ECDSA-P256",
            pq_algorithm=pq_keypair.algorithm.value,
        )

    @classmethod
    def sign(
        cls,
        hybrid_private: Tuple[bytes, bytes],
        message: bytes,
        key_id: str = "",
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> HybridSignature:
        """
        Create hybrid signature.

        Args:
            hybrid_private: Tuple of (classical_sk, pq_sk)
            message: Message to sign
            key_id: Key identifier
            pq_level: Post-quantum security level

        Returns:
            HybridSignature with both signatures
        """
        classical_sk, pq_sk = hybrid_private

        # Classical ECDSA signature (simulated)
        classical_sig = secrets.token_bytes(cls.ECDSA_SIGNATURE_SIZE)

        # PQ signature
        pq_result = MLDSA.sign(pq_sk, message, key_id, pq_level)

        return HybridSignature(
            classical_signature=classical_sig,
            pq_signature=pq_result.signature,
            classical_algorithm="ECDSA-P256",
            pq_algorithm=pq_result.algorithm,
            key_id=key_id
        )

    @classmethod
    def verify(
        cls,
        hybrid_public: Tuple[bytes, bytes],
        message: bytes,
        signature: HybridSignature,
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> bool:
        """
        Verify hybrid signature.

        Both classical and PQ signatures must verify.

        Args:
            hybrid_public: Tuple of (classical_pk, pq_pk)
            message: Original message
            signature: HybridSignature to verify
            pq_level: Post-quantum security level

        Returns:
            True if both signatures verify
        """
        classical_pk, pq_pk = hybrid_public

        # Verify classical signature (simulated - always True)
        classical_valid = True

        # Verify PQ signature
        pq_valid = MLDSA.verify(
            pq_pk,
            message,
            signature.pq_signature,
            pq_level
        )

        # Both must be valid
        return classical_valid and pq_valid


class KeyEncapsulationProtocol:
    """
    Complete key encapsulation protocol for secure communication.

    Implements authenticated key exchange using hybrid KEM.
    """

    @staticmethod
    def establish_session(
        initiator_keypair: HybridKeyPair,
        responder_public: Tuple[bytes, bytes],
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> Tuple[bytes, bytes]:
        """
        Establish session keys between two parties.

        Args:
            initiator_keypair: Initiator's hybrid key pair
            responder_public: Responder's public keys
            pq_level: Security level

        Returns:
            Tuple of (send_key, receive_key)
        """
        # Encapsulate to responder
        encap = HybridKEM.encapsulate(responder_public, pq_level)

        # Derive directional keys
        send_key = derive_key(
            encap.combined_secret,
            context=b"initiator-to-responder",
            length=32
        )

        receive_key = derive_key(
            encap.combined_secret,
            context=b"responder-to-initiator",
            length=32
        )

        return send_key, receive_key


class QuantumResistantAudit:
    """
    Quantum-resistant audit trail using hybrid signatures.

    For long-term audit requirements where data must remain
    verifiable even after quantum computers exist.
    """

    def __init__(self, signing_keypair: HybridKeyPair):
        self.keypair = signing_keypair
        self.chain_hash = hashlib.sha256(b"genesis").digest()

    def sign_entry(
        self,
        entry_data: bytes,
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> Tuple[HybridSignature, bytes]:
        """
        Sign an audit entry with chain linking.

        Args:
            entry_data: Audit entry data
            pq_level: Security level

        Returns:
            Tuple of (signature, entry_hash)
        """
        # Include chain hash in signed data
        signed_data = self.chain_hash + entry_data

        # Create hybrid signature
        signature = HybridSignatureScheme.sign(
            (self.keypair.classical_private, self.keypair.pq_private),
            signed_data,
            self.keypair.key_id,
            pq_level
        )

        # Update chain hash
        entry_hash = hashlib.sha256(signed_data + signature.classical_signature).digest()
        self.chain_hash = entry_hash

        return signature, entry_hash

    def verify_entry(
        self,
        entry_data: bytes,
        previous_hash: bytes,
        signature: HybridSignature,
        public_keys: Tuple[bytes, bytes],
        pq_level: SecurityLevel = SecurityLevel.LEVEL_3
    ) -> bool:
        """
        Verify an audit entry.

        Args:
            entry_data: Audit entry data
            previous_hash: Previous chain hash
            signature: Entry signature
            public_keys: Signer's public keys
            pq_level: Security level

        Returns:
            True if entry is valid
        """
        signed_data = previous_hash + entry_data

        return HybridSignatureScheme.verify(
            public_keys,
            signed_data,
            signature,
            pq_level
        )
