
from lhdn_automation.browser.driver import wait_and_send_keys, wait_and_click, wait_and_find, select_dropdown
from lhdn_automation.browser.actions import select_date
from lhdn_automation.interaction import pause_for_manual_step
from lhdn_automation.config.constants import WAIT_TIME
import time
import logging
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from lhdn_automation.models import FirmData, ClientQuotationData


def maklumat_am_penyeteman(driver, date):
    preferred_options = ["Kuala Lumpur", "Selangor", "Putrajaya"] # List of preferred options for Pejabat Setem
    driver.get('https://stamps.hasil.gov.my/stamps/form/application')
    wait_and_click(driver, By.XPATH, "//div[@class='form-group']//div[@class='radio']//input[@class='radio-per' and @value='4']") # Selecting "Sekuriti" button
    for option in preferred_options:
        try:
            select_dropdown(driver, By.XPATH, "//select[@id='CD_DUTISETEM_ID' and @class='form-control']") # Selecting Pejabat Setem dropdown
            wait_and_click(driver, By.XPATH, f"//select[@id='CD_DUTISETEM_ID']//option[contains(text(), '{option}')]", timeout=1) # Selecting option
            break
        except TimeoutException:
            logging.warning("Option '%s' not found in dropdown, trying next option...", option)
    wait_and_click(driver, By.XPATH, "//div[contains(@class, 'date-t-sempurna')]//span[@class='input-group-addon']") # Entering tarikh surat cara
    select_date(driver, date)
    wait_and_click(driver, By.XPATH, "//button[@type='submit' and @id='btn-ma-submit']") # Confirming date selection

def maklumat_am_main_page(driver):
    # Pejabat Setem will follow previous section so it will be ignored for now
    driver.implicitly_wait(WAIT_TIME)
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input#namaperjanjian", "Service Agreement") # Entering Service Agreement
    time.sleep(0.2)
    wait_and_click(driver, By.XPATH, "//div[@id='namaperjanjian-suggestion-list']//strong[text()='Service Agreement']") # Selecting "Service Agreement" button

def fill_makluman_am(driver, date):
    maklumat_am_penyeteman(driver, date)
    maklumat_am_main_page(driver)

def bahagian_a_maklumat_pertama(driver, firmdata: FirmData):
    wait_and_click(driver, By.XPATH, "//div[@class='panel-body']//strong[contains(text(), 'Syarikat/Perniagaan/Agensi Berdaftar Dengan SSM')]")
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_nama']", firmdata.ClientName) # Entering Name of Client
    select_dropdown(driver, By.CSS_SELECTOR, "select#jenis_perniagaan") # Selecting Business Type dropdown
    wait_and_click(driver, By.XPATH, f"//div[@class='col-xs-8']//option[contains(text(), '{firmdata.BusinessType}')]" ) # Selecting business type

    wait_and_send_keys(driver, By.XPATH, "//input[@id='tb_roc' and @type='text']", firmdata.OldCompanyNumber) # Entering Old Company Number
    wait_and_send_keys(driver, By.XPATH, "//input[@id='tb_roc_new' and @type='text']", firmdata.NewCompanyNumber) # Entering New Company Number

    select_dropdown(driver, By.CSS_SELECTOR, "select#tb_syarikat.form-control") # Selecting Company Location Type dropdown
    wait_and_click(driver, By.XPATH, "//select[@id='tb_syarikat']//option[@value='1']") # Selecting Local option
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_1']", firmdata.AddressLine1) # Entering Address Line 1
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_2']", firmdata.AddressLine2) # Entering Address Line 2

    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_city']", firmdata.City) # Entering City
    select_dropdown(driver, By.CSS_SELECTOR, "select#negeri1.form-control") # Selecting State dropdown
    wait_and_click(driver, By.XPATH, f"//select[@id='negeri1']//option[contains(text(), '{firmdata.State}')]" ) # Selecting State
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_poskod']", firmdata.Postcode) # Entering Postal Code
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_telno']", firmdata.TelephoneNumber) # Entering Telephone Number
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_email']", firmdata.EmailAddress) # Entering Email Address

    wait_and_click(driver, By.XPATH, "//div[@class='button']//input[@type='submit']") # Submitting Bahagian A Maklumat Pertama

def bahagian_a_maklumat_kedua(driver, option: str, data: ClientQuotationData):
    before, _, after = driver.current_url.partition("edit/")
    match option:
        case "Individu": # individu ignored again
            logging.warning("Individu ignored for now as it is not commonly used")
            pass
        case "Syarikat_SSM_True":
            time.sleep(0.2)
            second_button = wait_and_find(driver, By.XPATH, f"//a[@href='{before}buyer_com/{after}']")
            driver.execute_script("arguments[0].click();", second_button)
            driver.implicitly_wait(WAIT_TIME)
            # wait_and_click(driver, By.XPATH, f"//a[@href='{before}buyer_com/{after}']") # Selecting "Syarikat Berdaftar Dengan SSM" button
            syarikat_berdaftar_dengan_ssm(driver, data)
        case "Syarikat_SSM_False":
            time.sleep(0.2)
            third_button = wait_and_find(driver, By.XPATH, f"//div[@href='{before}buyer_comxssm/{after}']")
            driver.execute_script("arguments[0].click();", third_button)
            driver.implicitly_wait(WAIT_TIME)
            # wait_and_click(driver, By.XPATH, f"//div[@href='{before}buyer_comxssm/{after}']") # Selecting "Tidak Berdaftar Dengan SSM" button
            syarikat_tidak_berdaftar_dengan_ssm(driver, data)
        case _:
            logging.warning("Invalid option for Bahagian A Maklumat Kedua: %s", option)

def syarikat_berdaftar_dengan_ssm(driver, data: ClientQuotationData):
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_nama']", data.ClientName) # Entering Name of Client
    select_dropdown(driver, By.CSS_SELECTOR, "select#jenis_perniagaan") # Selecting Business Type dropdown
    wait_and_click(driver, By.XPATH, f"//div[@class='col-xs-8']//option[contains(text(), '{data.BusinessType}')]" ) # Selecting business type
    driver.implicitly_wait(WAIT_TIME)

    if data.OldCompanyNumber:
        wait_and_send_keys(driver, By.XPATH, "//input[@id='tb_roc' and @type='text']", data.OldCompanyNumber) # Entering Old Company Number
    else:
        wait_and_click(driver, By.XPATH, "//div[@class='col-xs-2']//input[type='checkbox' and value='1']") # Clicking on TIADA

    if data.NewCompanyNumber:
        wait_and_send_keys(driver, By.XPATH, "//input[@id='tb_roc_new' and @type='text']", data.NewCompanyNumber) # Entering New Company Number
    else:
        wait_and_click(driver, By.XPATH, "//div[@class='col-xs-2']//input[type='checkbox' and value='2']") # Clicking on TIADA
    
    select_dropdown(driver, By.CSS_SELECTOR, "select#tb_syarikat.form-control") # Selecting Company Location Type dropdown
    if data.CompanyLocationType == "Local":
        wait_and_click(driver, By.XPATH, "//select[@id='tb_syarikat']//option[@value='1']") # Selecting Local option
    else:
        wait_and_click(driver, By.XPATH, "//select[@id='tb_syarikat']//option[@value='2']") # Selecting Foreign option

    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_1']", data.AddressLine1) # Entering Address Line 1
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_2']", data.AddressLine2) # Entering Address Line 2
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_3']", data.AddressLine3) # Entering Address Line 3

    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_city']", data.City) # Entering City
    select_dropdown(driver, By.CSS_SELECTOR, "select#negeri1.form-control") # Selecting State dropdown
    wait_and_click(driver, By.XPATH, f"//select[@id='negeri1']//option[contains(text(), '{data.State}')]" ) # Selecting State
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_poskod']", data.Postcode) # Entering Postal Code
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_telno']", data.TelephoneNumber) # Entering Telephone Number
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_email']", data.EmailAddress) # Entering Email Address

    driver.implicitly_wait(WAIT_TIME)
    if data.BusinessType != "Sendirian Berhad": # If business type is a Sole Proprietorship, Owner Name and Nationality fields will appear
            pause_for_manual_step("Please fill in the Owner Name and Nationality fields manually, then click Continue.", allow_abort=True)
            
    wait_and_click(driver, By.XPATH, "//div[@class='button']//input[@type='submit']") # Submitting Bahagian B Maklumat Kedua

def syarikat_tidak_berdaftar_dengan_ssm(driver, data: ClientQuotationData):
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_nama']", data.ClientName) # Entering Name of Client
    select_dropdown(driver, By.CSS_SELECTOR, "select#jenis_perniagaan") # Selecting Business Type dropdown
    wait_and_click(driver, By.XPATH, f"//div[@class='col-xs-8']//option[contains(text(), '{data.BusinessType}')]" ) # Selecting business type

    driver.implicitly_wait(WAIT_TIME)

    if data.OldCompanyNumber:
        wait_and_send_keys(driver, By.XPATH, "//input[@id='tb_roc' and @type='text']", data.OldCompanyNumber) # Entering Old Company Number
    else:
        wait_and_click(driver, By.XPATH, "//div[@class='col-xs-2']//input[type='checkbox' and value='1']") # Clicking on TIADA

    if data.NewCompanyNumber:
        wait_and_send_keys(driver, By.XPATH, "//input[@id='tb_roc_new' and @type='text']", data.NewCompanyNumber) # Entering New Company Number
    else:
        wait_and_click(driver, By.XPATH, "//div[@class='col-xs-2']//input[type='checkbox' and value='2']") # Clicking on TIADA

    select_dropdown(driver, By.CSS_SELECTOR, "select#tb_syarikat.form-control") # Selecting Company Location Type dropdown
    if data.CompanyLocationType == "Local":
        wait_and_click(driver, By.XPATH, "//select[@id='tb_syarikat']//option[@value='1']") # Selecting Local option
    else:
        wait_and_click(driver, By.XPATH, "//select[@id='tb_syarikat']//option[@value='2']") # Selecting Foreign option

    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_1']", data.AddressLine1) # Entering Address Line 1
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_2']", data.AddressLine2) # Entering Address Line 2
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_alamat_3']", data.AddressLine3) # Entering Address Line 3

    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_city']", data.City) # Entering City
    select_dropdown(driver, By.CSS_SELECTOR, "select#negeri1.form-control") # Selecting State dropdown
    wait_and_click(driver, By.XPATH, f"//select[@id='negeri1']//option[contains(text(), '{data.State}')]" ) # Selecting State
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_poskod']", data.Postcode) # Entering Postal Code
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_telno']", data.TelephoneNumber) # Entering Telephone Number
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input.form-control[name='tb_email']", data.EmailAddress) # Entering Email Address

    driver.implicitly_wait(WAIT_TIME)

    if data.BusinessType != "Sendirian Berhad": # If business type is a Sole Proprietorship, Owner Name and Nationality fields will appear
        pause_for_manual_step("Please fill in the other fields manually, then click Continue.", allow_abort=True)

    wait_and_click(driver, By.XPATH, "//div[@class='button']//input[@type='submit']") # Submitting Bahagian B Maklumat Kedua

def fill_bahagian_a(driver, option: str, firmdata: FirmData, clientdata: ClientQuotationData):
    driver.execute_script("window.scrollTo(0, 0);")
    wait_and_click(driver, By.XPATH, "//a[@href='#bhgn-a' and contains(text(), 'Bahagian A')]") # Navigating to Bahagian A section
    bahagian_a_maklumat_pertama(driver, firmdata)
    driver.implicitly_wait(WAIT_TIME)
    bahagian_a_maklumat_kedua(driver, option, clientdata)

def fill_bahagian_b(driver, data: ClientQuotationData):
    # TODO - Add functionality to fill in collateral information
    driver.execute_script("window.scrollTo(0, 0);")
    wait_and_click(driver, By.XPATH, "//a[@href='#bhgn-b' and contains(text(), 'Bahagian B')]") # Navigating to Bahagian B section
    driver.implicitly_wait(WAIT_TIME)
    wait_and_send_keys(driver, By.ID, "pds_pinjamanbayaran", data.NetTotal) # Entering Name of Client
    select_dropdown(driver, By.XPATH, "//div[@class='col-md-1']//select[@name='pds_salinan']") # Selecting dropdown for Question 2
    time.sleep(0.2)
    wait_and_click(driver, By.XPATH, f"//div[@class='col-md-1']//select[@name='pds_salinan']//option[contains(text(), '{int(data.QuotationQuantity)}')]") # selecting number of copies based on option for Question 2

def fill_bahagian_c(driver):
    driver.execute_script("window.scrollTo(0, 0);") # Scroll to top of page to ensure Bahagian C is visible
    wait_and_click(driver, By.XPATH, "//a[@href='#bhgn-c' and contains(text(), 'Bahagian C')]") # Navigating to Bahagian C section
    select_dropdown(driver, By.XPATH, "//div[@class='panel panel-info']//select[@name='pds_remission']") # Selecting Payment Method dropdown
    wait_and_click(driver, By.XPATH, "//div[@class='panel panel-info']//select[@name='pds_remission']//option[contains(text(), 'P.U.(A) 428/2021')]") # Selecting Online Banking option