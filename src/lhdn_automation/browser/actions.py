from lhdn_automation.browser.driver import wait_and_send_keys, wait_and_click, wait_and_find
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from lhdn_automation.config.constants import COMPANY_SUFFIXES
from datetime import datetime
import re

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