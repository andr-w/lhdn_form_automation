import os

TENANT_ID = os.getenv("APP_TENANT_ID")
CLIENT_ID = os.getenv("APP_CLIENT_ID")  # public-client app ID for delegated sign-in - see auth.py
BASE_URL = os.getenv("ESTAMP_BASE_URL")

PROD_IC = os.getenv("ESTAMP_PROD_IC")
PROD_PASSWORD = os.getenv("ESTAMP_PROD_PASSWORD")
SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME")
SHAREPOINT_SITE_PATH = os.getenv("SHAREPOINT_SITE_PATH")
SHAREPOINT_SITE_ID = os.getenv("SHAREPOINT_SITE_ID")
SHAREPOINT_LIST_ID = os.getenv("SHAREPOINT_LIST_ID")
SHAREPOINT_LIST_NAME = os.getenv("SHAREPOINT_LIST_NAME")
SHAREPOINT_LOG_LIST_NAME = os.getenv("SHAREPOINT_LOG_LIST_NAME")
EDIT_ENTRIES_URL = os.getenv("POWERAPP_EDIT_ENTRIES_URL")
WAIT_TIME = 20
POLL_INTERVAL = 30
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 3
REQUEST_RETRY_DELAY = 2
MAX_RETRY_ATTEMPTS = 3
COMPANY_SUFFIXES = ["group", "holdings", "sdn", "sdn bhd", "limited", "ltd.", "co.", "company", "corporation", "inc.", "incorporated", "plc", "llc", "gmbh", "pte ltd", "pty ltd"]

APP_VERSION = "1.1.0"  # keep in sync with version_info.txt's ProductVersion when cutting a release
GITHUB_RELEASES_API = "https://api.github.com/repos/andr-w/yyc_lhdn_automation/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/andr-w/yyc_lhdn_automation/releases"

LAST_DRIVER = None

