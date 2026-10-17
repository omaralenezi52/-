"""محوّلات المنصات — عزل النظام عن أي وسيط معيّن."""
from .base import BrokerAdapter, NotSupportedError, OrderResult
from .paper import PaperBroker
from .derayah import DerayahAdapter
from .ibkr import IBKRAdapter
from .alpaca import AlpacaAdapter

__all__ = [
    "BrokerAdapter", "NotSupportedError", "OrderResult",
    "PaperBroker", "DerayahAdapter", "IBKRAdapter", "AlpacaAdapter",
]
