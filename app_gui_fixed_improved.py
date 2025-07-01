import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
import queue
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageTk

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
        self.geometry('900x700')
        self.minsize(700, 500)
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
        tk.Label(frame_video, text='File video:').pack(side='left')
        self.video_entry = tk.Entry(frame_video, textvariable=self.selected_video, width=50, state='readonly')
        self.video_entry.pack(side='left', padx=5)
        tk.Button(frame_video, text='Chọn...', command=self.choose_video_file).pack(side='left')
        # Output directory
        frame_output = tk.Frame(main_scrollable)
        frame_output.pack(fill='x', padx=20, pady=10)
        tk.Label(frame_output, text='Thư mục lưu:').pack(side='left')
        self.output_entry = tk.Entry(frame_output, textvariable=self.output_dir, width=40)
        self.output_entry.pack(side='left', padx=5)
        tk.Button(frame_output, text='Chọn...', command=self.choose_output_dir).pack(side='left')
        # Region selection frame
        region_frame = tk.LabelFrame(main_scrollable, text='Chọn vùng text', padx=5, pady=5)
        region_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Button(region_frame, text='Xóa vùng đã chọn', command=self.clear_regions, width=15).pack(side='right', padx=5)
        self.region_info = tk.Label(region_frame, text='Chưa chọn vùng nào', fg='red')
        self.region_info.pack(side='left', padx=10)
        # Preview Canvas
        preview_frame = tk.LabelFrame(main_scrollable, text='Preview & chọn vùng', padx=5, pady=5)
        preview_frame.pack(padx=20, pady=(0, 5))
        self.preview_canvas = tk.Canvas(preview_frame, width=800, height=450, bg='black')
        self.preview_canvas.pack()
        self.preview_canvas.bind('<ButtonPress-1>', self.on_canvas_mouse_down)
        self.preview_canvas.bind('<B1-Motion>', self.on_canvas_mouse_move)
        self.preview_canvas.bind('<ButtonRelease-1>', self.on_canvas_mouse_up)
        tk.Button(preview_frame, text='Xóa vùng cuối', command=self.delete_last_region, bg='orange', fg='white').pack(side='left', padx=5)
        # Processing method selection
        method_frame = tk.LabelFrame(main_scrollable, text='Phương pháp xử lý', padx=5, pady=5)
        method_frame.pack(fill='x', padx=20, pady=(0, 5))
        self.processing_method = tk.StringVar(value='advanced_modules' if self.has_advanced_modules else 'basic')
        if self.has_advanced_modules:
            tk.Radiobutton(method_frame, text='Sử dụng modules nâng cao', variable=self.processing_method, value='advanced_modules').pack(side='left')
            tk.Radiobutton(method_frame, text='Xử lý cơ bản', variable=self.processing_method, value='basic').pack(side='left')
        else:
            tk.Label(method_frame, text='Chỉ có phương pháp cơ bản', fg='orange').pack(side='left')
        # Chinese mode toggle
        chinese_frame = tk.LabelFrame(main_scrollable, text='Tối ưu tiếng Trung', padx=5, pady=5)
        chinese_frame.pack(fill='x', padx=20, pady=(0, 5))
        self.chinese_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(chinese_frame, text='Bật chế độ tiếng Trung', variable=self.chinese_mode).pack(side='left')
        # Video cutting
        cut_frame = tk.LabelFrame(main_scrollable, text='Cắt video', padx=5, pady=5)
        cut_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Label(cut_frame, text='Số giây/đoạn:').pack(side='left')
        self.cut_seconds = tk.Entry(cut_frame, width=8)
        self.cut_seconds.pack(side='left', padx=5)
        tk.Button(cut_frame, text='Cắt video', command=self.start_cut_video).pack(side='left', padx=5)
        tk.Button(cut_frame, text='Trích audio', command=self.start_extract_audio).pack(side='left', padx=5)
        # Process button
        self.process_btn = tk.Button(main_scrollable, text='Xử lý Text', command=self.start_processing, width=15, bg='green', fg='white')
        self.process_btn.pack(pady=5)
        # Progress bar
        self.progress = ttk.Progressbar(main_scrollable, variable=self.progress_value, maximum=100, length=650)
        self.progress.pack(padx=20, pady=(0, 5))
        # Log area
        log_frame = tk.LabelFrame(main_scrollable, text='Log', padx=5, pady=5)
        log_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=8, wrap='word', bg='#f7f7f7')
        self.log_text.pack(fill='both', expand=True)
        # Status
        self.status_label = tk.Label(main_scrollable, textvariable=self.status, fg='blue')
        self.status_label.pack(padx=20, pady=5)
        self.notebook.add(main_frame, text='Chức năng chính')

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
        self.monitor_text = tk.Text(monitor_scrollable, height=30, bg='#222', fg='#0f0', font=('Consolas', 11))
        self.monitor_text.pack(fill='both', expand=True)
        self.notebook.add(monitor_frame, text='Theo dõi tool')

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
                self.preview_canvas.create_text(x1+5, y1-10, text=str(idx), fill='yellow', anchor='nw', font=('Arial', 14, 'bold'))
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
        method = self.processing_method.get()
        chinese_mode = self.chinese_mode.get()
        import settings
        settings.CHINESE_MODE = chinese_mode
        settings.PROCESSING_MODE = (method == 'advanced_modules')
        regions = None  # Luôn auto, không chọn vùng thủ công nữa
        # Không còn logic chọn vùng thủ công cho 'basic'
        self.safe_log(f'🎬 Bắt đầu xử lý video...')
        self.safe_log(f'📋 Phương pháp: {method}')
        self.safe_log(f'🇨🇳 Chế độ tiếng Trung: {"Bật" if chinese_mode else "Tắt"}')
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
