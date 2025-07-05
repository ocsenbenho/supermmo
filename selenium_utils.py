import os
import shutil
import sys
import string

def find_chrome_binary():
    if sys.platform.startswith('win'):
        candidates = [
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        ]
    elif sys.platform.startswith('darwin'):
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ]
    else:
        candidates = ["google-chrome", "chrome", "chromium", "chromium-browser"]
    for path in candidates:
        if os.path.exists(path):
            return path
        if shutil.which(path):
            return shutil.which(path)
    return None

def find_all_chromedriver_on_disk(drives=None, names=None):
    if names is None:
        names = ["chromedriver.exe", "chromedriver"]
    if drives is None:
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

def find_chromedriver_full_scan(driver_path=None, allow_full_disk_scan=True):
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

def inject_cookies_from_netscape(driver, cookies_file, domain):
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