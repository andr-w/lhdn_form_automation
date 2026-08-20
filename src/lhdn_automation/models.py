from dataclasses import dataclass

@dataclass
class ClientQuotationData:
    ClientName: str
    BusinessType: str
    CompanyLocationType: str
    City: str
    State: str
    Postcode: str
    TelephoneNumber: str
    EmailAddress: str
    QuoteDate: str
    EffectiveDate: str
    AddressLine1: str
    AddressLine2: str
    SSMOption: str
    NetTotal: str
    QuotationQuantity: str
    OwnerName: str | None = None
    OwnerNationality: str | None = None
    AddressLine3: str | None = None
    OldCompanyNumber: str | None = None
    NewCompanyNumber: str | None = None

@dataclass
class FirmData:
    ClientName: str
    BusinessType: str
    CompanyLocationType: str
    City: str
    State: str
    Postcode: str
    TelephoneNumber: str
    EmailAddress: str
    AddressLine1: str
    AddressLine2: str
    OldCompanyNumber: str
    NewCompanyNumber: str
    AddressLine3: str | None = None

def default_firm_data():
    """
    Blank template that can be filled in with actual firm data before calling main_automate_form().
    Will be validated by validate_firm_data() and raise an exception if any required fields are missing.
    """
    return FirmData(
        ClientName="",
        BusinessType="",
        CompanyLocationType="",
        City="",
        State="",
        Postcode="",
        TelephoneNumber="",
        EmailAddress="",
        AddressLine1="",
        AddressLine2="",
        OldCompanyNumber="",
        NewCompanyNumber=""
    )