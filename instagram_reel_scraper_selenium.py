from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import re
import os

def inject_cookies_from_netscape(driver, cookies_file, domain='.instagram.com'):
    with open(cookies_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                domain_c, flag, path, secure, expires, name, value = parts
                cookie = {
                    'domain': domain_c,
                    'name': name,
                    'value': value,
                    'path': path,
                    'secure': secure.lower() == 'true',
                }
                if expires.isdigit():
                    cookie['expiry'] = int(expires)
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass

def get_instagram_reel_links_selenium(profile_url, cookies_file=None, num_links=20, driver_path=None):
    """
    Lấy tối đa num_links link Instagram Reel từ profile bằng Selenium.
    profile_url: link profile Instagram (ví dụ: https://www.instagram.com/username/)
    cookies_file: file cookies Netscape nếu có (tự động đăng nhập)
    driver_path: chromedriver nếu cần
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    if driver_path:
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    driver.get('https://www.instagram.com/')
    time.sleep(2)
    # Đăng nhập bằng cookies nếu có
    if cookies_file and os.path.exists(cookies_file):
        inject_cookies_from_netscape(driver, cookies_file, domain='.instagram.com')
        driver.refresh()
        time.sleep(2)
    # Truy cập profile
    driver.get(profile_url)
    time.sleep(3)
    links = set()
    last_count = 0
    for i in range(50):
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
        time.sleep(2)
        elems = driver.find_elements(By.TAG_NAME, 'a')
        for e in elems:
            href = e.get_attribute('href')
            if href and '/reel/' in href:
                m = re.search(r'/reel/([\w-]+)/', href)
                if m:
                    reel_id = m.group(1)
                    links.add(f'https://www.instagram.com/reel/{reel_id}/')
        print(f'[DEBUG] Sau lần cuộn {i+1}, tổng số link reel: {len(links)}')
        if len(links) >= num_links or len(links) == last_count:
            break
        last_count = len(links)
    driver.quit()
    return list(links)[:num_links] 