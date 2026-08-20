from lhdn_automation.browser.driver import wait_and_click, wait_and_send_keys, wait_and_find
from lhdn_automation.browser.actions import extract_company_name
from lhdn_automation.config.constants import WAIT_TIME
from selenium.webdriver.common.by import By
import logging

def find_company_number(driver, old_company_number="", new_company_number="", company_name=""):
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
