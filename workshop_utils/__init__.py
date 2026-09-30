"""Workshop helper utilities.

Importing from the package root keeps notebook cells short::

    from workshop_utils import get_chat_client, setup_tracing
"""

from .clients import SUPPORTED_PROVIDERS, current_provider, get_chat_client
from .tracing import SUPPORTED_TRACE_BACKENDS, current_trace_backend, setup_tracing

__all__ = [
    "get_chat_client",
    "current_provider",
    "SUPPORTED_PROVIDERS",
    "setup_tracing",
    "current_trace_backend",
    "SUPPORTED_TRACE_BACKENDS",
]
