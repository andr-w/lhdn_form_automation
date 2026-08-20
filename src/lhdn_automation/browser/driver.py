from contextlib import suppress
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from lhdn_automation.config.constants import WAIT_TIME

def safe_quit_driver(driver):
    if driver is None:
        return
    with suppress(Exception):
        driver.quit()

LAST_DRIVER = None

def close_last_driver():
    """Closes the most recently opened visible driver, if any. Returns True if one was closed."""
    global LAST_DRIVER
    if LAST_DRIVER is None:
        return False
    safe_quit_driver(LAST_DRIVER)
    LAST_DRIVER = None
    return True

def setup_driver(website, headless=False):
    global LAST_DRIVER
    options = webdriver.EdgeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    driver = webdriver.Edge(options=options)
    driver.get(website)
    driver.set_window_size(1920, 1080)
    if not headless:
        LAST_DRIVER = driver
    return driver

def replace_driver(current_driver, website, headless=False):
    safe_quit_driver(current_driver)
    return setup_driver(website, headless=headless)

def wait_and_find(driver, by, selector, timeout=None):
    if timeout is None:
        timeout = WAIT_TIME
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector)))

def wait_and_send_keys(driver, by, selector, text, timeout=None):
    if timeout is None:
        timeout = WAIT_TIME
    element = wait_and_find(driver, by, selector, timeout)
    element.clear()
    element.send_keys(text)

def wait_and_click(driver, by, selector, timeout=None):
    if timeout is None:
        timeout = WAIT_TIME
    element = wait_and_find(driver, by, selector, timeout)
    element.click()

def select_dropdown(driver, by, selector, text=None, timeout=None):
    timeout = timeout or WAIT_TIME

    dropdown = wait_and_find(driver, by, selector, timeout)

    WebDriverWait(driver, timeout).until(
        lambda d: dropdown.is_displayed() and dropdown.is_enabled()
    )

    select = Select(dropdown)

    if text:
        select.select_by_visible_text(text)
    else:
        if len(select.options) > 1:
            select.select_by_index(1)
        else:
            raise RuntimeError(
                f"Dropdown '{selector}' has no selectable options."
            )

def is_driver_alive(driver):
    """True if `driver` still has a live, responsive browser session."""
    if driver is None:
        return False
    try:
        _ = driver.title
        return True
    except Exception:
        return False