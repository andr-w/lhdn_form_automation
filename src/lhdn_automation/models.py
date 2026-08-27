from dataclasses import dataclass

# Selectable in the Pejabat Setem dropdown (sekuriti.maklumat_am_page_1) - the
# firm's CityPriority1..5 fields must be chosen from this list.
MALAYSIAN_STATES = [
    "Johor",
    "Kedah",
    "Kelantan",
    "Melaka",
    "Negeri Sembilan",
    "Pahang",
    "Pulau Pinang",
    "Perak",
    "Perlis",
    "Selangor",
    "Terengganu",
    "Sabah",
    "Sarawak",
    "Kuala Lumpur",
    "Putrajaya",
    "Labuan",
]

# FirmData field names holding the Pejabat Setem fallback order, highest
# priority first.
CITY_PRIORITY_FIELDS = ("CityPriority1", "CityPriority2", "CityPriority3", "CityPriority4", "CityPriority5")

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
    # Pejabat Setem dropdown fallback order (see sekuriti.maklumat_am_page_1):
    # tried highest priority first, skipping any left blank.
    CityPriority1: str = ""
    CityPriority2: str = ""
    CityPriority3: str = ""
    CityPriority4: str = ""
    CityPriority5: str = ""

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
        NewCompanyNumber="",
        CityPriority1="Wilayah Persekutuan Kuala Lumpur",
        CityPriority2="Selangor",
        CityPriority3="Wilayah Persekutuan Putrajaya",
    )