import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
import queue
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageTk
import re
import time
from facebook_reel_scraper_selenium import get_facebook_reel_links_selenium
from remove_music_utils import remove_music_from_video_smart

# Import các module hiện có
try:
    from video_processing import process_video_optimized
    from image_processing import process_single_image_chinese
    from masking import create_advanced_mask
    from inpainting import advanced_inpaint
    from ocr_utils import setup_tesseract_chinese, detect_chinese_text_ocr
    from settings import CHINESE_MODE, PROCESSING_MODE
    print("✅ Đã import thành công các module xử lý")
except ImportError as e:
    print(f"⚠️  Không thể import module: {e}")
    print("   Sẽ sử dụng fallback methods")

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'OutputFile')

class RegionSelector:
    def __init__(self):
        self.regions = []
        self.current_region = []
        self.drawing = False
        self.img_display = None
        self.original_img = None
        self.scale_factor = 1.0

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.current_region = [(x, y)]
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing and self.img_display is not None:
                # Vẽ rectangle tạm thời
                temp_img = self.img_display.copy()
                cv2.rectangle(temp_img, self.current_region[0], (x, y), (0, 255, 0), 2)
                cv2.imshow('Chọn vùng text - Nhấn SPACE để xác nhận, ESC để hủy', temp_img)
        elif event == cv2.EVENT_LBUTTONUP:
            if self.drawing and self.img_display is not None:
                self.drawing = False
                self.current_region.append((x, y))
                # Vẽ rectangle đã chọn
                cv2.rectangle(self.img_display, self.current_region[0], self.current_region[1], (0, 255, 0), 2)
                # Thêm text hiển thị số thứ tự
                region_num = len(self.regions) + 1
                cv2.putText(self.img_display, f'{region_num}', 
                           (self.current_region[0][0], self.current_region[0][1] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow('Chọn vùng text - Nhấn SPACE để xác nhận, ESC để hủy', self.img_display)

    def select_regions(self, frame):
        """Cho phép người dùng chọn nhiều vùng text"""
        self.original_img = frame.copy()
        
        # Scale image để hiển thị vừa màn hình
        height, width = frame.shape[:2]
        max_height = 800
        if height > max_height:
            self.scale_factor = max_height / height
            new_width = int(width * self.scale_factor)
            self.img_display = cv2.resize(frame, (new_width, max_height))
        else:
            self.img_display = frame.copy()
            self.scale_factor = 1.0
        
        cv2.namedWindow('Chọn vùng text - Nhấn SPACE để xác nhận, ESC để hủy', cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback('Chọn vùng text - Nhấn SPACE để xác nhận, ESC để hủy', self.mouse_callback)
        
        # Hiển thị hướng dẫn
        instruction_img = self.img_display.copy()
        cv2.putText(instruction_img, 'Keo chuot de chon vung text', (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(instruction_img, 'SPACE: Xac nhan | ESC: Huy | ENTER: Hoan thanh', (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow('Chọn vùng text - Nhấn SPACE để xác nhận, ESC để hủy', instruction_img)
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == 32:  # SPACE - xác nhận vùng hiện tại
                if len(self.current_region) == 2:
                    # Convert về tọa độ gốc
                    x1 = int(self.current_region[0][0] / self.scale_factor)
                    y1 = int(self.current_region[0][1] / self.scale_factor)
                    x2 = int(self.current_region[1][0] / self.scale_factor)
                    y2 = int(self.current_region[1][1] / self.scale_factor)
                    
                    # Đảm bảo tọa độ đúng thứ tự
                    x1, x2 = min(x1, x2), max(x1, x2)
                    y1, y2 = min(y1, y2), max(y1, y2)
                    
                    self.regions.append([(x1, y1), (x2, y2)])
                    print(f"✅ Đã thêm vùng {len(self.regions)}: ({x1},{y1}) -> ({x2},{y2})")
                    self.current_region = []
                    
            elif key == 27:  # ESC - hủy
                break
                
            elif key == 13:  # ENTER - hoàn thành
                if self.regions:
                    break
                else:
                    print("⚠️  Chưa chọn vùng nào!")
        
        cv2.destroyAllWindows()
        return self.regions

class VideoRemoverApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('RemoveText - Enhanced with Existing Modules')
        width = 450
        height = 600
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.minsize(900, 1200)
        self.resizable(True, True)
        self.selected_video = tk.StringVar()
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.status = tk.StringVar(value='Sẵn sàng')
        self.progress_value = tk.DoubleVar(value=0)
        self.log_queue = queue.Queue()
        self.selected_regions = []
        self.has_advanced_modules = self.check_modules()
        self._canvas_frame = None
        self._canvas_imgtk = None
        self._canvas_current_rect = None
        self._canvas_start_x = 0
        self._canvas_start_y = 0
        self._canvas_rects = []
        # Đặt giá trị mặc định cho settings để không bao giờ là None
        import settings
        settings.CHINESE_MODE = self.chinese_mode.get() if hasattr(self, 'chinese_mode') else True
        settings.PROCESSING_MODE = True if self.has_advanced_modules else False
        self.create_widgets()
        self.after(100, self.update_gui)

    def check_modules(self):
        """Kiểm tra xem có import được các module nâng cao không"""
        try:
            from video_processing import process_video_optimized
            from masking import create_advanced_mask
            from inpainting import advanced_inpaint
            return True
        except ImportError:
            return False

    def create_widgets(self):
        bold_font = ('Arial', 11, 'bold')
        # Sử dụng Notebook để tạo tab
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=0, pady=0)

        # Tab 1: Giao diện chính với scroll
        main_frame = tk.Frame(self.notebook)
        main_canvas = tk.Canvas(main_frame, borderwidth=0)
        main_scrollbar = tk.Scrollbar(main_frame, orient='vertical', command=main_canvas.yview)
        main_canvas.configure(yscrollcommand=main_scrollbar.set)
        main_scrollable = tk.Frame(main_canvas)
        main_scrollable.bind(
            "<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.create_window((0, 0), window=main_scrollable, anchor='nw')
        main_canvas.pack(side='left', fill='both', expand=True)
        main_scrollbar.pack(side='right', fill='y')
        self._main_frame = main_scrollable
        # File selection
        frame_video = tk.Frame(main_scrollable)
        frame_video.pack(fill='x', padx=20, pady=(20, 0))
        tk.Label(frame_video, text='File video:', font=bold_font).pack(side='left')
        self.video_entry = tk.Entry(frame_video, textvariable=self.selected_video, width=50, state='readonly', font=bold_font)
        self.video_entry.pack(side='left', padx=5)
        tk.Button(frame_video, text='Chọn...', command=self.choose_video_file, font=bold_font).pack(side='left')
        # Output directory
        frame_output = tk.Frame(main_scrollable)
        frame_output.pack(fill='x', padx=20, pady=10)
        tk.Label(frame_output, text='Thư mục lưu:', font=bold_font).pack(side='left')
        self.output_entry = tk.Entry(frame_output, textvariable=self.output_dir, width=40, font=bold_font)
        self.output_entry.pack(side='left', padx=5)
        tk.Button(frame_output, text='Chọn...', command=self.choose_output_dir, font=bold_font).pack(side='left')
        # Region selection frame
        region_frame = tk.LabelFrame(main_scrollable, text='Chọn vùng text', padx=5, pady=5, font=bold_font)
        region_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Button(region_frame, text='Xóa vùng đã chọn', command=self.clear_regions, width=15, font=bold_font).pack(side='right', padx=5)
        self.region_info = tk.Label(region_frame, text='Chưa chọn vùng nào', fg='red', font=bold_font)
        self.region_info.pack(side='left', padx=10)
        # Preview Canvas
        preview_frame = tk.LabelFrame(main_scrollable, text='Preview & chọn vùng', padx=5, pady=5, font=bold_font)
        preview_frame.pack(padx=20, pady=(0, 5))
        self.preview_canvas = tk.Canvas(preview_frame, width=800, height=450, bg='black')
        self.preview_canvas.pack()
        self.preview_canvas.bind('<ButtonPress-1>', self.on_canvas_mouse_down)
        self.preview_canvas.bind('<B1-Motion>', self.on_canvas_mouse_move)
        self.preview_canvas.bind('<ButtonRelease-1>', self.on_canvas_mouse_up)
        tk.Button(preview_frame, text='Xóa vùng cuối', command=self.delete_last_region, bg='orange', fg='white', font=bold_font).pack(side='left', padx=5)
        # Processing method selection
        method_frame = tk.LabelFrame(main_scrollable, text='Phương pháp xử lý', padx=5, pady=5, font=bold_font)
        method_frame.pack(fill='x', padx=20, pady=(0, 5))
        self.processing_method = tk.StringVar(value='advanced_modules' if self.has_advanced_modules else 'basic')
        if self.has_advanced_modules:
            tk.Radiobutton(method_frame, text='Sử dụng modules nâng cao', variable=self.processing_method, value='advanced_modules', font=bold_font).pack(side='left')
            tk.Radiobutton(method_frame, text='Xử lý cơ bản', variable=self.processing_method, value='basic', font=bold_font).pack(side='left')
        else:
            tk.Label(method_frame, text='Chỉ có phương pháp cơ bản', fg='orange', font=bold_font).pack(side='left')
        # Chinese mode toggle
        chinese_frame = tk.LabelFrame(main_scrollable, text='Tối ưu tiếng Trung', padx=5, pady=5, font=bold_font)
        chinese_frame.pack(fill='x', padx=20, pady=(0, 5))
        self.chinese_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(chinese_frame, text='Bật chế độ tiếng Trung', variable=self.chinese_mode, font=bold_font).pack(side='left')
        # Video cutting
        cut_frame = tk.LabelFrame(main_scrollable, text='Cắt video', padx=5, pady=5, font=bold_font)
        cut_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Label(cut_frame, text='Số giây/đoạn:', font=bold_font).pack(side='left')
        self.cut_seconds = tk.Entry(cut_frame, width=8, font=bold_font)
        self.cut_seconds.pack(side='left', padx=5)
        tk.Button(cut_frame, text='Cắt video', command=self.start_cut_video, font=bold_font).pack(side='left', padx=5)
        tk.Button(cut_frame, text='Trích audio', command=self.start_extract_audio, font=bold_font).pack(side='left', padx=5)
        # Process button
        self.process_btn = tk.Button(main_scrollable, text='Xử lý Text', command=self.start_processing, width=15, bg='green', fg='white', font=bold_font)
        self.process_btn.pack(pady=5)
        # Progress bar
        self.progress = ttk.Progressbar(main_scrollable, variable=self.progress_value, maximum=100, length=650)
        self.progress.pack(padx=20, pady=(0, 5))
        # Log area
        log_frame = tk.LabelFrame(main_scrollable, text='Log', padx=5, pady=5, font=bold_font)
        log_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=8, wrap='word', bg='#f7f7f7', font=bold_font)
        self.log_text.pack(fill='both', expand=True)
        # Status
        self.status_label = tk.Label(main_scrollable, textvariable=self.status, fg='blue', font=bold_font)
        self.status_label.pack(padx=20, pady=5)
        self.notebook.add(main_frame, text='Chức năng chính',)

        # Tab 2: Theo dõi tool với scroll
        monitor_frame = tk.Frame(self.notebook)
        monitor_canvas = tk.Canvas(monitor_frame, borderwidth=0)
        monitor_scrollbar = tk.Scrollbar(monitor_frame, orient='vertical', command=monitor_canvas.yview)
        monitor_canvas.configure(yscrollcommand=monitor_scrollbar.set)
        monitor_scrollable = tk.Frame(monitor_canvas)
        monitor_scrollable.bind(
            "<Configure>", lambda e: monitor_canvas.configure(scrollregion=monitor_canvas.bbox("all")))
        monitor_canvas.create_window((0, 0), window=monitor_scrollable, anchor='nw')
        monitor_canvas.pack(side='left', fill='both', expand=True)
        monitor_scrollbar.pack(side='right', fill='y')
        self.monitor_text = tk.Text(monitor_scrollable, height=30, bg='#222', fg='#0f0', font=('Consolas', 11, 'bold'))
        self.monitor_text.pack(fill='both', expand=True)
        self.notebook.add(monitor_frame, text='Theo dõi tool',)

        # Tab TikTok
        tiktok_frame = tk.Frame(self.notebook)
        tiktok_canvas = tk.Canvas(tiktok_frame, borderwidth=0)
        tiktok_scrollbar = tk.Scrollbar(tiktok_frame, orient='vertical', command=tiktok_canvas.yview)
        tiktok_canvas.configure(yscrollcommand=tiktok_scrollbar.set)
        tiktok_scrollable = tk.Frame(tiktok_canvas)
        tiktok_scrollable.bind(
            "<Configure>", lambda e: tiktok_canvas.configure(scrollregion=tiktok_canvas.bbox("all")))
        tiktok_canvas.create_window((0, 0), window=tiktok_scrollable, anchor='nw')
        tiktok_canvas.pack(side='left', fill='both', expand=True)
        tiktok_scrollbar.pack(side='right', fill='y')
        # Bước 1: Chọn file cookies TikTok
        tk.Label(tiktok_scrollable, text='Bước 1: Chọn file cookies TikTok', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(20, 0))
        tiktok_cookie_frame = tk.Frame(tiktok_scrollable)
        tiktok_cookie_frame.pack(fill='x', padx=20, pady=5)
        self.tiktok_cookies_file = tk.StringVar(value='')
        self.tiktok_cookies_entry = tk.Entry(tiktok_cookie_frame, textvariable=self.tiktok_cookies_file, width=40, font=bold_font)
        self.tiktok_cookies_entry.pack(side='left', padx=5)
        tk.Button(tiktok_cookie_frame, text='Chọn...', command=self.choose_tiktok_cookies_file, font=bold_font).pack(side='left')
        self.tiktok_cookie_status = tk.Label(tiktok_cookie_frame, text='Chưa chọn file cookies', fg='red', font=bold_font)
        self.tiktok_cookie_status.pack(side='left', padx=10)
        # Bước 2: Chọn thư mục lưu
        tk.Label(tiktok_scrollable, text='Bước 2: Chọn thư mục lưu file tải về', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        tiktok_out_frame = tk.Frame(tiktok_scrollable)
        tiktok_out_frame.pack(fill='x', padx=20, pady=5)
        self.tiktok_output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.tiktok_output_entry = tk.Entry(tiktok_out_frame, textvariable=self.tiktok_output_dir, width=40, font=bold_font)
        self.tiktok_output_entry.pack(side='left', padx=5)
        tk.Button(tiktok_out_frame, text='Chọn...', command=self.choose_tiktok_output_dir, font=bold_font).pack(side='left')
        self.tiktok_output_status = tk.Label(tiktok_out_frame, text='Chưa chọn thư mục lưu', fg='red', font=bold_font)
        self.tiktok_output_status.pack(side='left', padx=10)
        # Bước 3: Nhập link profile và lấy link video
        tk.Label(tiktok_scrollable, text='Bước 3: Nhập link profile TikTok và bấm "Lấy link Video"', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        tiktok_user_frame = tk.Frame(tiktok_scrollable)
        tiktok_user_frame.pack(fill='x', padx=20, pady=5)
        self.tiktok_user_url = tk.StringVar(value='')
        self.tiktok_user_entry = tk.Entry(tiktok_user_frame, textvariable=self.tiktok_user_url, width=50, font=bold_font)
        self.tiktok_user_entry.pack(side='left', padx=5)
        tk.Label(tiktok_user_frame, text='Số lượng link muốn lấy:', font=bold_font).pack(side='left', padx=5)
        self.tiktok_num_links = tk.IntVar(value=20)
        tk.Entry(tiktok_user_frame, textvariable=self.tiktok_num_links, width=5, font=bold_font).pack(side='left', padx=5)
        self.tiktok_get_links_btn = tk.Button(tiktok_user_frame, text='Lấy link Video', command=self.get_all_tiktok_video_links_selenium, font=bold_font, bg='#0af')
        self.tiktok_get_links_btn.pack(side='left', padx=5)
        tk.Label(tiktok_user_frame, text='(Ví dụ: https://www.tiktok.com/@username)', font=('Arial', 10, 'italic')).pack(side='left', padx=10)
        # Bước 4: Xem và tải hàng loạt
        tk.Label(tiktok_scrollable, text='Bước 4: Kiểm tra danh sách link và bấm "Tải hàng loạt"', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        self.tiktok_links_text = tk.Text(tiktok_scrollable, height=10, width=80, font=bold_font)
        self.tiktok_links_text.pack(padx=20, pady=5)
        tiktok_btn_frame = tk.Frame(tiktok_scrollable)
        tiktok_btn_frame.pack(pady=10)
        self.tiktok_download_btn = tk.Button(tiktok_btn_frame, text='Tải hàng loạt', command=self.start_tiktok_download, width=15, bg='blue', fg='white', font=bold_font)
        self.tiktok_download_btn.pack(side='left', padx=5)
        self.tiktok_cancel_btn = tk.Button(tiktok_btn_frame, text='Cancel', command=self.cancel_tiktok_download, width=10, bg='red', fg='white', font=bold_font, state='disabled')
        self.tiktok_cancel_btn.pack(side='left', padx=5)
        self.tiktok_log_text = tk.Text(tiktok_scrollable, height=10, wrap='word', bg='#f7f7f7', font=bold_font)
        self.tiktok_log_text.pack(fill='both', expand=True, padx=20, pady=5)
        self.notebook.add(tiktok_frame, text='Tải TikTok Video')

        # Tab Facebook
        fb_frame = tk.Frame(self.notebook)
        fb_canvas = tk.Canvas(fb_frame, borderwidth=0)
        fb_scrollbar = tk.Scrollbar(fb_frame, orient='vertical', command=fb_canvas.yview)
        fb_canvas.configure(yscrollcommand=fb_scrollbar.set)
        fb_scrollable = tk.Frame(fb_canvas)
        fb_scrollable.bind(
            "<Configure>", lambda e: fb_canvas.configure(scrollregion=fb_canvas.bbox("all")))
        fb_canvas.create_window((0, 0), window=fb_scrollable, anchor='nw')
        fb_canvas.pack(side='left', fill='both', expand=True)
        fb_scrollbar.pack(side='right', fill='y')
        # Bước 1: Chọn file cookies Facebook
        tk.Label(fb_scrollable, text='Bước 1: Chọn file cookies Facebook', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(20, 0))
        fb_cookie_frame = tk.Frame(fb_scrollable)
        fb_cookie_frame.pack(fill='x', padx=20, pady=5)
        self.fb_cookies_file = tk.StringVar(value='')
        self.fb_cookies_entry = tk.Entry(fb_cookie_frame, textvariable=self.fb_cookies_file, width=40, font=bold_font)
        self.fb_cookies_entry.pack(side='left', padx=5)
        tk.Button(fb_cookie_frame, text='Chọn...', command=self.choose_fb_cookies_file, font=bold_font).pack(side='left')
        self.fb_cookie_status = tk.Label(fb_cookie_frame, text='Chưa chọn file cookies', fg='red', font=bold_font)
        self.fb_cookie_status.pack(side='left', padx=10)
        # Bước 2: Chọn thư mục lưu
        tk.Label(fb_scrollable, text='Bước 2: Chọn thư mục lưu file tải về', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        fb_out_frame = tk.Frame(fb_scrollable)
        fb_out_frame.pack(fill='x', padx=20, pady=5)
        self.fb_output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.fb_output_entry = tk.Entry(fb_out_frame, textvariable=self.fb_output_dir, width=40, font=bold_font)
        self.fb_output_entry.pack(side='left', padx=5)
        tk.Button(fb_out_frame, text='Chọn...', command=self.choose_fb_output_dir, font=bold_font).pack(side='left')
        self.fb_output_status = tk.Label(fb_out_frame, text='Chưa chọn thư mục lưu', fg='red', font=bold_font)
        self.fb_output_status.pack(side='left', padx=10)
        # Bước 3: Nhập link profile và lấy link reel
        tk.Label(fb_scrollable, text='Bước 3: Nhập link profile Facebook và bấm "Lấy link Reel"', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        fb_user_frame = tk.Frame(fb_scrollable)
        fb_user_frame.pack(fill='x', padx=20, pady=5)
        self.fb_user_url = tk.StringVar(value='')
        self.fb_user_entry = tk.Entry(fb_user_frame, textvariable=self.fb_user_url, width=50, font=bold_font)
        self.fb_user_entry.pack(side='left', padx=5)
        tk.Label(fb_user_frame, text='Số lượng link muốn lấy:', font=bold_font).pack(side='left', padx=5)
        self.fb_num_links = tk.IntVar(value=20)
        tk.Entry(fb_user_frame, textvariable=self.fb_num_links, width=5, font=bold_font).pack(side='left', padx=5)
        self.fb_get_links_btn = tk.Button(fb_user_frame, text='Lấy link Reel', command=self.get_all_fb_reel_links_selenium, font=bold_font, bg='#0af')
        self.fb_get_links_btn.pack(side='left', padx=5)
        tk.Label(fb_user_frame, text='(Ví dụ: https://www.facebook.com/username/reels/)', font=('Arial', 10, 'italic')).pack(side='left', padx=10)
        # Bước 4: Xem và tải hàng loạt
        tk.Label(fb_scrollable, text='Bước 4: Kiểm tra danh sách link và bấm "Tải hàng loạt"', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        self.fb_links_text = tk.Text(fb_scrollable, height=10, width=80, font=bold_font)
        self.fb_links_text.pack(padx=20, pady=5)
        fb_btn_frame = tk.Frame(fb_scrollable)
        fb_btn_frame.pack(pady=10)
        self.fb_download_btn = tk.Button(fb_btn_frame, text='Tải hàng loạt', command=self.start_fb_download, width=15, bg='blue', fg='white', font=bold_font)
        self.fb_download_btn.pack(side='left', padx=5)
        self.fb_cancel_btn = tk.Button(fb_btn_frame, text='Cancel', command=self.cancel_fb_download, width=10, bg='red', fg='white', font=bold_font, state='disabled')
        self.fb_cancel_btn.pack(side='left', padx=5)
        self.fb_log_text = tk.Text(fb_scrollable, height=10, wrap='word', bg='#f7f7f7', font=bold_font)
        self.fb_log_text.pack(fill='both', expand=True, padx=20, pady=5)
        self.notebook.add(fb_frame, text='Tải Facebook Reel')

        # Tab Instagram
        insta_frame = tk.Frame(self.notebook)
        insta_canvas = tk.Canvas(insta_frame, borderwidth=0)
        insta_scrollbar = tk.Scrollbar(insta_frame, orient='vertical', command=insta_canvas.yview)
        insta_canvas.configure(yscrollcommand=insta_scrollbar.set)
        insta_scrollable = tk.Frame(insta_canvas)
        insta_scrollable.bind(
            "<Configure>", lambda e: insta_canvas.configure(scrollregion=insta_canvas.bbox("all")))
        insta_canvas.create_window((0, 0), window=insta_scrollable, anchor='nw')
        insta_canvas.pack(side='left', fill='both', expand=True)
        insta_scrollbar.pack(side='right', fill='y')
        # Bước 1: Chọn file cookies Instagram
        tk.Label(insta_scrollable, text='Bước 1: Chọn file cookies Instagram', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(20, 0))
        insta_cookie_frame = tk.Frame(insta_scrollable)
        insta_cookie_frame.pack(fill='x', padx=20, pady=5)
        self.insta_cookies_file = tk.StringVar(value='')
        self.insta_cookies_entry = tk.Entry(insta_cookie_frame, textvariable=self.insta_cookies_file, width=40, font=bold_font)
        self.insta_cookies_entry.pack(side='left', padx=5)
        tk.Button(insta_cookie_frame, text='Chọn...', command=self.choose_insta_cookies_file, font=bold_font).pack(side='left')
        self.insta_cookie_status = tk.Label(insta_cookie_frame, text='Chưa chọn file cookies', fg='red', font=bold_font)
        self.insta_cookie_status.pack(side='left', padx=10)
        # Bước 2: Chọn thư mục lưu
        tk.Label(insta_scrollable, text='Bước 2: Chọn thư mục lưu file tải về', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        insta_out_frame = tk.Frame(insta_scrollable)
        insta_out_frame.pack(fill='x', padx=20, pady=5)
        self.insta_output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.insta_output_entry = tk.Entry(insta_out_frame, textvariable=self.insta_output_dir, width=40, font=bold_font)
        self.insta_output_entry.pack(side='left', padx=5)
        tk.Button(insta_out_frame, text='Chọn...', command=self.choose_insta_output_dir, font=bold_font).pack(side='left')
        self.insta_output_status = tk.Label(insta_out_frame, text='Chưa chọn thư mục lưu', fg='red', font=bold_font)
        self.insta_output_status.pack(side='left', padx=10)
        # Bước 3: Nhập link profile và lấy link reel
        tk.Label(insta_scrollable, text='Bước 3: Nhập link profile Instagram và bấm "Lấy link Reel"', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        insta_user_frame = tk.Frame(insta_scrollable)
        insta_user_frame.pack(fill='x', padx=20, pady=5)
        self.insta_user_url = tk.StringVar(value='')
        self.insta_user_entry = tk.Entry(insta_user_frame, textvariable=self.insta_user_url, width=50, font=bold_font)
        self.insta_user_entry.pack(side='left', padx=5)
        tk.Label(insta_user_frame, text='Số lượng link muốn lấy:', font=bold_font).pack(side='left', padx=5)
        self.insta_num_links = tk.IntVar(value=20)
        tk.Entry(insta_user_frame, textvariable=self.insta_num_links, width=5, font=bold_font).pack(side='left', padx=5)
        self.insta_get_links_btn = tk.Button(insta_user_frame, text='Lấy link Reel', command=self.get_all_insta_reel_links_selenium, font=bold_font, bg='#0af')
        self.insta_get_links_btn.pack(side='left', padx=5)
        tk.Label(insta_user_frame, text='(Ví dụ: https://www.instagram.com/username/)', font=('Arial', 10, 'italic')).pack(side='left', padx=10)
        # Bước 4: Xem và tải hàng loạt
        tk.Label(insta_scrollable, text='Bước 4: Kiểm tra danh sách link và bấm "Tải hàng loạt"', font=('Arial', 12, 'bold')).pack(anchor='w', padx=20, pady=(10, 0))
        self.insta_links_text = tk.Text(insta_scrollable, height=10, width=80, font=bold_font)
        self.insta_links_text.pack(padx=20, pady=5)
        insta_btn_frame = tk.Frame(insta_scrollable)
        insta_btn_frame.pack(pady=10)
        self.insta_download_btn = tk.Button(insta_btn_frame, text='Tải hàng loạt', command=self.start_insta_download, width=15, bg='blue', fg='white', font=bold_font)
        self.insta_download_btn.pack(side='left', padx=5)
        self.insta_cancel_btn = tk.Button(insta_btn_frame, text='Cancel', command=self.cancel_insta_download, width=10, bg='red', fg='white', font=bold_font, state='disabled')
        self.insta_cancel_btn.pack(side='left', padx=5)
        self.insta_log_text = tk.Text(insta_scrollable, height=10, wrap='word', bg='#f7f7f7', font=bold_font)
        self.insta_log_text.pack(fill='both', expand=True, padx=20, pady=5)
        self.notebook.add(insta_frame, text='Tải Instagram Reel')

        # Tab Remove Music
        remove_music_frame = tk.Frame(self.notebook)
        self.notebook.add(remove_music_frame, text='Remove Nhạc Nền')
        self._init_remove_music_tab(remove_music_frame)

        # Tab Tạo nhạc thư giãn
        relax_music_frame = tk.Frame(self.notebook)
        self.notebook.add(relax_music_frame, text='Tạo nhạc thư giãn')
        self._init_relax_music_tab(relax_music_frame)

    def _init_remove_music_tab(self, parent):
        self.rm_input_path = tk.StringVar()
        self.rm_output_path = tk.StringVar()
        self.rm_keep_vocals = tk.BooleanVar(value=True)
        tk.Label(parent, text='Chọn file video:').pack(pady=5)
        frame1 = tk.Frame(parent)
        frame1.pack(fill='x', padx=10)
        tk.Entry(frame1, textvariable=self.rm_input_path, width=40).pack(side='left', padx=5)
        tk.Button(frame1, text='Chọn...', command=self.rm_choose_input).pack(side='left')
        tk.Label(parent, text='Chọn file lưu kết quả:').pack(pady=5)
        frame2 = tk.Frame(parent)
        frame2.pack(fill='x', padx=10)
        tk.Entry(frame2, textvariable=self.rm_output_path, width=40).pack(side='left', padx=5)
        tk.Button(frame2, text='Chọn...', command=self.rm_choose_output).pack(side='left')
        tk.Checkbutton(parent, text='Chỉ giữ lại giọng nói (vocal)', variable=self.rm_keep_vocals).pack(pady=5)
        tk.Button(parent, text='Remove nhạc nền', command=self.rm_start_remove_music, bg='#4CAF50', fg='white').pack(pady=10)
        self.rm_log_text = tk.Text(parent, height=7, state='normal')
        self.rm_log_text.pack(fill='both', padx=10, pady=5)

    def rm_choose_input(self):
        path = filedialog.askopenfilename(title='Chọn file video', filetypes=[('Video files', '*.mp4;*.mkv;*.avi;*.mov'), ('All files', '*.*')])
        if path:
            self.rm_input_path.set(path)
            if not self.rm_output_path.get():
                out = os.path.splitext(path)[0] + '_no_music.mp4'
                self.rm_output_path.set(out)

    def rm_choose_output(self):
        path = filedialog.asksaveasfilename(title='Chọn file lưu', defaultextension='.mp4', filetypes=[('MP4 files', '*.mp4'), ('All files', '*.*')])
        if path:
            self.rm_output_path.set(path)

    def rm_log(self, msg):
        self.rm_log_text.config(state='normal')
        self.rm_log_text.insert('end', msg + '\n')
        self.rm_log_text.see('end')
        self.rm_log_text.config(state='normal')

    def rm_start_remove_music(self):
        inp = self.rm_input_path.get()
        outp = self.rm_output_path.get()
        keep = self.rm_keep_vocals.get()
        if not inp or not outp:
            messagebox.showerror('Thiếu thông tin', 'Vui lòng chọn file video và file lưu kết quả!')
            return
        self.rm_log('🔄 Bắt đầu xử lý...')
        threading.Thread(target=self._rm_run_remove_music, args=(inp, outp, keep), daemon=True).start()

    def _rm_run_remove_music(self, inp, outp, keep):
        try:
            self.rm_log(f'🔄 Đang xử lý: {inp}')
            result = remove_music_from_video_smart(inp, outp, keep)
            self.rm_log(f'✅ Đã lưu file: {result}')
        except Exception as e:
            self.rm_log(f'❌ Lỗi: {e}')

    def choose_video_file(self):
        filetypes = [("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.webm")]
        file_selected = filedialog.askopenfilename(title='Chọn video', filetypes=filetypes)
        if file_selected:
            self.selected_video.set(file_selected)
            self.clear_regions()
            self.show_first_frame_on_canvas(file_selected)

    def choose_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.output_dir.get())
        if dir_selected:
            self.output_dir.set(dir_selected)

    def show_first_frame_on_canvas(self, video_path):
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if ret:
            h, w = frame.shape[:2]
            scale = min(800/w, 450/h, 1.0)
            new_w, new_h = int(w*scale), int(h*scale)
            frame_resized = cv2.resize(frame, (new_w, new_h))
            img = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img)
            self._canvas_imgtk = ImageTk.PhotoImage(pil_img)
            self.preview_canvas.delete('all')
            self.preview_canvas.create_image(0, 0, anchor='nw', image=self._canvas_imgtk)
            self._canvas_frame = frame
            self._canvas_scale = scale
            self.selected_regions = []
            self._canvas_rects = []
            self.region_info.config(text='Chưa chọn vùng nào', fg='red')

    def on_canvas_mouse_down(self, event):
        self._canvas_start_x = event.x
        self._canvas_start_y = event.y
        self._canvas_current_rect = self.preview_canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=2)

    def on_canvas_mouse_move(self, event):
        if self._canvas_current_rect is not None:
            self.preview_canvas.coords(self._canvas_current_rect, self._canvas_start_x, self._canvas_start_y, event.x, event.y)

    def on_canvas_mouse_up(self, event):
        if self._canvas_current_rect is not None:
            x1, y1 = self._canvas_start_x, self._canvas_start_y
            x2, y2 = event.x, event.y
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            if abs(x2-x1) > 5 and abs(y2-y1) > 5:
                # Lưu vùng chọn (scale về kích thước gốc)
                scale = getattr(self, '_canvas_scale', 1.0)
                self.selected_regions.append([(int(x1/scale), int(y1/scale)), (int(x2/scale), int(y2/scale))])
                self._canvas_rects.append(self._canvas_current_rect)
                idx = len(self.selected_regions)
                # Vẽ số thứ tự nổi bật: outline trắng, text đỏ
                font = ('Arial', 14, 'bold')
                # Outline trắng
                self.preview_canvas.create_text(x1+6, y1-9, text=str(idx), fill='white', anchor='nw', font=font)
                # Text đỏ nổi bật
                self.preview_canvas.create_text(x1+5, y1-10, text=str(idx), fill='red', anchor='nw', font=font)
                self.region_info.config(text=f'Đã chọn {len(self.selected_regions)} vùng', fg='green')
            else:
                self.preview_canvas.delete(self._canvas_current_rect)
            self._canvas_current_rect = None

    def delete_last_region(self):
        if self.selected_regions and self._canvas_rects:
            self.preview_canvas.delete(self._canvas_rects[-1])
            self.selected_regions.pop()
            self._canvas_rects.pop()
            if self.selected_regions:
                self.region_info.config(text=f'Đã chọn {len(self.selected_regions)} vùng', fg='green')
            else:
                self.region_info.config(text='Chưa chọn vùng nào', fg='red')

    def clear_regions(self):
        self.selected_regions = []
        for rect in getattr(self, '_canvas_rects', []):
            self.preview_canvas.delete(rect)
        self._canvas_rects = []
        self.region_info.config(text='Chưa chọn vùng nào', fg='red')
        self.safe_log('🗑️ Đã xóa các vùng đã chọn')

    def safe_log(self, message):
        """Thread-safe logging"""
        self.log_queue.put(('log', message))
        # Ghi log vào monitor_text nếu có
        if hasattr(self, 'monitor_text') and self.monitor_text.winfo_exists():
            self.monitor_text.insert('end', message + '\n')
            self.monitor_text.see('end')

    def safe_messagebox(self, msg_type, title, message):
        """Đưa yêu cầu hiển thị messagebox vào queue để xử lý ở main thread"""
        self.log_queue.put(('messagebox', (msg_type, title, message)))

    def start_processing(self):
        if not self.selected_video.get():
            self.safe_log('❌ Chưa chọn video')
            return
        
        # Kiểm tra file type
        file_path = self.selected_video.get()
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']:
            # Xử lý ảnh đơn lẻ
            self.start_image_processing()
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v', '.webm']:
            # Xử lý video
            self.start_video_processing()
        else:
            self.safe_log(f'❌ Định dạng file không được hỗ trợ: {ext}')
            return

    def start_image_processing(self):
        """Xử lý ảnh đơn lẻ"""
        self.safe_log('🖼️ Bắt đầu xử lý ảnh...')
        self.process_btn.config(state='disabled')
        
        thread = threading.Thread(target=self.process_image_worker, daemon=True)
        thread.start()

    def process_image_worker(self):
        """Worker xử lý ảnh"""
        try:
            import settings
            # Đảm bảo không gọi GUI trong masking
            if settings.CHINESE_MODE is None:
                settings.CHINESE_MODE = self.chinese_mode.get()
            if settings.PROCESSING_MODE is None:
                settings.PROCESSING_MODE = self.processing_method.get() == 'advanced_modules'
            image_path = self.selected_video.get()
            output_dir = self.output_dir.get()
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            # Sử dụng module image_processing hiện có
            if self.has_advanced_modules:
                success = process_single_image_chinese(image_path, output_dir, preview=False)
                if success:
                    self.safe_log('✅ Xử lý ảnh hoàn tất!')
                    self.log_queue.put(('status', '✅ Xử lý ảnh hoàn tất!'))
                else:
                    self.safe_log('❌ Xử lý ảnh thất bại!')
                    self.log_queue.put(('status', '❌ Xử lý ảnh thất bại!'))
            else:
                # Fallback method
                success = self.process_image_fallback(image_path, output_dir)
        except Exception as e:
            self.safe_log(f'❌ Lỗi xử lý ảnh: {e}')
            self.log_queue.put(('status', '❌ Lỗi xử lý ảnh!'))
        finally:
            self.log_queue.put(('enable_button', None))

    def start_video_processing(self):
        # Xác định method và regions phù hợp với logic của process_video_optimized
        if self.selected_regions:
            regions = self.selected_regions
            method = 'manual'
        else:
            regions = None
            method = 'auto'
        chinese_mode = self.chinese_mode.get()
        import settings
        settings.CHINESE_MODE = chinese_mode
        settings.PROCESSING_MODE = (self.processing_method.get() == 'advanced_modules')
        self.safe_log(f'🎬 Bắt đầu xử lý video...')
        self.safe_log(f'📋 Phương pháp: {method}')
        self.safe_log(f'🇨🇳 Chế độ tiếng Trung: {"Bật" if chinese_mode else "Tắt"}')
        if regions:
            self.safe_log(f'✏️  Sử dụng vùng chọn thủ công ({len(regions)} vùng)')
        else:
            self.safe_log('🤖 Sử dụng auto-detect')
        self.process_btn.config(state='disabled')
        thread = threading.Thread(target=self.process_video_worker, args=(settings.CHINESE_MODE, settings.PROCESSING_MODE, regions, method), daemon=True)
        thread.start()

    def process_video_worker(self, chinese_mode, processing_mode, regions, method):
        try:
            import settings
            settings.CHINESE_MODE = chinese_mode
            settings.PROCESSING_MODE = processing_mode
            video_path = self.selected_video.get()
            output_dir = self.output_dir.get()
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            if self.has_advanced_modules and processing_mode:
                from video_processing import process_video_optimized
                success = process_video_optimized(
                    video_path,
                    output_dir,
                    log_callback=self.safe_log,
                    progress_callback=self.safe_progress,
                    regions=regions,
                    method=method
                )
            else:
                success = self.process_video_fallback(video_path, output_dir)
            if success:
                self.safe_log('🎉 Xử lý video hoàn tất!')
                self.log_queue.put(('status', '🎉 Xử lý video hoàn tất!'))
            else:
                self.safe_log('❌ Xử lý video thất bại!')
                self.log_queue.put(('status', '❌ Xử lý video thất bại!'))
        except Exception as e:
            self.safe_log(f'❌ Lỗi xử lý video: {e}')
            self.log_queue.put(('status', '❌ Lỗi xử lý video!'))
        finally:
            self.log_queue.put(('enable_button', None))

    def safe_progress(self, percent):
        """Thread-safe progress update"""
        self.log_queue.put(('progress', percent))

    def process_image_fallback(self, image_path, output_dir):
        """Fallback method cho xử lý ảnh"""
        try:
            self.safe_log('📸 Đang đọc ảnh...')
            img = cv2.imread(image_path)
            if img is None:
                self.safe_log('❌ Không thể đọc ảnh')
                return False
            
            # Tạo mask
            if self.selected_regions:
                mask = self.create_mask_from_regions(img)
            else:
                mask = self.create_auto_mask(img)
            
            # Inpainting
            if np.any(mask):
                self.safe_log('🎨 Đang xử lý inpainting...')
                result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
            else:
                self.safe_log('⚠️  Không phát hiện text nào')
                result = img
            
            # Lưu kết quả
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            output_path = os.path.join(output_dir, f'{image_name}_text_removed.jpg')
            cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            self.safe_log(f'✅ Đã lưu: {os.path.basename(output_path)}')
            return True
            
        except Exception as e:
            self.safe_log(f'❌ Lỗi fallback image: {e}')
            return False

    def process_video_fallback(self, video_path, output_dir):
        """Fallback method cho xử lý video"""
        try:
            self.safe_log('📹 Đang mở video...')
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.safe_log('❌ Không thể mở video')
                return False
            
            # Lấy thông tin video
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            self.safe_log(f'📊 Video: {width}x{height}, {fps:.1f}FPS, {total_frames} frames')
            
            # Tạo video writer
            basename = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(output_dir, f'{basename}_text_removed_fallback.mp4')
            
            # Đảm bảo tương thích mọi phiên bản OpenCV, tránh linter báo lỗi
            fourcc_func = getattr(cv2, 'VideoWriter_fourcc', None)
            if fourcc_func is not None:
                fourcc = fourcc_func(*'mp4v')
            else:
                cv_attr = getattr(cv2, 'cv', None)
                if cv_attr is not None and hasattr(cv_attr, 'CV_FOURCC'):
                    fourcc = cv_attr.CV_FOURCC(*'mp4v')
                else:
                    raise RuntimeError('Không tìm thấy hàm VideoWriter_fourcc phù hợp trong cv2!')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                self.safe_log('❌ Không thể tạo video writer')
                cap.release()
                return False
            
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Xử lý frame
                if self.selected_regions:
                    processed_frame = self.process_frame_with_regions(frame)
                else:
                    processed_frame = self.process_frame_auto(frame)
                
                out.write(processed_frame)
                frame_count += 1
                
                # Update progress
                if frame_count % 30 == 0:
                    progress = (frame_count / total_frames) * 100
                    self.log_queue.put(('progress', progress))
                    self.safe_log(f'⏳ Đã xử lý: {frame_count}/{total_frames} frames ({progress:.1f}%)')
            
            cap.release()
            out.release()
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                file_size = os.path.getsize(output_path) / (1024*1024)
                self.safe_log(f'✅ Video đã lưu: {os.path.basename(output_path)} ({file_size:.1f}MB)')
                return True
            else:
                self.safe_log('❌ Lỗi tạo video output')
                return False
                
        except Exception as e:
            self.safe_log(f'❌ Lỗi fallback video: {e}')
            return False

    def create_mask_from_regions(self, img):
        """Tạo mask từ các vùng đã chọn"""
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        
        for region in self.selected_regions:
            x1, y1 = region[0]
            x2, y2 = region[1]
            
            # Tạo mask cho vùng này
            roi = img[y1:y2, x1:x2]
            if roi.size > 0:
                region_mask = self.create_region_mask(roi)
                mask[y1:y2, x1:x2] = cv2.bitwise_or(mask[y1:y2, x1:x2], region_mask)
        
        return mask

    def create_auto_mask(self, img):
        """Tạo mask tự động"""
        if self.chinese_mode.get():
            return self.create_chinese_mask(img)
        else:
            return self.create_basic_mask(img)

    def create_region_mask(self, roi):
        """Tạo mask cho một vùng cụ thể"""
        try:
            if self.chinese_mode.get():
                return self.create_chinese_mask(roi)
            else:
                return self.create_basic_mask(roi)
        except:
            return np.zeros(roi.shape[:2], dtype=np.uint8)

    def create_basic_mask(self, img):
        """Tạo mask cơ bản"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Simple threshold
            _, mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            
            # Clean up
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            return mask
        except:
            return np.zeros(img.shape[:2], dtype=np.uint8)

    def create_chinese_mask(self, img):
        """Tạo mask tối ưu cho tiếng Trung"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            mask = np.zeros(gray.shape, dtype=np.uint8)
            
            # Multiple threshold levels for Chinese characters
            thresholds = [180, 200, 220, 240, 250]
            for thresh in thresholds:
                _, thresh_mask = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
                mask = cv2.bitwise_or(mask, thresh_mask)  # Sửa lại dòng này
            
            # Adaptive thresholds with different parameters
            adaptive_configs = [
                (cv2.ADAPTIVE_THRESH_MEAN_C, 11, 2),
                (cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 11, 2),
                (cv2.ADAPTIVE_THRESH_MEAN_C, 15, 2),
                (cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 15, 2)
            ]
            
            for method, block_size, C in adaptive_configs:
                adaptive_mask = cv2.adaptiveThreshold(gray, 255, method, cv2.THRESH_BINARY, block_size, C)
                mask = cv2.bitwise_or(mask, adaptive_mask)
            
            # Color ranges optimized for Chinese subtitles
            color_ranges = [
                # White text (various shades)
                ([0, 0, 160], [180, 60, 255]),
                ([0, 0, 180], [180, 40, 255]),
                # Yellow text (common in Chinese videos)
                ([15, 80, 80], [35, 255, 255]),
                ([20, 100, 100], [30, 255, 255]),
                # Red text
                ([0, 100, 100], [10, 255, 255]),
                ([170, 100, 100], [180, 255, 255]),
                # Green text
                ([40, 80, 80], [80, 255, 255]),
                # Blue text
                ([100, 80, 80], [130, 255, 255])
            ]
            
            for lower, upper in color_ranges:
                lower = np.array(lower)
                upper = np.array(upper)
                color_mask = cv2.inRange(hsv, lower, upper)
                mask = cv2.bitwise_or(mask, color_mask)
            
            # Edge detection for character strokes
            edges = cv2.Canny(gray, 30, 100)
            mask = cv2.bitwise_or(mask, edges)
            
            # Morphological operations optimized for Chinese characters
            kernels = [
                cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
                cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            ]
            
            for kernel in kernels:
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.dilate(mask, kernel, iterations=1)
            
            # Filter contours for Chinese character characteristics
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            filtered_mask = np.zeros_like(mask)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 30:  # Smaller minimum for Chinese characters
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h if h > 0 else 0
                    # Chinese characters can be more square
                    if 0.1 < aspect_ratio < 15 and w > 5 and h > 5:
                        # Add padding around detected text
                        padding = 5
                        x = max(0, x - padding)
                        y = max(0, y - padding)
                        w = min(img.shape[1] - x, w + 2*padding)
                        h = min(img.shape[0] - y, h + 2*padding)
                        
                        cv2.rectangle(filtered_mask, (x, y), (x+w, y+h), 255, -1)
            
            # Final morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            filtered_mask = cv2.morphologyEx(filtered_mask, cv2.MORPH_CLOSE, kernel)
            filtered_mask = cv2.dilate(filtered_mask, kernel, iterations=2)
            
            # Smooth the mask
            filtered_mask = cv2.GaussianBlur(filtered_mask, (7, 7), 0)
            _, filtered_mask = cv2.threshold(filtered_mask, 127, 255, cv2.THRESH_BINARY)
            
            return filtered_mask
        except:
            return np.zeros(img.shape[:2], dtype=np.uint8)

    def process_frame_with_regions(self, frame):
        """Xử lý frame với các vùng đã chọn"""
        try:
            # Tạo mask từ regions
            mask = self.create_mask_from_regions(frame)
            
            # Inpainting
            if np.any(mask):
                if self.has_advanced_modules:
                    result = advanced_inpaint(frame, mask)
                else:
                    result = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
                return result
            else:
                return frame
        except:
            return frame

    def process_frame_auto(self, frame):
        """Xử lý frame tự động"""
        try:
            # Tạo mask tự động
            mask = self.create_auto_mask(frame)
            
            # Inpainting
            if np.any(mask):
                if self.has_advanced_modules:
                    result = advanced_inpaint(frame, mask)
                else:
                    result = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
                return result
            else:
                return frame
        except:
            return frame

    def start_cut_video(self):
        if not self.selected_video.get() or not self.cut_seconds.get().isdigit():
            self.safe_log('❌ Chọn video và nhập số giây hợp lệ')
            return
        
        self.safe_log('✂️ Bắt đầu cắt video...')
        self.process_btn.config(state='disabled')
        thread = threading.Thread(target=self.cut_video_worker, daemon=True)
        thread.start()

    def cut_video_worker(self):
        """Worker cắt video bằng ffmpeg"""
        try:
            video_path = self.selected_video.get()
            output_dir = self.output_dir.get()
            seconds = int(self.cut_seconds.get())
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            # Get video duration
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            if duration == 0:
                self.safe_log('❌ Không thể lấy thông tin video')
                return
            basename = os.path.splitext(os.path.basename(video_path))[0]
            ext = os.path.splitext(video_path)[1]
            part = 1
            start = 0
            success_count = 0
            while start < duration:
                end = min(start + seconds, duration)
                output_file = os.path.join(output_dir, f'{basename}_part{part:03d}{ext}')
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(start),
                    '-i', video_path,
                    '-t', str(seconds),
                    '-c', 'copy',
                    output_file
                ]
                self.safe_log(f'✂️ Cắt đoạn {part}: {self.format_time(start)} - {self.format_time(end)}')
                try:
                    result = subprocess.run(cmd, capture_output=True, timeout=300)
                    if result.returncode == 0 and os.path.exists(output_file):
                        file_size = os.path.getsize(output_file) / (1024*1024)
                        self.safe_log(f'✅ Đã tạo: {os.path.basename(output_file)} ({file_size:.1f}MB)')
                        success_count += 1
                    else:
                        self.safe_log(f'❌ Lỗi cắt đoạn {part}')
                except subprocess.TimeoutExpired:
                    self.safe_log(f'⏰ Timeout cắt đoạn {part}')
                except Exception as e:
                    self.safe_log(f'❌ Exception đoạn {part}: {e}')
                part += 1
                start += seconds
                # Update progress
                progress = min(100, (start / duration) * 100)
                self.log_queue.put(('progress', progress))
            self.safe_log(f'🎉 Hoàn thành! Tạo được {success_count}/{part-1} đoạn')
            self.log_queue.put(('status', f'🎉 Cắt xong {success_count} đoạn!'))
        except Exception as e:
            self.safe_log(f'❌ Lỗi cắt video: {e}')
            self.log_queue.put(('status', '❌ Lỗi cắt video!'))
        finally:
            self.log_queue.put(('enable_button', None))

    def start_extract_audio(self):
        if not self.selected_video.get():
            self.safe_log('❌ Chưa chọn video')
            return
        
        self.safe_log('🎵 Bắt đầu trích xuất audio...')
        self.process_btn.config(state='disabled')
        thread = threading.Thread(target=self.extract_audio_worker, daemon=True)
        thread.start()

    def extract_audio_worker(self):
        """Worker trích xuất audio"""
        try:
            video_path = self.selected_video.get()
            output_dir = self.output_dir.get()
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            basename = os.path.splitext(os.path.basename(video_path))[0]
            output_file = os.path.join(output_dir, f'{basename}.mp3')
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'mp3',
                '-ab', '192k',  # Audio bitrate
                output_file
            ]
            self.safe_log('🎵 Đang trích xuất audio...')
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=600)
                if result.returncode == 0 and os.path.exists(output_file):
                    file_size = os.path.getsize(output_file) / (1024*1024)
                    self.safe_log(f'✅ Đã trích xuất: {os.path.basename(output_file)} ({file_size:.1f}MB)')
                    self.log_queue.put(('status', '🎵 Trích audio thành công!'))
                else:
                    self.safe_log('❌ Lỗi trích xuất audio')
                    self.log_queue.put(('status', '❌ Lỗi trích audio!'))
            except subprocess.TimeoutExpired:
                self.safe_log('⏰ Timeout trích xuất audio')
            except Exception as e:
                self.safe_log(f'❌ Exception: {e}')
        except Exception as e:
            self.safe_log(f'❌ Lỗi trích xuất audio: {e}')
        finally:
            self.log_queue.put(('enable_button', None))

    def format_time(self, seconds):
        """Chuyển giây thành HH:MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def update_gui(self):
        """Update GUI từ queue - chạy trên main thread"""
        try:
            while True:
                msg_type, msg_data = self.log_queue.get_nowait()
                if msg_type == 'log':
                    self.log_text.insert('end', msg_data + '\n')
                    self.log_text.see('end')
                elif msg_type == 'progress':
                    self.progress_value.set(msg_data)
                elif msg_type == 'status':
                    self.status.set(msg_data)
                elif msg_type == 'enable_button':
                    self.process_btn.config(state='normal')
                elif msg_type == 'messagebox':
                    # Xử lý messagebox trên main thread
                    mtype, title, message = msg_data
                    if mtype == 'error':
                        messagebox.showerror(title, message)
                    elif mtype == 'info':
                        messagebox.showinfo(title, message)
                    elif mtype == 'warning':
                        messagebox.showwarning(title, message)
        except queue.Empty:
            pass
        # Lên lịch cho lần kiểm tra tiếp theo
        self.after(100, self.update_gui)

    def append_log(self, msg):
        """Thêm log - chỉ gọi từ main thread"""
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')

    def clear_log(self):
        """Xóa log - chỉ gọi từ main thread"""
        self.log_text.delete('1.0', 'end')

    # --- TikTok Tab: Chuẩn hóa workflow ---
    def tiktok_check_ready(self):
        # Chỉ cập nhật trạng thái label, không disable nút lấy link
        cookies_ok = bool(self.tiktok_cookies_file.get())
        output_ok = bool(self.tiktok_output_dir.get())
        url_ok = bool(self.tiktok_user_url.get().strip())
        if cookies_ok:
            self.tiktok_cookie_status.config(text='Đã chọn file cookies', fg='green')
        else:
            self.tiktok_cookie_status.config(text='Chưa chọn file cookies', fg='red')
        if output_ok:
            self.tiktok_output_status.config(text='Đã chọn thư mục lưu', fg='green')
        else:
            self.tiktok_output_status.config(text='Chưa chọn thư mục lưu', fg='red')
        # Luôn enable nút lấy link, chỉ disable khi đang lấy link
        if getattr(self, '_tiktok_getting_links', False):
            self.tiktok_get_links_btn.config(state='disabled')
        else:
            self.tiktok_get_links_btn.config(state='normal')
        self.tiktok_download_btn.config(state='normal' if self.tiktok_links_text.get('1.0', 'end').strip() else 'disabled')

    def choose_tiktok_cookies_file(self):
        file_selected = filedialog.askopenfilename(title='Chọn file cookies TikTok', filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if file_selected:
            self.tiktok_cookies_file.set(file_selected)
        self.tiktok_check_ready()

    def choose_tiktok_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.tiktok_output_dir.get())
        if dir_selected:
            self.tiktok_output_dir.set(dir_selected)
        self.tiktok_check_ready()

    def tiktok_on_profile_url_change(self, *args):
        self.tiktok_check_ready()

    def get_all_tiktok_video_links_selenium(self):
        profile_url = self.tiktok_user_url.get().strip()
        cookies_file = self.tiktok_cookies_file.get().strip() or None
        num_links = self.tiktok_num_links.get() if hasattr(self, 'tiktok_num_links') else 20
        chromedriver_path = self.fb_chromedriver_path.get().strip() if hasattr(self, 'fb_chromedriver_path') else None
        if not profile_url:
            self.tiktok_log_text.insert('end', '❌ Chưa nhập link profile TikTok\n')
            self.tiktok_log_text.see('end')
            return
        if not self.tiktok_output_dir.get():
            self.tiktok_log_text.insert('end', '❌ Bạn phải chọn thư mục lưu trước khi lấy link!\n')
            self.tiktok_log_text.see('end')
            return
        self.tiktok_log_text.insert('end', f'🔎 [Selenium] Đang lấy tối đa {num_links} link video từ: {profile_url}\n')
        self.tiktok_log_text.see('end')
        self.tiktok_get_links_btn.config(state='disabled')
        _tiktok_getting_links = True
        thread = threading.Thread(target=self.get_all_tiktok_video_links_selenium_worker, args=(profile_url, cookies_file, chromedriver_path, num_links), daemon=True)
        thread.start()

    def get_all_tiktok_video_links_selenium_worker(self, profile_url, cookies_file, chromedriver_path, num_links):
        try:
            from tiktok_video_scraper_selenium import get_tiktok_video_links_selenium
            links = get_tiktok_video_links_selenium(profile_url, cookies_file, num_links, chromedriver_path)
            clean_links = []
            for idx, l in enumerate(links, 1):
                m = re.search(r'/video/(\d+)', l)
                if m:
                    clean_links.append(f'{idx:02d}_{m.group(1)} {l}')
            self.tiktok_links_text.config(state='normal')
            self.tiktok_links_text.delete('1.0', 'end')
            if clean_links:
                self.tiktok_links_text.insert('end', '\n'.join(clean_links))
                self.tiktok_download_btn.config(state='normal')
                self.tiktok_log_text.insert('end', f'✅ [Selenium] Đã lấy {len(clean_links)} link video\n')
            else:
                self.tiktok_links_text.insert('end', '')
                self.tiktok_download_btn.config(state='disabled')
                self.tiktok_log_text.insert('end', '[Selenium] ⚠️ Không tìm thấy link video nào\n')
        except Exception as e:
            import traceback
            err_str = str(e) + '\n' + traceback.format_exc()
            self.tiktok_log_text.insert('end', f'[Selenium] ❌ Lỗi lấy link: {err_str}\n')
            self.tiktok_log_text.see('end')
        finally:
            self.tiktok_log_text.see('end')
            _tiktok_getting_links = False
            self.tiktok_get_links_btn.config(state='normal')
            self.tiktok_check_ready()

    def start_tiktok_download(self):
        lines = self.tiktok_links_text.get('1.0', 'end').strip().splitlines()
        links = []
        stt_id_list = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 2:
                stt_id, link = parts
                links.append(link)
                stt_id_list.append(stt_id)
            elif len(parts) == 1:
                links.append(parts[0])
                stt_id_list.append('')
        if not links:
            self.tiktok_log_text.insert('end', '❌ Chưa có link nào để tải\n')
            self.tiktok_log_text.see('end')
            return
        output_dir = self.tiktok_output_dir.get()
        cookies_file = self.tiktok_cookies_file.get().strip() or None
        self.tiktok_download_btn.config(state='disabled')
        self.tiktok_cancel_btn.config(state='normal')
        self.tiktok_cancel_download = False
        self.tiktok_log_text.insert('end', f'🚀 Bắt đầu tải {len(links)} link...\n')
        self.tiktok_log_text.see('end')
        thread = threading.Thread(target=self.tiktok_download_worker, args=(links, output_dir, cookies_file, stt_id_list), daemon=True)
        thread.start()

    def cancel_tiktok_download(self):
        self.tiktok_cancel_download = True
        self.tiktok_log_text.insert('end', '⏹️ Đã yêu cầu dừng tải hàng loạt!\n')
        self.tiktok_log_text.see('end')
        self.tiktok_cancel_btn.config(state='disabled')

    def tiktok_download_worker(self, links, output_dir, cookies_file, stt_id_list):
        def log_callback(msg):
            self.tiktok_log_text.insert('end', msg + '\n')
            self.tiktok_log_text.see('end')
        success_count = 0
        fail_count = 0
        try:
            for idx, (link, stt_id) in enumerate(zip(links, stt_id_list), 1):
                if getattr(self, 'tiktok_cancel_download', False):
                    log_callback(f'⏹️ Đã dừng tải tại link thứ {idx}/{len(links)}')
                    break
                log_callback(f'⬇️ [{idx}/{len(links)}] Đang tải: {stt_id} {link}')
                try:
                    videoid_match = re.search(r'/video/(\d+)', link)
                    videoid = videoid_match.group(1) if videoid_match else f'video_{idx}'
                    prefix = stt_id if stt_id else f'{idx:02d}_{videoid}'
                    output_file_tpl = f'{output_dir}/{prefix}.%(ext)s'
                    cmd = [
                        'yt-dlp',
                        '-o', output_file_tpl,
                        '-f', 'bestvideo+bestaudio/best',
                        '--no-continue',
                        '--no-part',
                        '--no-overwrites',
                        '--no-mtime',
                        '--no-cache-dir',
                        '--force-overwrites',
                        link
                    ]
                    if cookies_file:
                        cmd[1:1] = ['--cookies', cookies_file]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        log_callback(f'✅ Đã lưu: {prefix}')
                        if result.stdout:
                            log_callback('[yt-dlp stdout]\n' + result.stdout)
                        if result.stderr:
                            log_callback('[yt-dlp stderr]\n' + result.stderr)
                        success_count += 1
                    else:
                        log_callback(f'❌ Lỗi tải {link}: {result.stderr}')
                        fail_count += 1
                except Exception as e:
                    log_callback(f'❌ Lỗi tải {link}: {e}')
                    fail_count += 1
                time.sleep(3)
            else:
                log_callback(f'🎉 Đã tải xong tất cả link! Thành công: {success_count}, Thất bại: {fail_count}')
        except Exception as e:
            log_callback(f'❌ Lỗi: {e}')
        finally:
            self.tiktok_download_btn.config(state='normal')
            self.tiktok_cancel_btn.config(state='disabled')
            self.tiktok_check_ready()

    # Các hàm xử lý cho tab mới
    def social_update_platform(self):
        plat = self.social_platform.get()
        if plat == 'tiktok':
            self.social_profile_hint.config(text='(Ví dụ: https://www.tiktok.com/@username)')
        elif plat == 'facebook':
            self.social_profile_hint.config(text='(Ví dụ: https://www.facebook.com/username/reels/)')
        elif plat == 'instagram':
            self.social_profile_hint.config(text='(Ví dụ: https://www.instagram.com/username/)')
        else:
            self.social_profile_hint.config(text='')

    def choose_social_cookies_file(self):
        file_selected = filedialog.askopenfilename(title='Chọn file cookies', filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if file_selected:
            self.social_cookies_file.set(file_selected)
            self.social_cookie_status.config(text='Đã chọn file cookies', fg='green')
        else:
            self.social_cookie_status.config(text='Chưa chọn file cookies', fg='red')

    def choose_social_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.social_output_dir.get())
        if dir_selected:
            self.social_output_dir.set(dir_selected)
            self.social_output_status.config(text='Đã chọn thư mục lưu', fg='green')
        else:
            self.social_output_status.config(text='Chưa chọn thư mục lưu', fg='red')

    def get_all_social_video_links(self):
        plat = self.social_platform.get()
        profile_url = self.social_user_url.get().strip()
        cookies_file = self.social_cookies_file.get().strip() or None
        num_links = self.social_num_links.get() if hasattr(self, 'social_num_links') else 20
        chromedriver_path = self.fb_chromedriver_path.get().strip() if hasattr(self, 'fb_chromedriver_path') else None
        if not profile_url:
            self.social_log_text.insert('end', '❌ Chưa nhập link profile!\n')
            self.social_log_text.see('end')
            return
        if not self.social_output_dir.get():
            self.social_log_text.insert('end', '❌ Bạn phải chọn thư mục lưu trước khi lấy link!\n')
            self.social_log_text.see('end')
            return
        self.social_log_text.insert('end', f'🔎 Đang lấy tối đa {num_links} link video từ: {profile_url}\n')
        self.social_log_text.see('end')
        self.social_get_links_btn.config(state='disabled')
        thread = threading.Thread(target=self.get_all_social_video_links_worker, args=(plat, profile_url, cookies_file, chromedriver_path, num_links), daemon=True)
        thread.start()

    def get_all_social_video_links_worker(self, plat, profile_url, cookies_file, chromedriver_path, num_links):
        try:
            if plat == 'tiktok':
                links = get_tiktok_video_links_selenium(profile_url, cookies_file, num_links, chromedriver_path)
                regex = r'/video/(\d+)'
            elif plat == 'facebook':
                links = get_facebook_reel_links_selenium(profile_url, cookies_file, num_links, chromedriver_path)
                regex = r'/reel/(\d+)'
            elif plat == 'instagram':
                from instagram_reel_scraper_selenium import get_instagram_reel_links_selenium
                links = get_instagram_reel_links_selenium(profile_url, cookies_file, num_links, chromedriver_path)
                regex = r'/reel/(\w+)'
            else:
                links = []
                regex = ''
            clean_links = []
            for idx, l in enumerate(links, 1):
                m = re.search(regex, l)
                if m:
                    clean_links.append(f'{idx:02d}_{m.group(1)} {l}')
            self.social_links_text.config(state='normal')
            self.social_links_text.delete('1.0', 'end')
            if clean_links:
                self.social_links_text.insert('end', '\n'.join(clean_links))
                self.social_download_btn.config(state='normal')
                self.social_log_text.insert('end', f'✅ Đã lấy {len(clean_links)} link video\n')
            else:
                self.social_links_text.insert('end', '')
                self.social_download_btn.config(state='disabled')
                self.social_log_text.insert('end', '⚠️ Không tìm thấy link video nào\n')
        except Exception as e:
            err_str = str(e)
            self.social_log_text.insert('end', f'❌ Lỗi lấy link: {err_str}\n')
            self.social_log_text.see('end')
        finally:
            self.social_log_text.see('end')
            self.social_get_links_btn.config(state='normal')

    def start_social_download(self):
        lines = self.social_links_text.get('1.0', 'end').strip().splitlines()
        links = []
        stt_id_list = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 2:
                stt_id, link = parts
                links.append(link)
                stt_id_list.append(stt_id)
            elif len(parts) == 1:
                links.append(parts[0])
                stt_id_list.append('')
        if not links:
            self.social_log_text.insert('end', '❌ Chưa có link nào để tải\n')
            self.social_log_text.see('end')
            return
        output_dir = self.social_output_dir.get()
        cookies_file = self.social_cookies_file.get().strip() or None
        self.social_download_btn.config(state='disabled')
        self.social_cancel_btn.config(state='normal')
        self.social_cancel_download = False
        self.social_log_text.insert('end', f'🚀 Bắt đầu tải {len(links)} link...\n')
        self.social_log_text.see('end')
        thread = threading.Thread(target=self.social_download_worker, args=(links, output_dir, cookies_file, stt_id_list), daemon=True)
        thread.start()

    def cancel_social_download(self):
        self.social_cancel_download = True
        self.social_log_text.insert('end', '⏹️ Đã yêu cầu dừng tải hàng loạt!\n')
        self.social_log_text.see('end')
        self.social_cancel_btn.config(state='disabled')

    def social_download_worker(self, links, output_dir, cookies_file, stt_id_list):
        def log_callback(msg):
            self.social_log_text.insert('end', msg + '\n')
            self.social_log_text.see('end')
        success_count = 0
        fail_count = 0
        try:
            for idx, (link, stt_id) in enumerate(zip(links, stt_id_list), 1):
                if getattr(self, 'social_cancel_download', False):
                    log_callback(f'⏹️ Đã dừng tải tại link thứ {idx}/{len(links)}')
                    break
                log_callback(f'⬇️ [{idx}/{len(links)}] Đang tải: {stt_id} {link}')
                try:
                    videoid_match = re.search(r'/([\w\d]+)', link)
                    videoid = videoid_match.group(1) if videoid_match else f'video_{idx}'
                    prefix = stt_id if stt_id else f'{idx:02d}_{videoid}'
                    output_file_tpl = f'{output_dir}/{prefix}.%(ext)s'
                    cmd = [
                        'yt-dlp',
                        '-o', output_file_tpl,
                        '-f', 'bestvideo+bestaudio/best',
                        '--no-continue',
                        '--no-part',
                        '--no-overwrites',
                        '--no-mtime',
                        '--no-cache-dir',
                        '--force-overwrites',
                        link
                    ]
                    if cookies_file:
                        cmd[1:1] = ['--cookies', cookies_file]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        log_callback(f'✅ Đã lưu: {prefix}')
                        if result.stdout:
                            log_callback('[yt-dlp stdout]\n' + result.stdout)
                        if result.stderr:
                            log_callback('[yt-dlp stderr]\n' + result.stderr)
                        success_count += 1
                    else:
                        log_callback(f'❌ Lỗi tải {link}: {result.stderr}')
                        fail_count += 1
                except Exception as e:
                    log_callback(f'❌ Lỗi tải {link}: {e}')
                    fail_count += 1
                time.sleep(3)
            else:
                log_callback(f'🎉 Đã tải xong tất cả link! Thành công: {success_count}, Thất bại: {fail_count}')
        except Exception as e:
            log_callback(f'❌ Lỗi: {e}')
        finally:
            self.social_download_btn.config(state='normal')
            self.social_cancel_btn.config(state='disabled')

    def choose_fb_cookies_file(self):
        file_selected = filedialog.askopenfilename(title='Chọn file cookies Facebook', filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if file_selected:
            self.fb_cookies_file.set(file_selected)
            self.fb_cookie_status.config(text='Đã chọn file cookies', fg='green')
        else:
            self.fb_cookie_status.config(text='Chưa chọn file cookies', fg='red')

    def choose_fb_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.fb_output_dir.get())
        if dir_selected:
            self.fb_output_dir.set(dir_selected)
            self.fb_output_status.config(text='Đã chọn thư mục lưu', fg='green')
        else:
            self.fb_output_status.config(text='Chưa chọn thư mục lưu', fg='red')

    def get_all_fb_reel_links_selenium(self):
        profile_url = self.fb_user_url.get().strip()
        cookies_file = self.fb_cookies_file.get().strip() or None
        num_links = self.fb_num_links.get() if hasattr(self, 'fb_num_links') else 20
        chromedriver_path = None  # Nếu có hỗ trợ chọn chromedriver riêng thì lấy từ biến phù hợp
        if not profile_url:
            self.fb_log_text.insert('end', '❌ Chưa nhập link profile Facebook!\n')
            self.fb_log_text.see('end')
            return
        if not self.fb_output_dir.get():
            self.fb_log_text.insert('end', '❌ Bạn phải chọn thư mục lưu trước khi lấy link!\n')
            self.fb_log_text.see('end')
            return
        self.fb_log_text.insert('end', f'🔎 Đang lấy tối đa {num_links} link reel từ: {profile_url}\n')
        self.fb_log_text.see('end')
        self.fb_get_links_btn.config(state='disabled')
        thread = threading.Thread(target=self.get_all_fb_reel_links_selenium_worker, args=(profile_url, cookies_file, chromedriver_path, num_links), daemon=True)
        thread.start()

    def get_all_fb_reel_links_selenium_worker(self, profile_url, cookies_file, chromedriver_path, num_links):
        try:
            links = get_facebook_reel_links_selenium(profile_url, cookies_file, num_links, chromedriver_path)
            clean_links = []
            for idx, l in enumerate(links, 1):
                m = re.search(r'/reel/(\d+)', l)
                if m:
                    clean_links.append(f'{idx:02d}_{m.group(1)} {l}')
            self.fb_links_text.config(state='normal')
            self.fb_links_text.delete('1.0', 'end')
            if clean_links:
                self.fb_links_text.insert('end', '\n'.join(clean_links))
                self.fb_download_btn.config(state='normal')
                self.fb_log_text.insert('end', f'✅ Đã lấy {len(clean_links)} link reel\n')
            else:
                self.fb_links_text.insert('end', '')
                self.fb_download_btn.config(state='disabled')
                self.fb_log_text.insert('end', '⚠️ Không tìm thấy link reel nào\n')
        except Exception as e:
            err_str = str(e)
            self.fb_log_text.insert('end', f'❌ Lỗi lấy link: {err_str}\n')
            self.fb_log_text.see('end')
        finally:
            self.fb_log_text.see('end')
            self.fb_get_links_btn.config(state='normal')

    def start_fb_download(self):
        lines = self.fb_links_text.get('1.0', 'end').strip().splitlines()
        links = []
        stt_id_list = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 2:
                stt_id, link = parts
                links.append(link)
                stt_id_list.append(stt_id)
            elif len(parts) == 1:
                links.append(parts[0])
                stt_id_list.append('')
        if not links:
            self.fb_log_text.insert('end', '❌ Chưa có link nào để tải\n')
            self.fb_log_text.see('end')
            return
        output_dir = self.fb_output_dir.get()
        cookies_file = self.fb_cookies_file.get().strip() or None
        self.fb_download_btn.config(state='disabled')
        self.fb_cancel_btn.config(state='normal')
        self.fb_cancel_download = False
        self.fb_log_text.insert('end', f'🚀 Bắt đầu tải {len(links)} link...\n')
        self.fb_log_text.see('end')
        thread = threading.Thread(target=self.fb_download_worker, args=(links, output_dir, cookies_file, stt_id_list), daemon=True)
        thread.start()

    def fb_download_worker(self, links, output_dir, cookies_file, stt_id_list):
        def log_callback(msg):
            self.fb_log_text.insert('end', msg + '\n')
            self.fb_log_text.see('end')
        success_count = 0
        fail_count = 0
        try:
            for idx, (link, stt_id) in enumerate(zip(links, stt_id_list), 1):
                if getattr(self, 'fb_cancel_download', False):
                    log_callback(f'⏹️ Đã dừng tải tại link thứ {idx}/{len(links)}')
                    break
                log_callback(f'⬇️ [{idx}/{len(links)}] Đang tải: {stt_id} {link}')
                try:
                    videoid_match = re.search(r'/reel/(\d+)', link)
                    videoid = videoid_match.group(1) if videoid_match else f'reel_{idx}'
                    prefix = stt_id if stt_id else f'{idx:02d}_{videoid}'
                    output_file_tpl = f'{output_dir}/{prefix}.%(ext)s'
                    cmd = [
                        'yt-dlp',
                        '-o', output_file_tpl,
                        '-f', 'bestvideo+bestaudio/best',
                        '--no-continue',
                        '--no-part',
                        '--no-overwrites',
                        '--no-mtime',
                        '--no-cache-dir',
                        '--force-overwrites',
                        link
                    ]
                    if cookies_file:
                        cmd[1:1] = ['--cookies', cookies_file]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        log_callback(f'✅ Đã lưu: {prefix}')
                        if result.stdout:
                            log_callback('[yt-dlp stdout]\n' + result.stdout)
                        if result.stderr:
                            log_callback('[yt-dlp stderr]\n' + result.stderr)
                        success_count += 1
                    else:
                        log_callback(f'❌ Lỗi tải {link}: {result.stderr}')
                        fail_count += 1
                except Exception as e:
                    log_callback(f'❌ Lỗi tải {link}: {e}')
                    fail_count += 1
                time.sleep(3)
            else:
                log_callback(f'🎉 Đã tải xong tất cả link! Thành công: {success_count}, Thất bại: {fail_count}')
        except Exception as e:
            log_callback(f'❌ Lỗi: {e}')
        finally:
            self.fb_download_btn.config(state='normal')
            self.fb_cancel_btn.config(state='disabled')

    def cancel_fb_download(self):
        self.fb_cancel_download = True
        self.fb_log_text.insert('end', '⏹️ Đã yêu cầu dừng tải hàng loạt!\n')
        self.fb_log_text.see('end')
        self.fb_cancel_btn.config(state='disabled')

    def choose_insta_cookies_file(self):
        file_selected = filedialog.askopenfilename(title='Chọn file cookies Instagram', filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if file_selected:
            self.insta_cookies_file.set(file_selected)
            self.insta_cookie_status.config(text='Đã chọn file cookies', fg='green')
        else:
            self.insta_cookie_status.config(text='Chưa chọn file cookies', fg='red')

    def choose_insta_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.insta_output_dir.get())
        if dir_selected:
            self.insta_output_dir.set(dir_selected)
            self.insta_output_status.config(text='Đã chọn thư mục lưu', fg='green')
        else:
            self.insta_output_status.config(text='Chưa chọn thư mục lưu', fg='red')

    def get_all_insta_reel_links_selenium(self):
        profile_url = self.insta_user_url.get().strip()
        cookies_file = self.insta_cookies_file.get().strip() or None
        num_links = self.insta_num_links.get() if hasattr(self, 'insta_num_links') else 20
        chromedriver_path = None  # Nếu có hỗ trợ chọn chromedriver riêng thì lấy từ biến phù hợp
        if not profile_url:
            self.insta_log_text.insert('end', '❌ Chưa nhập link profile Instagram!\n')
            self.insta_log_text.see('end')
            return
        if not self.insta_output_dir.get():
            self.insta_log_text.insert('end', '❌ Bạn phải chọn thư mục lưu trước khi lấy link!\n')
            self.insta_log_text.see('end')
            return
        self.insta_log_text.insert('end', f'🔎 Đang lấy tối đa {num_links} link reel từ: {profile_url}\n')
        self.insta_log_text.see('end')
        self.insta_get_links_btn.config(state='disabled')
        thread = threading.Thread(target=self.get_all_insta_reel_links_selenium_worker, args=(profile_url, cookies_file, chromedriver_path, num_links), daemon=True)
        thread.start()

    def get_all_insta_reel_links_selenium_worker(self, profile_url, cookies_file, chromedriver_path, num_links):
        try:
            from instagram_reel_scraper_selenium import get_instagram_reel_links_selenium
            links = get_instagram_reel_links_selenium(profile_url, cookies_file, num_links, chromedriver_path)
            clean_links = []
            for idx, l in enumerate(links, 1):
                m = re.search(r'/reel/([\w-]+)', l)
                if m:
                    clean_links.append(f'{idx:02d}_{m.group(1)} {l}')
            self.insta_links_text.config(state='normal')
            self.insta_links_text.delete('1.0', 'end')
            if clean_links:
                self.insta_links_text.insert('end', '\n'.join(clean_links))
                self.insta_download_btn.config(state='normal')
                self.insta_log_text.insert('end', f'✅ Đã lấy {len(clean_links)} link reel\n')
            else:
                self.insta_links_text.insert('end', '')
                self.insta_download_btn.config(state='disabled')
                self.insta_log_text.insert('end', '⚠️ Không tìm thấy link reel nào\n')
        except Exception as e:
            err_str = str(e)
            self.insta_log_text.insert('end', f'❌ Lỗi lấy link: {err_str}\n')
            self.insta_log_text.see('end')
        finally:
            self.insta_log_text.see('end')
            self.insta_get_links_btn.config(state='normal')

    def start_insta_download(self):
        lines = self.insta_links_text.get('1.0', 'end').strip().splitlines()
        links = []
        stt_id_list = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 2:
                stt_id, link = parts
                links.append(link)
                stt_id_list.append(stt_id)
            elif len(parts) == 1:
                links.append(parts[0])
                stt_id_list.append('')
        if not links:
            self.insta_log_text.insert('end', '❌ Chưa có link nào để tải\n')
            self.insta_log_text.see('end')
            return
        output_dir = self.insta_output_dir.get()
        cookies_file = self.insta_cookies_file.get().strip() or None
        self.insta_download_btn.config(state='disabled')
        self.insta_cancel_btn.config(state='normal')
        self.insta_cancel_download = False
        self.insta_log_text.insert('end', f'🚀 Bắt đầu tải {len(links)} link...\n')
        self.insta_log_text.see('end')
        thread = threading.Thread(target=self.insta_download_worker, args=(links, output_dir, cookies_file, stt_id_list), daemon=True)
        thread.start()

    def cancel_insta_download(self):
        self.insta_cancel_download = True
        self.insta_log_text.insert('end', '⏹️ Đã yêu cầu dừng tải hàng loạt!\n')
        self.insta_log_text.see('end')
        self.insta_cancel_btn.config(state='disabled')

    def insta_download_worker(self, links, output_dir, cookies_file, stt_id_list):
        def log_callback(msg):
            self.insta_log_text.insert('end', msg + '\n')
            self.insta_log_text.see('end')
        success_count = 0
        fail_count = 0
        try:
            for idx, (link, stt_id) in enumerate(zip(links, stt_id_list), 1):
                if getattr(self, 'insta_cancel_download', False):
                    log_callback(f'⏹️ Đã dừng tải tại link thứ {idx}/{len(links)}')
                    break
                log_callback(f'⬇️ [{idx}/{len(links)}] Đang tải: {stt_id} {link}')
                try:
                    videoid_match = re.search(r'/reel/([\w-]+)', link)
                    videoid = videoid_match.group(1) if videoid_match else f'reel_{idx}'
                    prefix = stt_id if stt_id else f'{idx:02d}_{videoid}'
                    output_file_tpl = f'{output_dir}/{prefix}.%(ext)s'
                    cmd = [
                        'yt-dlp',
                        '-o', output_file_tpl,
                        '-f', 'bestvideo+bestaudio/best',
                        '--no-continue',
                        '--no-part',
                        '--no-overwrites',
                        '--no-mtime',
                        '--no-cache-dir',
                        '--force-overwrites',
                        link
                    ]
                    if cookies_file:
                        cmd[1:1] = ['--cookies', cookies_file]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        log_callback(f'✅ Đã lưu: {prefix}')
                        if result.stdout:
                            log_callback('[yt-dlp stdout]\n' + result.stdout)
                        if result.stderr:
                            log_callback('[yt-dlp stderr]\n' + result.stderr)
                        success_count += 1
                    else:
                        log_callback(f'❌ Lỗi tải {link}: {result.stderr}')
                        fail_count += 1
                except Exception as e:
                    log_callback(f'❌ Lỗi tải {link}: {e}')
                    fail_count += 1
                time.sleep(3)
            else:
                log_callback(f'🎉 Đã tải xong tất cả link! Thành công: {success_count}, Thất bại: {fail_count}')
        except Exception as e:
            log_callback(f'❌ Lỗi: {e}')
        finally:
            self.insta_download_btn.config(state='normal')
            self.insta_cancel_btn.config(state='disabled')

    def _init_relax_music_tab(self, parent):
        import tkinter as tk
        from tkinter import ttk
        bold_font = ('Arial', 11, 'bold')
        # Tần số
        freq_frame = tk.Frame(parent)
        freq_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(freq_frame, text='Tần số:', font=bold_font).pack(side='left')
        self.relax_freq = tk.IntVar(value=432)
        tk.Radiobutton(freq_frame, text='432 Hz', variable=self.relax_freq, value=432, font=bold_font).pack(side='left', padx=5)
        tk.Radiobutton(freq_frame, text='416 Hz', variable=self.relax_freq, value=416, font=bold_font).pack(side='left', padx=5)
        # Loại âm thanh
        type_frame = tk.Frame(parent)
        type_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(type_frame, text='Loại âm thanh:', font=bold_font).pack(side='left')
        self.relax_sound_type = tk.StringVar(value='sine')
        tk.Radiobutton(type_frame, text='Sóng sine thuần', variable=self.relax_sound_type, value='sine', font=bold_font).pack(side='left', padx=5)
        tk.Radiobutton(type_frame, text='Singing bowl (chuông ngân)', variable=self.relax_sound_type, value='singing_bowl', font=bold_font).pack(side='left', padx=5)
        # Thời lượng
        dur_frame = tk.Frame(parent)
        dur_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(dur_frame, text='Thời lượng (phút):', font=bold_font).pack(side='left')
        self.relax_duration = tk.StringVar(value='10')
        tk.Entry(dur_frame, textvariable=self.relax_duration, width=5, font=bold_font).pack(side='left', padx=5)
        # Định dạng file
        fmt_frame = tk.Frame(parent)
        fmt_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(fmt_frame, text='Định dạng:', font=bold_font).pack(side='left')
        self.relax_format = tk.StringVar(value='wav')
        fmt_combo = ttk.Combobox(fmt_frame, textvariable=self.relax_format, values=['wav', 'mp3'], width=5, font=bold_font, state='readonly')
        fmt_combo.pack(side='left', padx=5)
        # Sample rate
        sr_frame = tk.Frame(parent)
        sr_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(sr_frame, text='Sample rate:', font=bold_font).pack(side='left')
        self.relax_sr = tk.IntVar(value=44100)
        sr_combo = ttk.Combobox(sr_frame, textvariable=self.relax_sr, values=[44100, 48000], width=7, font=bold_font, state='readonly')
        sr_combo.pack(side='left', padx=5)
        # Fade in/out
        fade_frame = tk.Frame(parent)
        fade_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(fade_frame, text='Fade in (giây):', font=bold_font).pack(side='left')
        self.relax_fadein = tk.StringVar(value='3')
        tk.Entry(fade_frame, textvariable=self.relax_fadein, width=4, font=bold_font).pack(side='left', padx=2)
        tk.Label(fade_frame, text='Fade out (giây):', font=bold_font).pack(side='left', padx=10)
        self.relax_fadeout = tk.StringVar(value='3')
        tk.Entry(fade_frame, textvariable=self.relax_fadeout, width=4, font=bold_font).pack(side='left', padx=2)
        # White noise
        wn_frame = tk.Frame(parent)
        wn_frame.pack(pady=5, padx=10, anchor='w')
        self.relax_add_wn = tk.BooleanVar(value=False)
        tk.Checkbutton(wn_frame, text='Thêm white noise nhẹ', variable=self.relax_add_wn, font=bold_font).pack(side='left')
        # Nút chọn nơi lưu
        out_frame = tk.Frame(parent)
        out_frame.pack(pady=5, padx=10, anchor='w')
        tk.Label(out_frame, text='Lưu vào:', font=bold_font).pack(side='left')
        self.relax_output_path = tk.StringVar()
        tk.Entry(out_frame, textvariable=self.relax_output_path, width=40, font=bold_font).pack(side='left', padx=5)
        tk.Button(out_frame, text='Chọn...', command=self.relax_choose_output).pack(side='left')
        # Nút tạo nhạc
        tk.Button(parent, text='Tạo nhạc', command=self.relax_start_generate, bg='#4CAF50', fg='white', font=bold_font).pack(pady=10)
        # Log
        self.relax_log_text = tk.Text(parent, height=7, state='normal')
        self.relax_log_text.pack(fill='both', padx=10, pady=5)
        # Đường dẫn file đã tạo
        self.relax_result_label = tk.Label(parent, text='', fg='blue', font=bold_font)
        self.relax_result_label.pack(pady=5)

    def relax_choose_output(self):
        import tkinter as tk
        from tkinter import filedialog
        fmt = self.relax_format.get()
        path = filedialog.asksaveasfilename(title='Chọn nơi lưu nhạc', defaultextension=f'.{fmt}', filetypes=[('WAV', '*.wav'), ('MP3', '*.mp3'), ('All files', '*.*')])
        if path:
            self.relax_output_path.set(path)

    def relax_log(self, msg):
        self.relax_log_text.config(state='normal')
        self.relax_log_text.insert('end', msg + '\n')
        self.relax_log_text.see('end')
        self.relax_log_text.config(state='normal')

    def relax_start_generate(self):
        import threading
        self.relax_log('🔄 Đang tạo nhạc...')
        self.relax_result_label.config(text='')
        threading.Thread(target=self._relax_generate_worker, daemon=True).start()

    def _relax_generate_worker(self):
        try:
            from relax_music_generator import generate_relax_music
            freq = int(self.relax_freq.get())
            duration_min = float(self.relax_duration.get())
            duration_sec = int(duration_min * 60)
            fmt = self.relax_format.get()
            sr = int(self.relax_sr.get())
            fadein = float(self.relax_fadein.get())
            fadeout = float(self.relax_fadeout.get())
            add_wn = self.relax_add_wn.get()
            out_path = self.relax_output_path.get()
            sound_type = self.relax_sound_type.get()
            if not out_path:
                self.relax_log('❌ Bạn phải chọn nơi lưu file nhạc!')
                return
            result = generate_relax_music(
                output_path=out_path,
                frequency=freq,
                duration_sec=duration_sec,
                sample_rate=sr,
                file_format=fmt,
                fade_in_sec=fadein,
                fade_out_sec=fadeout,
                add_white_noise=add_wn,
                noise_level=0.01,
                sound_type=sound_type
            )
            self.relax_log(f'✅ Đã tạo file: {result}')
            self.relax_result_label.config(text=f'Đã lưu: {result}')
        except Exception as e:
            self.relax_log(f'❌ Lỗi: {e}')
            self.relax_result_label.config(text='')

def main():
    import platform
    print(f"🖥️  Hệ điều hành: {platform.system()}")
    print("🚀 Khởi động ứng dụng RemoveText cải tiến...")
    
    # Kiểm tra dependencies
    try:
        import cv2
        print(f"✅ OpenCV version: {cv2.__version__}")
    except ImportError:
        print("❌ Thiếu OpenCV. Cài đặt: pip install opencv-python")
        return
    
    try:
        import numpy as np
        print(f"✅ NumPy version: {np.__version__}")
    except ImportError:
        print("❌ Thiếu NumPy. Cài đặt: pip install numpy")
        return
    
    # Kiểm tra ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFmpeg có sẵn")
        else:
            print("⚠️  FFmpeg có thể không hoạt động đúng")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️  Không tìm thấy FFmpeg. Một số tính năng có thể không hoạt động")
        print("   Cài đặt FFmpeg: https://ffmpeg.org/download.html")
    
    try:
        app = VideoRemoverApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ Lỗi khởi động ứng dụng: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
