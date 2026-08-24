import os
import sys
from datetime import timedelta

from dotenv import load_dotenv

_APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_APP_DIR, ".env"))

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

_INITIAL_SHAREPOINT_HOSTNAME = SHAREPOINT_HOSTNAME
_INITIAL_SHAREPOINT_SITE_PATH = SHAREPOINT_SITE_PATH
_INITIAL_SHAREPOINT_LIST_NAME = SHAREPOINT_LIST_NAME

WAIT_TIME = 20
POLL_INTERVAL = 30
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 3
REQUEST_RETRY_DELAY = 2
MAX_RETRY_ATTEMPTS = 3
COMPANY_SUFFIXES = ["group", "holdings", "sdn", "sdn bhd", "limited", "ltd.", "co.", "company", "corporation", "inc.", "incorporated", "plc", "llc", "gmbh", "pte ltd", "pty ltd"]

AUTOFILL_STATUSES = ("Pending", "Awaiting Review", "Approved")
STALE_PROCESSING_TIMEOUT = timedelta(minutes=10)

APP_VERSION = "1.1.0"  # keep in sync with version_info.txt's ProductVersion when cutting a release
GITHUB_RELEASES_API = "https://api.github.com/repos/andr-w/yyc_lhdn_automation/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/andr-w/yyc_lhdn_automation/releases"

