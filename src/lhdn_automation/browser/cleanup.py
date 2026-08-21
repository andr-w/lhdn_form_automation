import time
import logging
from selenium.webdriver.common.by import By
from lhdn_automation.browser.actions import input_credentials, click_login, choose_profile
from lhdn_automation.browser.driver import wait_and_click, wait_and_send_keys, select_dropdown
from lhdn_automation.config.constants import PROD_PASSWORD, PROD_IC, WAIT_TIME
from lhdn_automation.interaction import pause_for_manual_step


def cleanup_sign_in(driver):
    """
    Login and profile selection to bring straight to dashboard for cleanup_scan_and_cancel_one().
    """
    input_credentials(driver, PROD_IC, PROD_PASSWORD)
    click_login(driver)
    driver.implicitly_wait(WAIT_TIME)
    choose_profile(driver)
    driver.implicitly_wait(WAIT_TIME)

def cleanup_scan_and_cancel_one(driver, date):
    """
    Navigates to the 'Dalam Simpanan' listing and cancels the first entry
    matching `date` (dd/mm/yyyy) that has no existing cancellation reference.
    Returns True if a match was found and cancelled, False otherwise.

    The matched row is highlighted directly in the browser and held there
    for a single Continue/Abort confirmation - previously there were two
    separate pauses (one before the search even started, one right before
    the destructive cancel click).
    """
    driver.get("https://stamps.hasil.gov.my/stamps/utama/senarai/permohonan/4")
    driver.implicitly_wait(WAIT_TIME)
    select_dropdown(driver, By.ID, "dropdown_status")
    driver.implicitly_wait(WAIT_TIME)
    wait_and_click(driver, By.XPATH, "//option[@value='1']") # Dalam Simpanan
    driver.implicitly_wait(WAIT_TIME)

    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    target_row = None

    for row in rows:
        logging.debug("Row: %r", row.text)
        cells = row.find_elements(By.TAG_NAME, "td")
        logging.debug("Number of cells: %d", len(cells))
        for i, cell in enumerate(cells):
            logging.debug("%d: %r", i, cell.text)

        if len(cells) >= 6 and cells[5].text.strip() == date and cells[4].text.strip() == "-":
            target_row = row
            break

    if target_row is None:
        logging.info("No matching entry found for %s.", date)
        return False

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});"
        "arguments[0].style.backgroundColor = '#fff3a3';"
        "arguments[0].style.outline = '3px solid #d9534f';",
        target_row,
    )
    entry_summary = " | ".join(cell.text.strip() for cell in target_row.find_elements(By.TAG_NAME, "td"))

    pause_for_manual_step(
        f"Found and highlighted an entry matching {date}:\n{entry_summary}\n\n"
        "Continue to cancel it, or Abort to leave it untouched.",
        allow_abort=True,
    )

    link = target_row.find_element(By.XPATH, "./td[2]//a")
    link.click()
    driver.implicitly_wait(WAIT_TIME)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    wait_and_click(driver, By.XPATH, "//button[@id='btn-main-batal']")
    wait_and_send_keys(driver, By.XPATH, "//textarea[@id='alasan-batal']", "Automated test cleanup")
    wait_and_click(driver, By.XPATH, "//button[@id='btn-batal-suratcara']")
    time.sleep(1)
    return True

def cleanup_test_entries(driver, date):  # date in the form of dd/mm/yyyy
    """Signs in once, then cancels every matching entry until none remain."""
    cleanup_sign_in(driver)
    while cleanup_scan_and_cancel_one(driver, date):
        pass
    time.sleep(1)  # or use WebDriverWait
