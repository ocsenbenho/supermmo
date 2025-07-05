from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import re
import os
import shutil
import sys
import subprocess
from selenium_utils import find_chrome_binary, find_chromedriver_full_scan, inject_cookies_from_netscape

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

def find_all_chromedriver_on_disk(drives=None, names=None):
    """
    Quét toàn bộ ổ đĩa (hoặc danh sách ổ đĩa) để tìm chromedriver.exe/chromedriver.
    Trả về danh sách đường dẫn tìm được.
    """
    if names is None:
        names = ["chromedriver.exe", "chromedriver"]
    if drives is None:
        import string
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    found = []
    for drive in drives:
        print(f"[SCAN] Đang quét ổ đĩa: {drive}")
        for root, dirs, files in os.walk(drive):
            for name in names:
                if name in files:
                    path = os.path.join(root, name)
                    print(f"[FOUND] {path}")
                    found.append(path)
    return found

def get_chromedriver_cache_path():
    return os.path.join(os.path.dirname(__file__), 'chromedriver_path_cache.txt')

def save_chromedriver_to_cache(path):
    try:
        with open(get_chromedriver_cache_path(), 'w', encoding='utf-8') as f:
            f.write(path.strip())
    except Exception as e:
        print(f"[DEBUG] Không thể lưu cache chromedriver: {e}")

def load_chromedriver_from_cache():
    try:
        cache_path = get_chromedriver_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                path = f.read().strip()
                if path and os.path.exists(path):
                    print(f"[DEBUG] Đã lấy chromedriver từ cache: {path}")
                    return path
    except Exception as e:
        print(f"[DEBUG] Không thể đọc cache chromedriver: {e}")
    return None

def get_tiktok_video_links_selenium(profile_url, cookies_file=None, num_links=20, driver_path=None):
    """
    Lấy tối đa num_links link video TikTok từ profile bằng Selenium.
    profile_url: link profile TikTok (ví dụ: https://www.tiktok.com/@username)
    cookies_file: file cookies Netscape nếu có (tự động đăng nhập)
    driver_path: chromedriver nếu cần
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')

    # Tự động phát hiện chrome binary
    chrome_path = find_chrome_binary()
    if chrome_path:
        print(f"[DEBUG] Sử dụng Chrome binary: {chrome_path}")
        options.binary_location = chrome_path
    else:
        raise RuntimeError('Không tìm thấy Chrome! Hãy cài đặt Google Chrome.')

    # Tự động phát hiện chromedriver thông minh
    chromedriver_path = find_chromedriver_full_scan(driver_path)
    if not chromedriver_path:
        raise RuntimeError(
            'Không tìm thấy chromedriver!\n'
            'Hãy tải đúng phiên bản tại https://chromedriver.chromium.org/downloads '
            'và đặt vào cùng thư mục với project hoặc thêm vào PATH.\n'
            'Đã kiểm tra các vị trí phổ biến và PATH.'
        )

    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get('https://www.tiktok.com/')
    time.sleep(2)
    # Đăng nhập bằng cookies nếu có
    if cookies_file and os.path.exists(cookies_file):
        inject_cookies_from_netscape(driver, cookies_file, domain='.tiktok.com')
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
            if href and '/video/' in href:
                m = re.search(r'/video/(\d+)', href)
                if m:
                    links.add(href.split('?')[0])
        print(f'[DEBUG] Sau lần cuộn {i+1}, tổng số link video: {len(links)}')
        if len(links) >= num_links or len(links) == last_count:
            break
        last_count = len(links)
    driver.quit()
    return list(links)[:num_links]

if __name__ == '__main__':
    print('=== TEST TÌM CHROMEDRIVER ===')
    chromedriver_path = find_chromedriver_full_scan()
    if chromedriver_path:
        print(f'Đã tìm thấy chromedriver: {chromedriver_path}')
    else:
        print('Không tìm thấy chromedriver trên hệ thống!') 