import tkinter as tk
from tkinter import filedialog, ttk
import os
import threading
import queue
import subprocess
import cv2
import numpy as np

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'OutputFile')

class VideoRemoverApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('RemoveText - macOS Safe')
        self.geometry('700x600')
        self.resizable(False, False)
        
        self.selected_video = tk.StringVar()
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.status = tk.StringVar(value='Sẵn sàng')
        self.progress_value = tk.DoubleVar(value=0)
        self.log_queue = queue.Queue()
        
        self.create_widgets()
        self.after(100, self.update_gui)

    def create_widgets(self):
        # File selection
        frame_video = tk.Frame(self)
        frame_video.pack(fill='x', padx=20, pady=(20, 0))
        tk.Label(frame_video, text='File video:').pack(side='left')
        self.video_entry = tk.Entry(frame_video, textvariable=self.selected_video, width=50, state='readonly')
        self.video_entry.pack(side='left', padx=5)
        tk.Button(frame_video, text='Chọn...', command=self.choose_video_file).pack(side='left')
        
        # Output directory
        frame_output = tk.Frame(self)
        frame_output.pack(fill='x', padx=20, pady=10)
        tk.Label(frame_output, text='Thư mục lưu:').pack(side='left')
        self.output_entry = tk.Entry(frame_output, textvariable=self.output_dir, width=40)
        self.output_entry.pack(side='left', padx=5)
        tk.Button(frame_output, text='Chọn...', command=self.choose_output_dir).pack(side='left')
        
        # Video cutting
        cut_frame = tk.LabelFrame(self, text='Cắt video', padx=5, pady=5)
        cut_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Label(cut_frame, text='Số giây/đoạn:').pack(side='left')
        self.cut_seconds = tk.Entry(cut_frame, width=8)
        self.cut_seconds.pack(side='left', padx=5)
        tk.Button(cut_frame, text='Cắt video', command=self.start_cut_video).pack(side='left', padx=5)
        tk.Button(cut_frame, text='Trích audio', command=self.start_extract_audio).pack(side='left', padx=5)
        
        # Process button
        self.process_btn = tk.Button(self, text='Xử lý Text', command=self.start_processing, width=15)
        self.process_btn.pack(pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(self, variable=self.progress_value, maximum=100, length=650)
        self.progress.pack(padx=20, pady=(0, 5))
        
        # Log area
        log_frame = tk.LabelFrame(self, text='Log', padx=5, pady=5)
        log_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=8, wrap='word', bg='#f7f7f7')
        self.log_text.pack(fill='both', expand=True)
        
        # Status
        self.status_label = tk.Label(self, textvariable=self.status, fg='blue')
        self.status_label.pack(padx=20, pady=5)

    def choose_video_file(self):
        filetypes = [("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.webm")]
        file_selected = filedialog.askopenfilename(title='Chọn video', filetypes=filetypes)
        if file_selected:
            self.selected_video.set(file_selected)

    def choose_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.output_dir.get())
        if dir_selected:
            self.output_dir.set(dir_selected)

    def safe_log(self, message):
        """Thread-safe logging"""
        self.log_queue.put(('log', message))

    def start_processing(self):
        if not self.selected_video.get():
            self.safe_log('❌ Chưa chọn video')
            return
        
        self.safe_log('🔄 Bắt đầu xử lý remove text...')
        self.process_btn.config(state='disabled')
        
        thread = threading.Thread(target=self.process_video_worker, daemon=True)
        thread.start()

    def process_video_worker(self):
        """Worker xử lý remove text từ video"""
        try:
            video_path = self.selected_video.get()
            output_dir = self.output_dir.get()
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            self.safe_log(f'📹 Đang xử lý: {os.path.basename(video_path)}')
            
            # Mở video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.safe_log('❌ Không thể mở video')
                return
            
            # Lấy thông tin video
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            self.safe_log(f'📊 Video: {width}x{height}, {fps:.1f}FPS, {total_frames} frames')
            
            # Tạo video writer
            basename = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(output_dir, f'{basename}_text_removed.mp4')
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                self.safe_log('❌ Không thể tạo video output')
                cap.release()
                return
            
            frame_count = 0
            processed_frames = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Xử lý remove text cho frame
                processed_frame = self.remove_text_from_frame(frame)
                
                # Ghi frame đã xử lý
                out.write(processed_frame)
                
                frame_count += 1
                processed_frames += 1
                
                # Update progress
                if frame_count % 30 == 0:  # Update mỗi 30 frames
                    progress = (frame_count / total_frames) * 100
                    self.log_queue.put(('progress', progress))
                    self.safe_log(f'⏳ Đã xử lý: {frame_count}/{total_frames} frames ({progress:.1f}%)')
            
            # Cleanup
            cap.release()
            out.release()
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                file_size = os.path.getsize(output_path) / (1024*1024)
                self.safe_log(f'✅ Hoàn thành! Video đã lưu: {os.path.basename(output_path)} ({file_size:.1f}MB)')
                self.log_queue.put(('status', '✅ Xử lý text hoàn tất!'))
                self.log_queue.put(('progress', 100))
            else:
                self.safe_log('❌ Lỗi tạo video output')
                self.log_queue.put(('status', '❌ Lỗi xử lý!'))
            
        except Exception as e:
            self.safe_log(f'❌ Lỗi xử lý video: {e}')
            self.log_queue.put(('status', '❌ Lỗi xử lý!'))
        finally:
            self.log_queue.put(('enable_button', None))

    def remove_text_from_frame(self, frame):
        """Xử lý remove text từ một frame"""
        try:
            # Tạo mask để detect text
            mask = self.create_text_mask(frame)
            
            # Sử dụng inpainting để remove text
            if np.any(mask):
                result = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
                return result
            else:
                return frame
                
        except Exception as e:
            # Nếu có lỗi, trả về frame gốc
            return frame

    def create_text_mask(self, img):
        """Tạo mask để detect text areas"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Tạo mask tổng hợp
            mask = np.zeros(gray.shape, dtype=np.uint8)
            
            # Method 1: Threshold-based detection
            for thresh in [200, 220, 240]:
                _, thresh_mask = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
                mask = cv2.bitwise_or(mask, thresh_mask)
            
            # Method 2: Adaptive threshold
            adaptive_mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            mask = cv2.bitwise_or(mask, adaptive_mask)
            
            # Method 3: Color-based detection (white and yellow text)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # White text
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 30, 255])
            white_mask = cv2.inRange(hsv, lower_white, upper_white)
            mask = cv2.bitwise_or(mask, white_mask)
            
            # Yellow text
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([30, 255, 255])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            mask = cv2.bitwise_or(mask, yellow_mask)
            
            # Morphological operations để làm sạch mask
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.dilate(mask, kernel, iterations=2)
            
            # Lọc các contour nhỏ
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            filtered_mask = np.zeros_like(mask)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 50:  # Chỉ giữ các vùng đủ lớn
                    cv2.fillPoly(filtered_mask, [contour], 255)
            
            # Blur mask để làm mềm edges
            filtered_mask = cv2.GaussianBlur(filtered_mask, (5, 5), 0)
            
            return filtered_mask
            
        except Exception as e:
            # Nếu có lỗi, trả về mask rỗng
            return np.zeros(img.shape[:2], dtype=np.uint8)

    def start_cut_video(self):
        if not self.selected_video.get() or not self.cut_seconds.get().isdigit():
            self.safe_log('❌ Chọn video và nhập số giây hợp lệ')
            return
        
        self.safe_log('✂️ Bắt đầu cắt video...')
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

    def start_extract_audio(self):
        if not self.selected_video.get():
            self.safe_log('❌ Chưa chọn video')
            return
        
        self.safe_log('🎵 Bắt đầu trích xuất audio...')
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
    print("🚀 Khởi động ứng dụng macOS-safe...")
    
    try:
        app = VideoRemoverApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ Lỗi khởi động: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()