import tkinter as tk
from tkinter import filedialog, messagebox
import sys
import os
import cv2
import numpy as np
from settings import PROCESSING_MODE, CHINESE_MODE
import threading

def select_video_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    if sys.platform == "darwin":
        root.call('wm', 'attributes', '.', '-topmost', True)
    file_path = filedialog.askopenfilename(
        title="Chọn file video/ảnh cần xóa text",
        initialdir=os.path.expanduser("~/Downloads"),
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v"),
            ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.gif"),
            ("All files", "*.*")
        ],
        parent=root
    )
    root.destroy()
    return file_path

def select_output_directory():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    if sys.platform == "darwin":
        root.call('wm', 'attributes', '.', '-topmost', True)
    directory = filedialog.askdirectory(
        title="Chọn thư mục lưu kết quả",
        initialdir=os.path.expanduser("~/Downloads"),
        parent=root
    )
    root.destroy()
    return directory

def get_processing_method():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    if sys.platform == "darwin":
        root.call('wm', 'attributes', '.', '-topmost', True)
    choice = messagebox.askyesnocancel(
        "Chọn phương pháp xử lý",
        "Chọn phương pháp xử lý:\n\n"
        "YES: Tự động phát hiện và xóa text\n"
        "NO: Chọn vùng thủ công để xóa\n"
        "CANCEL: Hủy",
        parent=root
    )
    root.destroy()
    return choice

def get_chinese_processing_mode():
    global CHINESE_MODE
    if CHINESE_MODE is not None:
        return CHINESE_MODE
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    if sys.platform == "darwin":
        root.call('wm', 'attributes', '.', '-topmost', True)
    choice = messagebox.askyesnocancel(
        "Chế độ xử lý tiếng Trung",
        "Chọn chế độ xử lý cho TOÀN BỘ VIDEO:\n\n"
        "🇨🇳 YES: Chế độ tiếng Trung tối ưu\n"
        "   - OCR + Computer Vision\n"
        "   - Inpainting chuyên sâu\n"
        "   - Độ chính xác cao nhất\n\n"
        "🌐 NO: Chế độ thông thường\n"
        "   - Phát hiện đa ngôn ngữ\n"
        "   - Tốc độ nhanh hơn\n\n"
        "❌ CANCEL: Hủy\n\n"
        "⚠️  Lựa chọn này sẽ áp dụng cho TẤT CẢ frames!",
        parent=root
    )
    root.destroy()
    CHINESE_MODE = choice
    return choice

class RegionSelector:
    def __init__(self):
        self.regions = []
        self.current_region = []
        self.drawing = False
        self.img_copy = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.current_region = [(x, y)]
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                temp_img = self.img_copy.copy()
                cv2.rectangle(temp_img, self.current_region[0], (x, y), (0, 255, 0), 2)
                cv2.imshow('Chọn vùng cần xóa', temp_img)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.current_region.append((x, y))
            self.regions.append(self.current_region.copy())
            cv2.rectangle(self.img_copy, self.current_region[0], self.current_region[1], (0, 255, 0), 2)
            cv2.putText(self.img_copy, f'Region {len(self.regions)}', (self.current_region[0][0], self.current_region[0][1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow('Chọn vùng cần xóa', self.img_copy)

    def select_regions(self, img):
        while True:
            self.img_copy = img.copy()
            self.regions = []
            cv2.namedWindow('Chọn vùng cần xóa', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Chọn vùng cần xóa', 1200, 800)
            cv2.setMouseCallback('Chọn vùng cần xóa', self.mouse_callback)
            print("🖱️  Hướng dẫn:")
            print("   - Kéo chuột để chọn vùng cần xóa")
            print("   - Nhấn SPACE để hoàn thành")
            print("   - Nhấn 'r' để reset")
            print("   - Nhấn 'u' để undo vùng cuối")
            print("   - Nhấn ESC để hủy")
            cv2.imshow('Chọn vùng cần xóa', self.img_copy)
            while True:
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    cv2.destroyAllWindows()
                    return []
                elif key == ord(' '):
                    break
                elif key == ord('r'):
                    self.regions = []
                    self.img_copy = img.copy()
                    cv2.imshow('Chọn vùng cần xóa', self.img_copy)
                elif key == ord('u'):
                    if self.regions:
                        self.regions.pop()
                        self.img_copy = img.copy()
                        for i, region in enumerate(self.regions):
                            cv2.rectangle(self.img_copy, region[0], region[1], (0, 255, 0), 2)
                            cv2.putText(self.img_copy, f'Region {i+1}', (region[0][0], region[0][1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.imshow('Chọn vùng cần xóa', self.img_copy)
            cv2.destroyAllWindows()
            # Preview vùng chọn
            preview = img.copy()
            for region in self.regions:
                cv2.rectangle(preview, region[0], region[1], (0, 0, 255), 2)
            cv2.namedWindow('Xác nhận vùng chọn', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Xác nhận vùng chọn', 1200, 800)
            cv2.imshow('Xác nhận vùng chọn', preview)
            # Hiển thị cửa sổ xác nhận bằng tkinter
            result = self._show_confirm_dialog()
            cv2.destroyAllWindows()
            if result == 'ok':
                return self.regions.copy()
            elif result == 'retry':
                continue
            else:
                return []

    def _show_confirm_dialog(self):
        # Tạo cửa sổ xác nhận bằng tkinter
        result = {'value': None}
        def on_ok():
            result['value'] = 'ok'
            root.destroy()
        def on_retry():
            result['value'] = 'retry'
            root.destroy()
        def on_cancel():
            result['value'] = 'cancel'
            root.destroy()
        root = tk.Tk()
        root.title('Xác nhận vùng chọn')
        root.geometry('350x120')
        root.resizable(False, False)
        root.attributes('-topmost', True)
        label = tk.Label(root, text='Bạn có muốn xác nhận vùng đã chọn?', font=('Arial', 12))
        label.pack(pady=15)
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)
        btn_ok = tk.Button(btn_frame, text='Xác nhận', width=12, command=on_ok)
        btn_ok.pack(side='left', padx=8)
        btn_retry = tk.Button(btn_frame, text='Chọn lại', width=12, command=on_retry)
        btn_retry.pack(side='left', padx=8)
        btn_cancel = tk.Button(btn_frame, text='Hủy', width=12, command=on_cancel)
        btn_cancel.pack(side='left', padx=8)
        root.mainloop()
        return result['value']

def preview_mask(img, mask):
    preview = img.copy()
    preview[mask > 0] = [0, 0, 255]
    total_pixels = img.shape[0] * img.shape[1]
    mask_pixels = np.sum(mask > 0)
    coverage_percent = (mask_pixels / total_pixels) * 100
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    num_regions = len(contours)
    print(f"📊 Thống kê mask:")
    print(f"   - Số vùng phát hiện: {num_regions}")
    print(f"   - Diện tích che phủ: {coverage_percent:.2f}%")
    print(f"   - Pixels sẽ xóa: {mask_pixels}")
    combined = np.hstack([img, preview])
    combined = cv2.resize(combined, (1200, 400))
    cv2.imshow('Preview: Gốc (trái) vs Vùng xóa (phải)', combined)
    print("👀 Preview: Nhấn SPACE để tiếp tục, ESC để hủy")
    key = cv2.waitKey(0) & 0xFF
    cv2.destroyAllWindows()
    return key == ord(' ')

def reset_processing_settings():
    global PROCESSING_MODE, CHINESE_MODE
    PROCESSING_MODE = None
    CHINESE_MODE = None
    print("🔄 Đã reset cài đặt xử lý") 