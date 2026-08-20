
from lhdn_automation import authentication
from lhdn_automation.config.constants import CLIENT_ID, TENANT_ID

def get_access_token(allow_interactive=True):
    """
    Returns a Graph API access token for the signed-in coworker (delegated
    auth via auth.py/MSAL) rather than a shared app secret. allow_interactive
    controls whether a sign in prompt appears.
    """
    return authentication.get_delegated_token(TENANT_ID, CLIENT_ID, allow_interactive=allow_interactive)