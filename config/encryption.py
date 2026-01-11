"""Age encryption/decryption utilities for managing secrets.

Uses subprocess to call the age CLI tool directly, which supports ed25519 SSH keys.
"""

import subprocess
from pathlib import Path
from typing import Union

# Default SSH key paths - can be overridden in function calls
DEFAULT_SSH_PRIVATE_KEY = "~/.ssh/Youturn"
DEFAULT_SSH_PUBLIC_KEY = "~/.ssh/Youturn.pub"


def encrypt_with_ssh(
    data: Union[str, bytes],
    output_file: str,
    public_key_path: str = DEFAULT_SSH_PUBLIC_KEY,
) -> None:
    """Encrypt data using SSH public key and save to file.

    Args:
        data: String or bytes to encrypt
        output_file: Path to save encrypted file
        public_key_path: Path to SSH public key (default: ~/.ssh/Youturn.pub)

    Raises:
        FileNotFoundError: If public key file not found
        subprocess.CalledProcessError: If age command fails
    """
    pub_key_path = Path(public_key_path).expanduser().resolve()
    output_path = Path(output_file).resolve()

    if not pub_key_path.exists():
        raise FileNotFoundError(f"SSH public key not found: {pub_key_path}")

    # Convert string to bytes if needed
    if isinstance(data, str):
        data = data.encode("utf-8")

    try:
        subprocess.run(
            ["age", "-R", str(pub_key_path), "-o", str(output_path)],
            input=data,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Encryption failed: {e.stderr.decode()}") from e


def decrypt_with_ssh(
    encrypted_file: str,
    private_key_path: str = DEFAULT_SSH_PRIVATE_KEY,
) -> str:
    """Decrypt file using SSH private key.

    Args:
        encrypted_file: Path to encrypted .age file
        private_key_path: Path to SSH private key (default: ~/.ssh/Youturn)

    Returns:
        Decrypted data as string

    Raises:
        FileNotFoundError: If encrypted file or private key not found
        subprocess.CalledProcessError: If age command fails
    """
    encrypted_path = Path(encrypted_file).resolve()
    priv_key_path = Path(private_key_path).expanduser().resolve()

    if not encrypted_path.exists():
        raise FileNotFoundError(f"Encrypted file not found: {encrypted_path}")
    if not priv_key_path.exists():
        raise FileNotFoundError(f"SSH private key not found: {priv_key_path}")

    try:
        result = subprocess.run(
            ["age", "-d", "-i", str(priv_key_path), str(encrypted_path)],
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8").strip()
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Decryption failed: {e.stderr.decode()}") from e


# Convenience functions for common operations
def encrypt_secret(
    secret: str,
    output_file: str = "secrets.age",
    public_key_path: str = DEFAULT_SSH_PUBLIC_KEY,
) -> None:
    """Encrypt a secret string to secrets.age file.

    Args:
        secret: Secret string to encrypt (e.g., private key)
        output_file: Output file path (default: secrets.age)
        public_key_path: Path to SSH public key
    """
    encrypt_with_ssh(secret, output_file, public_key_path)


def decrypt_secret(
    secrets_file: str = "secrets.age",
    private_key_path: str = DEFAULT_SSH_PRIVATE_KEY,
) -> str:
    """Decrypt secrets.age file.

    Args:
        secrets_file: Path to encrypted secrets file (default: secrets.age)
        private_key_path: Path to SSH private key

    Returns:
        Decrypted secret string
    """
    return decrypt_with_ssh(secrets_file, private_key_path)
