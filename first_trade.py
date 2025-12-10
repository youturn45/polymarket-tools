from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from config.settings import load_config
# Load settings
config = load_config()

#Select from the following 3 initialization options to match your login method, and remove any unused lines so only one client is initialized.

### Initialization of a client using a Polymarket Proxy associated with a Browser Wallet(Metamask, Coinbase Wallet, etc)
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=2
)

## Create and sign a limit order buying 5 tokens for 0.010c each
#Refer to the API documentation to locate a tokenID: https://docs.polymarket.com/developers/gamma-markets-api/fetch-markets-guide

client.set_api_creds(client.create_or_derive_api_creds()) 

order_args = OrderArgs(
    price=0.008,
    size=100.0,
    side="SELL",
    token_id="114304586861386186441621124384163963092522056897081085884483958561365015034812", #Token ID you want to purchase goes here. Example token: 114304586861386186441621124384163963092522056897081085884483958561365015034812 ( Xi Jinping out in 2025, YES side )
)
signed_order = client.create_order(order_args)

## GTC(Good-Till-Cancelled) Order
resp = client.post_order(signed_order, OrderType.GTC)
print(resp)