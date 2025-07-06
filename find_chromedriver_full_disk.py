import os
import sys


def find_all_chromedriver_on_disk(drives=None, names=None):
    """
    Quét toàn bộ ổ đĩa (hoặc danh sách ổ đĩa) để tìm chromedriver.exe/chromedriver.
    Trả về danh sách đường dẫn tìm được.
    """
    if names is None:
        names = ["chromedriver.exe", "chromedriver"]
    if drives is None:
        # Lấy danh sách ổ đĩa trên Windows
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

