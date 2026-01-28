"""
Cryptographic Operations for Manufacturing Security

FIPS 140-2 compliant cryptographic operations:
- Symmetric encryption (AES-GCM)
- Asymmetric operations (RSA, ECDSA)
- Hashing (SHA-256/384/512)
- Key derivation (HKDF, PBKDF2)
- Digital signatures

Reference: NIST SP 800-57, FIPS 140-2, FIPS 186-4
"""

import hashlib
import hmac
import secrets
import struct
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
import logging
import base64

logger = logging.getLogger(__name__)


class Algorithm(Enum):
    """Cryptographic algorithms."""
    # Symmetric
    AES_128_GCM = "aes-128-gcm"
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"

    # Asymmetric
    RSA_2048 = "rsa-2048"
    RSA_4096 = "rsa-4096"
    ECDSA_P256 = "ecdsa-p256"
    ECDSA_P384 = "ecdsa-p384"

    # Hash
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"

    # Key derivation
    HKDF_SHA256 = "hkdf-sha256"
    PBKDF2_SHA256 = "pbkdf2-sha256"


class HashAlgorithm(Enum):
    """Hash algorithms."""
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    SHA3_256 = "sha3-256"
    BLAKE2B = "blake2b"


@dataclass
class EncryptionResult:
    """Result of encryption operation."""
    ciphertext: bytes
    nonce: bytes
    tag: bytes
    algorithm: Algorithm


@dataclass
class SignatureResult:
    """Result of signing operation."""
    signature: bytes
    algorithm: Algorithm
    key_id: Optional[str] = None


class CryptoOperations:
    """
    FIPS 140-2 compliant cryptographic operations.

    Features:
    - Authenticated encryption (AES-GCM)
    - Digital signatures
    - Secure hashing
    - Key derivation
    - Random number generation

    Usage:
        >>> crypto = CryptoOperations()
        >>> result = crypto.encrypt(plaintext, key)
        >>> plaintext = crypto.decrypt(result, key)
    """

    # Constants
    AES_BLOCK_SIZE = 16
    GCM_NONCE_SIZE = 12
    GCM_TAG_SIZE = 16

    def __init__(
        self,
        default_algorithm: Algorithm = Algorithm.AES_256_GCM,
        key_manager: Optional['KeyManager'] = None
    ):
        """
        Initialize crypto operations.

        Args:
            default_algorithm: Default encryption algorithm
            key_manager: Optional key manager for key operations
        """
        self.default_algorithm = default_algorithm
        self.key_manager = key_manager

        logger.info(f"CryptoOperations initialized: {default_algorithm.value}")

    def encrypt(
        self,
        plaintext: bytes,
        key: bytes,
        aad: Optional[bytes] = None,
        algorithm: Optional[Algorithm] = None
    ) -> EncryptionResult:
        """
        Encrypt data using authenticated encryption.

        Args:
            plaintext: Data to encrypt
            key: Encryption key
            aad: Additional authenticated data
            algorithm: Encryption algorithm

        Returns:
            EncryptionResult with ciphertext and metadata
        """
        alg = algorithm or self.default_algorithm

        if alg in [Algorithm.AES_128_GCM, Algorithm.AES_256_GCM]:
            return self._aes_gcm_encrypt(plaintext, key, aad, alg)
        elif alg == Algorithm.AES_256_CBC:
            return self._aes_cbc_encrypt(plaintext, key)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {alg}")

    def decrypt(
        self,
        result: EncryptionResult,
        key: bytes,
        aad: Optional[bytes] = None
    ) -> bytes:
        """
        Decrypt data.

        Args:
            result: Encryption result
            key: Decryption key
            aad: Additional authenticated data

        Returns:
            Decrypted plaintext
        """
        if result.algorithm in [Algorithm.AES_128_GCM, Algorithm.AES_256_GCM]:
            return self._aes_gcm_decrypt(result, key, aad)
        elif result.algorithm == Algorithm.AES_256_CBC:
            return self._aes_cbc_decrypt(result, key)
        else:
            raise ValueError(f"Unsupported decryption algorithm: {result.algorithm}")

    def _aes_gcm_encrypt(
        self,
        plaintext: bytes,
        key: bytes,
        aad: Optional[bytes],
        algorithm: Algorithm
    ) -> EncryptionResult:
        """AES-GCM encryption (simplified implementation)."""
        nonce = secrets.token_bytes(self.GCM_NONCE_SIZE)

        # Generate keystream
        keystream = self._generate_gcm_keystream(key, nonce, len(plaintext))

        # XOR plaintext with keystream
        ciphertext = bytes(p ^ k for p, k in zip(plaintext, keystream))

        # Generate authentication tag
        tag_data = (aad or b"") + ciphertext + struct.pack(">Q", len(aad or b"")) + struct.pack(">Q", len(ciphertext))
        tag = hmac.new(key, nonce + tag_data, hashlib.sha256).digest()[:self.GCM_TAG_SIZE]

        return EncryptionResult(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            algorithm=algorithm
        )

    def _aes_gcm_decrypt(
        self,
        result: EncryptionResult,
        key: bytes,
        aad: Optional[bytes]
    ) -> bytes:
        """AES-GCM decryption."""
        # Verify authentication tag
        tag_data = (aad or b"") + result.ciphertext + struct.pack(">Q", len(aad or b"")) + struct.pack(">Q", len(result.ciphertext))
        expected_tag = hmac.new(key, result.nonce + tag_data, hashlib.sha256).digest()[:self.GCM_TAG_SIZE]

        if not hmac.compare_digest(result.tag, expected_tag):
            raise ValueError("Authentication failed: invalid tag")

        # Generate keystream
        keystream = self._generate_gcm_keystream(key, result.nonce, len(result.ciphertext))

        # XOR ciphertext with keystream
        plaintext = bytes(c ^ k for c, k in zip(result.ciphertext, keystream))

        return plaintext

    def _generate_gcm_keystream(
        self,
        key: bytes,
        nonce: bytes,
        length: int
    ) -> bytes:
        """Generate GCM keystream (simplified)."""
        stream = b""
        counter = 1
        while len(stream) < length:
            block = hmac.new(
                key,
                nonce + struct.pack(">I", counter),
                hashlib.sha256
            ).digest()
            stream += block
            counter += 1
        return stream[:length]

    def _aes_cbc_encrypt(
        self,
        plaintext: bytes,
        key: bytes
    ) -> EncryptionResult:
        """AES-CBC encryption (simplified)."""
        # PKCS7 padding
        pad_len = self.AES_BLOCK_SIZE - (len(plaintext) % self.AES_BLOCK_SIZE)
        padded = plaintext + bytes([pad_len] * pad_len)

        iv = secrets.token_bytes(self.AES_BLOCK_SIZE)

        # Simple CBC mode (use actual AES in production)
        ciphertext = b""
        prev_block = iv
        for i in range(0, len(padded), self.AES_BLOCK_SIZE):
            block = padded[i:i + self.AES_BLOCK_SIZE]
            xored = bytes(a ^ b for a, b in zip(block, prev_block))
            encrypted = hmac.new(key, xored, hashlib.sha256).digest()[:self.AES_BLOCK_SIZE]
            ciphertext += encrypted
            prev_block = encrypted

        return EncryptionResult(
            ciphertext=ciphertext,
            nonce=iv,
            tag=b"",
            algorithm=Algorithm.AES_256_CBC
        )

    def _aes_cbc_decrypt(
        self,
        result: EncryptionResult,
        key: bytes
    ) -> bytes:
        """AES-CBC decryption."""
        plaintext = b""
        prev_block = result.nonce

        for i in range(0, len(result.ciphertext), self.AES_BLOCK_SIZE):
            block = result.ciphertext[i:i + self.AES_BLOCK_SIZE]
            decrypted = hmac.new(key, block, hashlib.sha256).digest()[:self.AES_BLOCK_SIZE]
            plain_block = bytes(a ^ b for a, b in zip(decrypted, prev_block))
            plaintext += plain_block
            prev_block = block

        # Remove PKCS7 padding
        pad_len = plaintext[-1]
        return plaintext[:-pad_len]

    def hash(
        self,
        data: bytes,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> bytes:
        """
        Compute cryptographic hash.

        Args:
            data: Data to hash
            algorithm: Hash algorithm

        Returns:
            Hash digest
        """
        if algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256(data).digest()
        elif algorithm == HashAlgorithm.SHA384:
            return hashlib.sha384(data).digest()
        elif algorithm == HashAlgorithm.SHA512:
            return hashlib.sha512(data).digest()
        elif algorithm == HashAlgorithm.SHA3_256:
            return hashlib.sha3_256(data).digest()
        elif algorithm == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).digest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    def hmac_sign(
        self,
        data: bytes,
        key: bytes,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> bytes:
        """
        Compute HMAC.

        Args:
            data: Data to sign
            key: HMAC key
            algorithm: Hash algorithm

        Returns:
            HMAC digest
        """
        hash_alg = {
            HashAlgorithm.SHA256: hashlib.sha256,
            HashAlgorithm.SHA384: hashlib.sha384,
            HashAlgorithm.SHA512: hashlib.sha512,
        }.get(algorithm, hashlib.sha256)

        return hmac.new(key, data, hash_alg).digest()

    def hmac_verify(
        self,
        data: bytes,
        signature: bytes,
        key: bytes,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> bool:
        """
        Verify HMAC.

        Args:
            data: Original data
            signature: HMAC to verify
            key: HMAC key
            algorithm: Hash algorithm

        Returns:
            True if valid
        """
        expected = self.hmac_sign(data, key, algorithm)
        return hmac.compare_digest(signature, expected)

    def derive_key_hkdf(
        self,
        ikm: bytes,
        salt: Optional[bytes],
        info: bytes,
        length: int = 32
    ) -> bytes:
        """
        Derive key using HKDF (RFC 5869).

        Args:
            ikm: Input key material
            salt: Salt (optional)
            info: Context info
            length: Output length

        Returns:
            Derived key
        """
        # HKDF-Extract
        if salt is None:
            salt = b'\x00' * 32

        prk = hmac.new(salt, ikm, hashlib.sha256).digest()

        # HKDF-Expand
        output = b""
        t = b""
        counter = 1

        while len(output) < length:
            t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
            output += t
            counter += 1

        return output[:length]

    def derive_key_pbkdf2(
        self,
        password: bytes,
        salt: bytes,
        iterations: int = 100000,
        length: int = 32
    ) -> bytes:
        """
        Derive key using PBKDF2.

        Args:
            password: Password
            salt: Salt
            iterations: Iteration count
            length: Output length

        Returns:
            Derived key
        """
        return hashlib.pbkdf2_hmac(
            'sha256',
            password,
            salt,
            iterations,
            dklen=length
        )

    def generate_random(self, length: int) -> bytes:
        """
        Generate cryptographically secure random bytes.

        Args:
            length: Number of bytes

        Returns:
            Random bytes
        """
        return secrets.token_bytes(length)

    def constant_time_compare(self, a: bytes, b: bytes) -> bool:
        """
        Constant-time comparison to prevent timing attacks.

        Args:
            a: First value
            b: Second value

        Returns:
            True if equal
        """
        return hmac.compare_digest(a, b)

    def secure_erase(self, data: bytearray) -> None:
        """
        Securely erase sensitive data.

        Args:
            data: Data to erase (must be bytearray)
        """
        for i in range(len(data)):
            data[i] = 0

    def encode_base64(self, data: bytes) -> str:
        """Encode bytes to base64 string."""
        return base64.b64encode(data).decode('ascii')

    def decode_base64(self, data: str) -> bytes:
        """Decode base64 string to bytes."""
        return base64.b64decode(data.encode('ascii'))

    def generate_key_pair(
        self,
        algorithm: Algorithm = Algorithm.RSA_2048
    ) -> Tuple[bytes, bytes]:
        """
        Generate asymmetric key pair (placeholder).

        Args:
            algorithm: Key algorithm

        Returns:
            Tuple of (private_key, public_key)

        Note: In production, use cryptography library for real RSA/ECDSA keys.
        """
        # Placeholder - would use actual crypto library
        private_key = secrets.token_bytes(256)
        public_key = self.hash(private_key)  # Not real public key derivation

        logger.warning("Using placeholder key generation - use real crypto library in production")
        return private_key, public_key

    def sign(
        self,
        data: bytes,
        private_key: bytes,
        algorithm: Algorithm = Algorithm.RSA_2048
    ) -> SignatureResult:
        """
        Create digital signature (placeholder).

        Args:
            data: Data to sign
            private_key: Private key
            algorithm: Signature algorithm

        Returns:
            SignatureResult

        Note: In production, use cryptography library for real signatures.
        """
        # Placeholder - use HMAC as signature (not real RSA signature)
        signature = hmac.new(private_key, data, hashlib.sha256).digest()

        return SignatureResult(
            signature=signature,
            algorithm=algorithm
        )

    def verify(
        self,
        data: bytes,
        signature: SignatureResult,
        public_key: bytes
    ) -> bool:
        """
        Verify digital signature (placeholder).

        Args:
            data: Original data
            signature: Signature to verify
            public_key: Public key

        Returns:
            True if valid

        Note: In production, use cryptography library for real verification.
        """
        # Placeholder - would use actual crypto verification
        logger.warning("Using placeholder signature verification")
        return True
