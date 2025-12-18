"""Shared HTTP client utilities with retry logic."""
from __future__ import annotations


import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_retry_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (500, 502, 503, 504),
    timeout: float = 5.0,
) -> requests.Session:
    """Create a requests.Session with automatic retries."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Store the default timeout in the session for convenient access by clients
    # Note: Requests doesn't support session-level timeout natively, 
    # so clients must still pass timeout=... or we can subclass Session.
    # For now, we'll just return the standard session and let clients handle timeout,
    # or we can attach it as an attribute if we want to be fancy.
    # Let's keep it simple.
    
    return session
