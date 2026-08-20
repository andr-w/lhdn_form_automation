import os
import threading

import msal

from lhdn_automation.authentication import secure_storage

SCOPES = ["Sites.Selected"]

_CACHE_PATH = os.path.join(secure_storage.app_data_dir(), "token_cache.bin")
_lock = threading.Lock()
_app = None


class SignInRequired(Exception):
    """Raised when no valid cached session exists and interactive sign-in was declined"""


def _load_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            encrypted = f.read()
        if encrypted:
            cache.deserialize(secure_storage.decrypt(encrypted))
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            f.write(secure_storage.encrypt(cache.serialize()))

def _get_app(tenant_id, client_id):
    global _app
    if _app is None:
        _app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            token_cache=_load_cache(),
        )
    return _app

def has_cached_account(tenant_id, client_id):
    """True if a previous sign-in is cached"""
    return bool(_get_app(tenant_id, client_id).get_accounts())

def get_delegated_token(tenant_id, client_id, allow_interactive=True):
    """
    Gets a valid Graph API token corresponding to the signed-in user. 
    If no valid token is cached, attempt to acquire one silently. 
    If that fails and allow_interactive is True, it will prompt the user to sign in interactively. 
    If allow_interactive is False and no valid token is available, it raises SignInRequired.
    """
    with _lock:
        app = _get_app(tenant_id, client_id)
        result = None

        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])

        if not result:
            if not allow_interactive:
                raise SignInRequired("No valid Microsoft sign-in session; interactive sign-in was declined.")
            result = app.acquire_token_interactive(SCOPES)

        _save_cache(app.token_cache)

        if not result or "access_token" not in result:
            error = (result or {}).get("error_description") or (result or {}).get("error") or "unknown error"
            raise RuntimeError(f"Microsoft sign-in failed: {error}")

        return result["access_token"]

def sign_out(tenant_id, client_id):
    with _lock:
        app = _get_app(tenant_id, client_id)
        for account in app.get_accounts():
            app.remove_account(account)
        _save_cache(app.token_cache)
