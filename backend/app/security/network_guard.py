"""
Safety utility for the confidential-paper embedding pipeline.

Purpose: provide a decorator that can wrap the embedding function to
assert no outbound network call happens during its execution. This turns
the "confidential data stays local" promise into something testable,
not just a comment in the code.

How it works: temporarily monkey-patches socket.socket.connect to raise
an error if called, for the duration of the wrapped function. Any
attempt to open a network connection (via requests, httpx, urllib, etc.)
during that window will fail loudly instead of silently leaking data.
"""

import socket
import functools


class NetworkCallBlockedError(Exception):
    """Raised if code inside a network_guard-wrapped function tries to open a network connection."""
    pass


def _blocked_connect(*args, **kwargs):
    raise NetworkCallBlockedError(
        "A network call was attempted inside a function protected by "
        "@no_network_calls. The confidential embedding pipeline must "
        "never make outbound network requests."
    )


def no_network_calls(func):
    """
    Decorator: wraps a function so that any attempt to open a network
    socket during its execution raises NetworkCallBlockedError instead
    of silently succeeding.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        original_connect = socket.socket.connect
        socket.socket.connect = _blocked_connect
        try:
            return func(*args, **kwargs)
        finally:
            socket.socket.connect = original_connect  # always restore, even on error
    return wrapper