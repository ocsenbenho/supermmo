from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import os
import re
import shutil
import sys
import subprocess
from selenium_utils import find_chrome_binary, find_chromedriver_full_scan, inject_cookies_from_netscape

# --- Tái sử dụng logic tìm chromedriver đã tối ưu ---
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

def find_all_chromedriver_on_disk(drives=None, names=None):
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

def find_chromedriver_full_scan(driver_path=None, allow_full_disk_scan=True):
    import os
    import shutil
    import sys
    # Ưu tiên lấy từ cache
    cached = load_chromedriver_from_cache()
    if cached:
        return cached
    checked_paths = []
    candidates = []
    if driver_path:
        candidates.append(driver_path)
    for name in ["chromedriver.exe", "chromedriver"]:
        path = shutil.which(name)
        if path:
            candidates.append(path)
    cwd = os.getcwd()
    candidates += [
        os.path.join(cwd, 'chromedriver.exe'),
        os.path.join(cwd, 'chromedriver'),
        r'C:\\Program Files\\Google\\Chrome\\Application\\chromedriver.exe',
        r'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chromedriver.exe',
        '/usr/local/bin/chromedriver',
        '/usr/bin/chromedriver',
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            print(f"[DEBUG] Đã tìm thấy chromedriver tại: {candidate}")
            save_chromedriver_to_cache(candidate)
            return candidate
        checked_paths.append(candidate)
    print("[DEBUG] Đã kiểm tra các vị trí chromedriver sau:")
    for p in checked_paths:
        print(f"  - {p}")
    # Nếu cho phép, quét toàn bộ ổ đĩa
    if allow_full_disk_scan:
        print("[DEBUG] Không tìm thấy chromedriver ở các vị trí phổ biến, bắt đầu quét toàn bộ ổ đĩa...")
        found = find_all_chromedriver_on_disk()
        if found:
            print(f"[DEBUG] Đã tìm thấy chromedriver trên ổ đĩa: {found[0]}")
            save_chromedriver_to_cache(found[0])
            return found[0]
        else:
            print("[DEBUG] Không tìm thấy chromedriver trên toàn bộ ổ đĩa!")
    return None

# --- Hàm inject cookies (giống TikTok) ---
def inject_cookies_from_netscape(driver, cookies_file, domain='.facebook.com'):
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

def get_facebook_reel_links_selenium(profile_url, cookies_file=None, num_links=20, driver_path=None):
    """
    Lấy tối đa num_links link video Facebook Reel từ profile bằng Selenium.
    profile_url: link profile Facebook (ví dụ: https://www.facebook.com/username/reels/)
    cookies_file: file cookies Netscape nếu có (tự động đăng nhập)
    driver_path: chromedriver nếu cần
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    options.add_argument('--lang=vi')
    # Tự động phát hiện chrome binary
    chrome_path = find_chrome_binary()
    if chrome_path:
        print(f"[DEBUG] Sử dụng Chrome binary: {chrome_path}")
        options.binary_location = chrome_path
    else:
        raise RuntimeError('Không tìm thấy Chrome! Hãy cài đặt Google Chrome.')
    # Tự động phát hiện chromedriver
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
    driver.get('https://www.facebook.com/')
    time.sleep(2)
    # Đăng nhập bằng cookies nếu có
    if cookies_file and os.path.exists(cookies_file):
        inject_cookies_from_netscape(driver, cookies_file, domain='.facebook.com')
        driver.refresh()
        time.sleep(2)
    # Truy cập profile reels
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
            # Facebook reel thường có dạng /reel/<id> hoặc /reels/video/<id>
            if href and re.search(r'/reel[s]?/\d+', href):
                links.add(href.split('?')[0])
        print(f'[DEBUG] Sau lần cuộn {i+1}, tổng số link reel: {len(links)}')
        if len(links) >= num_links or len(links) == last_count:
            break
        last_count = len(links)
    driver.quit()
    return list(links)[:num_links] 