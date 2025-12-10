from py_clob_client.client import ClobClient

from config.settings import load_config


def generate_api_creds():
    """Generate or derive Polymarket API credentials using private key from config."""
    config = load_config()

    client = ClobClient(
        host=config.host,
        chain_id=config.chain_id,
        key=config.private_key,
    )

    # Create or derive API credentials
    api_creds = client.create_or_derive_api_creds()
    return api_creds


if __name__ == "__main__":
    creds = generate_api_creds()
    print(f"API Key: {creds.api_key}")
    print(f"API Secret: {creds.api_secret}")
    print(f"API Passphrase: {creds.api_passphrase}")
