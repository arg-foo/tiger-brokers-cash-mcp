"""Shared factory for building tigeropen client configuration.

Used by both the TigerClient (REST API) and PushSubscriber (WebSocket events)
to ensure consistent configuration from a single ``Settings`` instance.
"""

from __future__ import annotations

from tigeropen.common.consts import Language
from tigeropen.tiger_open_config import TigerOpenClientConfig

from tiger_mcp.config import Settings


def build_client_config(settings: Settings) -> TigerOpenClientConfig:
    """Create a ``TigerOpenClientConfig`` from application settings.

    Parameters
    ----------
    settings:
        Runtime settings providing credentials and account info.

    Returns
    -------
    TigerOpenClientConfig
        Fully configured client config ready for use with TradeClient,
        QuoteClient, or PushClient.
    """
    client_config = TigerOpenClientConfig(sandbox_debug=False)
    client_config.private_key = settings.private_key_path.read_text()
    client_config.tiger_id = settings.tiger_id
    client_config.account = settings.tiger_account
    client_config.license = "TBSG"
    client_config.language = Language.en_US
    return client_config
