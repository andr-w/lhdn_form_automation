from lhdn_automation.config.constants import *

class ConfigurationError(RuntimeError):
    """Raised when required org/company configuration is missing or blank."""

def validate_runtime_config():
    """
    Check if all required configuration variables are set and not empty. Raises ConfigurationError if any are missing.
    """
    required = {
        "APP_TENANT_ID": TENANT_ID,
        "APP_CLIENT_ID": CLIENT_ID,
        "ESTAMP_BASE_URL": BASE_URL,
        "SHAREPOINT_SITE_ID": SHAREPOINT_SITE_ID,
        "SHAREPOINT_LIST_ID": SHAREPOINT_LIST_ID,
        "SHAREPOINT_HOSTNAME": SHAREPOINT_HOSTNAME,
        "SHAREPOINT_SITE_PATH": SHAREPOINT_SITE_PATH,
        "SHAREPOINT_LIST_NAME": SHAREPOINT_LIST_NAME,
        "SHAREPOINT_LOG_LIST_NAME": SHAREPOINT_LOG_LIST_NAME,
    }
    missing_variables = [name for name, value in required.items() if not value]
    if missing_variables:
        raise ConfigurationError(f"Missing required configuration: {', '.join(missing_variables)}")

def validate_firm_data(firmdata):
    """
    Checks if all required fields are not empty. Raises ConfigurationError otherwise.
    """
    required = {
        "ClientName": firmdata.ClientName,
        "BusinessType": firmdata.BusinessType,
        "CompanyLocationType": firmdata.CompanyLocationType,
        "City": firmdata.City,
        "State": firmdata.State,
        "Postcode": firmdata.Postcode,
        "TelephoneNumber": firmdata.TelephoneNumber,
        "AddressLine1": firmdata.AddressLine1,
        "AddressLine2": firmdata.AddressLine2,
        "OldCompanyNumber": firmdata.OldCompanyNumber,
        "NewCompanyNumber": firmdata.NewCompanyNumber,
    }
    missing_fields = [name for name, value in required.items() if not value]
    if missing_fields:
        raise ConfigurationError(
            f"Firm details are incomplete: {', '.join(missing_fields)}. "
            "Fill these in via Configuration -> Edit Company Details."
        )