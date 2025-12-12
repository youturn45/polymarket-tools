"""Utility tools for Polymarket operations."""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import AssetType, BalanceAllowanceParams

from config.settings import load_config


def check_balance_allowance():
    """
    Check wallet USDC balance and allowance for trading on Polymarket.

    Returns:
        dict: Balance and allowance information including:
            - address: Wallet address
            - collateral_address: USDC token address
            - balance: USDC balance in wallet (in USDC units)
            - allowance: Approved spending allowance (in USDC units)
    """
    config = load_config()

    client = ClobClient(
        host=config.host, chain_id=config.chain_id, key=config.private_key, signature_type=0
    )
    client.set_api_creds(client.create_or_derive_api_creds())

    # Get wallet address
    address = client.get_address()

    # Get USDC collateral address
    collateral_address = client.get_collateral_address()

    # Check balance and allowance for USDC collateral
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance_info = client.get_balance_allowance(params)

    return {
        "address": address,
        "collateral_address": collateral_address,
        "balance_info": balance_info,
    }


if __name__ == "__main__":
    result = check_balance_allowance()

    print(f"Wallet Address: {result['address']}")
    print(f"Balance Info: {result['balance_info']}")
