"""Test script to generate API credentials from a private key."""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds


def generate_api_key_from_private_key(
    private_key: str,
    host: str = "https://clob.polymarket.com",
    chain_id: int = 137,
) -> ApiCreds:
    """Generate Polymarket API credentials from a private key.

    This function takes an Ethereum private key and derives the API credentials
    (API key, secret, and passphrase) needed to authenticate with the Polymarket API.

    Args:
        private_key: Ethereum private key (without 0x prefix)
        host: Polymarket CLOB API host URL (default: https://clob.polymarket.com)
        chain_id: Blockchain chain ID (default: 137 for Polygon)

    Returns:
        ApiCreds object containing:
            - api_key: The API key for authentication
            - api_secret: The API secret for signing requests
            - api_passphrase: The passphrase for the API

    Example:
        >>> private_key = "your_private_key_here"
        >>> creds = generate_api_key_from_private_key(private_key)
        >>> print(f"API Key: {creds.api_key}")
        >>> print(f"API Passphrase: {creds.api_passphrase}")
    """
    # Create a ClobClient instance with the private key
    client = ClobClient(
        host=host,
        key=private_key,
        chain_id=chain_id,
    )

    # Generate or derive API credentials from the private key
    api_creds = client.create_or_derive_api_creds()

    return api_creds


def main():
    """Main function to demonstrate API key generation."""
    import os
    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    # Get private key from environment
    private_key = os.getenv("PRIVATE_KEY")

    if not private_key:
        print("Error: PRIVATE_KEY not found in .env file")
        print("Please create a .env file with your PRIVATE_KEY")
        return

    print("Generating API credentials from private key...")
    print("=" * 60)

    try:
        # Generate API credentials
        creds = generate_api_key_from_private_key(private_key)

        # Display the credentials
        print(f"\n✓ API credentials generated successfully!\n")
        print(f"API Key:        {creds.api_key}")
        print(f"API Passphrase: {creds.api_passphrase}")
        print(f"API Secret:     {creds.api_secret[:8]}...{creds.api_secret[-4:]}")
        print("\n" + "=" * 60)
        print("\nYou can now use these credentials to authenticate with Polymarket API")

    except Exception as e:
        print(f"\n❌ Error generating API credentials: {e}")
        raise


if __name__ == "__main__":
    main()
