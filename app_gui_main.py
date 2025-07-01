import tkinter as tk
from tkinter import filedialog, ttk
import os
import threading
import queue
import platform
from video_processing import process_video_optimized
from image_processing import process_single_image_chinese
from video_cutter import VideoCutter

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'OutputFile')

class VideoRemoverApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('RemoveText - Video Text Remover')
        self.geometry('700x600')
        self.resizable(False, False)
        
        # Detect OS
        self.is_macos = platform.system() == 'Darwin'
        
        self.selected_video = tk.StringVar()
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.status = tk.StringVar(value='Chọn file video và thư mục lưu để bắt đầu.')
        self.progress_value = tk.DoubleVar(value=0)
        self.log_queue = queue.Queue()
        
        self.video_cutter = VideoCutter(log_callback=self.safe_log)
        self.create_widgets()
        self.after(200, self.update_log_and_progress)

    def safe_log(self, message):
        """Thread-safe logging cho tất cả OS"""
        try:
            self.log_queue.put(('log', message))
        except:
            pass

    def safe_progress(self, percent):
        """Thread-safe progress update"""
        try:
            self.log_queue.put(('progress', percent))
        except:
            pass

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

    def start_processing(self):
        if not self.selected_video.get():
            self.append_log('❌ Chưa chọn video')
            return
        
        self.run_in_thread(self.process_video_worker)

    def start_cut_video(self):
        if not self.selected_video.get() or not self.cut_seconds.get().isdigit():
            self.append_log('❌ Chọn video và nhập số giây hợp lệ')
            return
        
        self.run_in_thread(self.cut_video_worker)

    def start_extract_audio(self):
        if not self.selected_video.get():
            self.append_log('❌ Chưa chọn video')
            return
        
        self.run_in_thread(self.extract_audio_worker)

    def run_in_thread(self, target_func):
        """Chạy function trong thread - tương thích cả Windows và macOS"""
        self.clear_log()
        self.process_btn.config(state='disabled')
        self.progress_value.set(0)
        
        thread = threading.Thread(target=target_func, daemon=True)
        thread.start()

    def process_video_worker(self):
        try:
            success = process_video_optimized(
                self.selected_video.get(),
                self.output_dir.get(),
                log_callback=self.safe_log,
                progress_callback=self.safe_progress,
                regions=None,
                method='auto'
            )
            self.log_queue.put(('status', '🎉 Hoàn tất!' if success else '💥 Thất bại!'))
        except Exception as e:
            self.log_queue.put(('log', f'❌ Lỗi: {e}'))
        finally:
            self.log_queue.put(('enable_button', None))

    def cut_video_worker(self):
        try:
            success = self.video_cutter.cut_by_duration(
                self.selected_video.get(),
                self.output_dir.get(),
                int(self.cut_seconds.get())
            )
            self.log_queue.put(('status', '🎉 Cắt xong!' if success else '💥 Thất bại!'))
        except Exception as e:
            self.log_queue.put(('log', f'❌ Lỗi: {e}'))

    def extract_audio_worker(self):
        try:
            success = self.video_cutter.extract_audio(
                self.selected_video.get(),
                self.output_dir.get()
            )
            self.log_queue.put(('status', '🎉 Trích audio xong!' if success else '💥 Thất bại!'))
        except Exception as e:
            self.log_queue.put(('log', f'❌ Lỗi: {e}'))

    def update_log_and_progress(self):
        """Update GUI từ queue - chạy trên main thread"""
        try:
            while True:
                kind, value = self.log_queue.get_nowait()
                if kind == 'log':
                    self.append_log(value)
                elif kind == 'progress':
                    self.progress_value.set(value)
                elif kind == 'status':
                    self.status.set(value)
                elif kind == 'enable_button':
                    self.process_btn.config(state='normal')
        except queue.Empty:
            pass
        
        self.after(200, self.update_log_and_progress)

    def append_log(self, msg):
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')

    def clear_log(self):
        self.log_text.delete('1.0', 'end')


def main():
    app = VideoRemoverApp()
    app.mainloop()

if __name__ == '__main__':
    main()
