import json
import time
from urllib.parse import urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuration
BASE_URL = "https://courtofappeal.lk/"
JSON_PATH = "appeal_court_run.json"

# Initialize Selenium WebDriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Run in headless mode if desired
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)
actions = ActionChains(driver)

def load_data(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_data(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def extract_page_id(url):
    parsed = urlparse(url)
    return parse_qs(parsed.query).get('page_id', [None])[0]


def main():
    # Load existing JSON content
    data = load_data(JSON_PATH)

    driver.get(BASE_URL)
    # Locate the "Judgements" menu item and hover to reveal years dropdown
    judgm_link = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Judgments")))
    actions.move_to_element(judgm_link).perform()
    year_menu = wait.until(EC.visibility_of_element_located((
        By.XPATH,
        "//li[a[normalize-space(text())='Judgments']]/ul"
    )))
    years = year_menu.find_elements(By.TAG_NAME, "a")

    time.sleep(1)

    # Find all year links under the Judgements menu
    years = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.sub-menu li.menu-item:has(> a[href*='judgements']) ul li a")))
    for year_elem in years:
        year = year_elem.text.strip()
        actions.move_to_element(year_elem).perform()
        # find the <ul> that’s directly under this year’s <li>
        month_ul = wait.until(EC.visibility_of_element_located((
            By.XPATH,
            f"//li[a[normalize-space(text())='{year}']]/ul"
        )))
        months = month_ul.find_elements(By.TAG_NAME, "a")
        for month_elem in months:
            month = month_elem.text.strip()
            month_elem.click()
            wait.until(EC.url_contains("page_id="))
            pid = extract_page_id(driver.current_url)
            # … update your JSON …
            # then go back & re-hover
            driver.get(BASE_URL)
            actions.move_to_element(judgm_link).perform()
            time.sleep(1)

    # Save updates back to JSON
    save_data(JSON_PATH, data)

    driver.quit()

if __name__ == '__main__':
    main()
