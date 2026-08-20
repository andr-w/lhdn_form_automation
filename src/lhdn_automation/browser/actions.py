from lhdn_automation.browser.driver import wait_and_send_keys, wait_and_click, wait_and_find
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from lhdn_automation.config.constants import COMPANY_SUFFIXES, WAIT_TIME
import datetime
import re
import logging

def input_credentials(driver, ID, password):
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input#user_ic", ID)
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input#USER_PASSWORD", password)

def click_login(driver):
    wait_and_click(driver, By.CSS_SELECTOR, "button#log-in-btn")

def choose_profile(driver):
    wait_and_click(driver, By.CSS_SELECTOR, "a[href='#render_ejen']") # Selecting profile type
    wait_and_click(driver, By.CSS_SELECTOR, "a.confirm[data-parent='EJEN']") # Footer profile type button
    wait_and_click(driver, By.CSS_SELECTOR, "button.btn.btn-sm.btn-primary.btn-sm.btn-yes") # Confirming login

def select_date(driver, date):
    parsed_date = datetime.strptime(date, "%Y-%m-%d")
    year_value = str(parsed_date.year)
    month_value = str(parsed_date.month - 1)
    day_value = str(parsed_date.day)

    year_select = wait_and_find(driver, By.XPATH, "//div[contains(@class, 'picker__header')]//select[@class='picker__select--year']")
    Select(year_select).select_by_visible_text(year_value)
    month_select = wait_and_find(driver, By.XPATH, "//div[contains(@class, 'picker__header')]//select[@class='picker__select--month']")
    Select(month_select).select_by_value(month_value)
    wait_and_click(driver, By.XPATH, f"//table[@class='picker__table']//td[@role='presentation']//div[contains(@class,'picker__day--infocus') and text()='{day_value}']") # Selecting date from date box

def extract_company_name(name: str):
    sorted_suffixes = sorted(COMPANY_SUFFIXES, key=len, reverse=True) # checks for longest matched suffix first to avoid partial matches
    suffix_pattern = r"(?:\s+" + r"|\s+".join(map(re.escape, sorted_suffixes)) + r")+$" # formatting strings in the form of " sdn| sdn bhd| berhad| ..."
    name_without_suffix = re.sub(suffix_pattern, "", name, flags=re.IGNORECASE) # removing suffixes from the company name
    return name[:len(name_without_suffix)].strip() # returning the company name without suffixes and any trailing whitespace

def findCompanyNumber(driver, old_company_number="", new_company_number="", company_name=""):
    def search_by_name():
        name_to_search = extract_company_name(company_name)
        logging.info("Searching for company name: %s", name_to_search)

        wait_and_click(driver, By.XPATH, "//form//input[@type='radio' and @value='name']")
        wait_and_click(driver, By.XPATH, "//form//input[@type='text' and @name='searchKey']")
        wait_and_send_keys(driver, By.XPATH, "//form//input[@type='text' and @name='searchKey']", name_to_search)

    def search_by_number(number):
        logging.info("Searching for company number: %s", number)

        wait_and_click(driver, By.XPATH, "//form//input[@type='radio' and @value='regNo']")
        wait_and_click(driver, By.XPATH, "//form//input[@type='text' and @name='searchKey']")
        wait_and_send_keys(driver, By.XPATH, "//form//input[@type='text' and @name='searchKey']", number)

    search_attempts = []

    if company_name:
        search_attempts.append(("Company Name", search_by_name))

    if new_company_number:
        search_attempts.append(("New Company Number", lambda: search_by_number(new_company_number)))

    if old_company_number:
        search_attempts.append(("Old Company Number", lambda: search_by_number(old_company_number)))

    if not search_attempts:
        logging.warning("No company name or company number provided.")
        return "", ""

    for method_name, search_func in search_attempts:
        try:
            logging.info("Trying %s...", method_name)

            driver.get("https://businessreport.ctoscredit.com.my/oneoffreport/home")
            driver.implicitly_wait(WAIT_TIME)

            search_func()

            wait_and_click(
                driver,
                By.XPATH,
                "//form//button[@type='submit' and @class='search_txt_home']"
            )

            full_number = wait_and_find(
                driver,
                By.CSS_SELECTOR,
                "mat-cell.cdk-column-Reg_Num a"
            ).text.strip()

            before, separator, after = full_number.partition("/")
            if not separator:
                raise ValueError(f"Unexpected CTOS company number format: {full_number!r}")

            old_number = before.strip()
            if len(old_number) < 8:
                raise ValueError(f"Unexpected CTOS old company number format: {old_number!r}")

            if len(old_number) == 9:
                formatted_old_number = f"{old_number[1:7]}-{old_number[7:]}"
            else:
                formatted_old_number = old_number

            new_number = after.strip()
            if not new_number:
                raise ValueError(f"Unexpected CTOS new company number format: {full_number!r}")

            logging.info(
                "Resolved company numbers using %s: old=%s new=%s",
                method_name,
                formatted_old_number,
                new_number,
            )

            return formatted_old_number, new_number

        except Exception as e:
            logging.warning("%s search failed: %s", method_name, e)

    logging.info("Unable to resolve company numbers using any search method.")
    return "", ""