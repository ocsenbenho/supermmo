import tkinter as tk
from tkinter import filedialog, ttk
import os
import threading
import queue
from video_processing import process_video_optimized
from image_processing import process_single_image_chinese
import subprocess
import cv2

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'OutputFile')

class VideoRemoverApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('RemoveText - Video Text Remover')
        self.geometry('700x600')
        self.resizable(False, False)
        self.selected_video = tk.StringVar()
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.status = tk.StringVar(value='Chọn file video và thư mục lưu để bắt đầu.')
        self.progress_value = tk.DoubleVar(value=0)
        self.log_queue = queue.Queue()
        self.create_widgets()
        self.after(200, self.update_log_and_progress)

    def create_widgets(self):
        # Chọn file video bất kỳ
        frame_video = tk.Frame(self)
        frame_video.pack(fill='x', padx=20, pady=(20, 0))
        tk.Label(frame_video, text='File video đã chọn:').pack(side='left')
        self.video_entry = tk.Entry(frame_video, textvariable=self.selected_video, width=50, state='readonly')
        self.video_entry.pack(side='left', padx=5)
        tk.Button(frame_video, text='Chọn file video...', command=self.choose_video_file).pack(side='left')
        # Chọn thư mục lưu
        frame = tk.Frame(self)
        frame.pack(fill='x', padx=20, pady=10)
        tk.Label(frame, text='Thư mục lưu kết quả:').pack(side='left')
        self.output_entry = tk.Entry(frame, textvariable=self.output_dir, width=40)
        self.output_entry.pack(side='left', padx=5)
        tk.Button(frame, text='Chọn...', command=self.choose_output_dir).pack(side='left')
        # Khung nhập khoảng cắt video thủ công
        cut_frame = tk.LabelFrame(self, text='Cắt video thành nhiều đoạn nhỏ (thủ công)', padx=5, pady=5)
        cut_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Label(cut_frame, text='Nhập mỗi dòng một khoảng: start-end (vd: 00:00-00:30)').pack(anchor='w')
        self.cut_text = tk.Text(cut_frame, height=3, width=60)
        self.cut_text.pack(side='left', padx=5, pady=5)
        tk.Button(cut_frame, text='Cắt video', command=self.start_cut_video, width=12).pack(side='left', padx=10)
        # Khung nhập số giây tự động cắt
        auto_cut_frame = tk.LabelFrame(self, text='Cắt video tự động theo số giây', padx=5, pady=5)
        auto_cut_frame.pack(fill='x', padx=20, pady=(0, 5))
        tk.Label(auto_cut_frame, text='Số giây mỗi đoạn:').pack(side='left')
        self.auto_cut_seconds = tk.Entry(auto_cut_frame, width=8)
        self.auto_cut_seconds.pack(side='left', padx=5)
        tk.Button(auto_cut_frame, text='Cắt video tự động', command=self.start_auto_cut_video, width=16).pack(side='left', padx=10)
        # Nút xử lý
        self.process_btn = tk.Button(self, text='Xử lý', command=self.start_processing, width=15)
        self.process_btn.pack(pady=5)
        # Progress bar
        self.progress = ttk.Progressbar(self, variable=self.progress_value, maximum=100, length=650)
        self.progress.pack(padx=20, pady=(0, 5))
        # Khung log
        log_frame = tk.LabelFrame(self, text='Log tiến trình', padx=5, pady=5)
        log_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=8, wrap='word', state='normal', bg='#f7f7f7')
        self.log_text.pack(fill='both', expand=True)
        # Trạng thái
        self.status_label = tk.Label(self, textvariable=self.status, fg='blue', wraplength=650, justify='left')
        self.status_label.pack(padx=20, pady=5)

    def choose_video_file(self):
        filetypes = [
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v"),
            ("All files", "*.*")
        ]
        file_selected = filedialog.askopenfilename(title='Chọn file video bất kỳ', filetypes=filetypes)
        if file_selected:
            folder = os.path.dirname(file_selected)
            filename = os.path.basename(file_selected)
            self.input_dir.set(folder)
            self.selected_video.set(file_selected)

    def choose_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.output_dir.get(), title='Chọn thư mục lưu kết quả')
        if dir_selected:
            self.output_dir.set(dir_selected)

    def start_processing(self):
        video_path = self.selected_video.get()
        output_dir = self.output_dir.get()
        if not video_path:
            self.append_log('❌ Chưa chọn video. Vui lòng chọn file video để xử lý.')
            self.status.set('❌ Chưa chọn video. Vui lòng chọn file video để xử lý.')
            return
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.status.set('Đang xử lý video, vui lòng chờ...')
        self.process_btn.config(state='disabled')
        self.progress_value.set(0)
        self.clear_log()
        threading.Thread(target=self.process_video, args=(video_path, output_dir), daemon=True).start()

    def process_video(self, video_path, output_dir):
        ext = os.path.splitext(video_path)[1].lower()
        try:
            if ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v']:
                success = self.process_video_with_progress(video_path, output_dir)
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']:
                success = process_single_image_chinese(video_path, output_dir)
            else:
                self.log_queue.put(('log', f'❌ Định dạng file không được hỗ trợ: {ext}'))
                self.log_queue.put(('status', f'❌ Định dạng file không được hỗ trợ: {ext}'))
                self.process_btn.config(state='normal')
                return
            if success:
                self.log_queue.put(('log', '🎉 Xử lý hoàn tất! Kết quả đã lưu tại: ' + output_dir))
                self.log_queue.put(('status', '🎉 Xử lý hoàn tất! Kết quả đã lưu tại: ' + output_dir))
            else:
                self.log_queue.put(('log', '💥 Xử lý thất bại!'))
                self.log_queue.put(('status', '💥 Xử lý thất bại!'))
        except Exception as e:
            self.log_queue.put(('log', f'❌ Lỗi: {e}'))
            self.log_queue.put(('status', f'❌ Lỗi: {e}'))
        finally:
            self.process_btn.config(state='normal')

    def process_video_with_progress(self, video_path, output_dir):
        def log_callback(msg):
            self.log_queue.put(('log', msg))
        def progress_callback(percent):
            self.log_queue.put(('progress', percent))
        return process_video_optimized(video_path, output_dir, log_callback=log_callback, progress_callback=progress_callback)

    def start_cut_video(self):
        video_path = self.selected_video.get()
        output_dir = self.output_dir.get()
        time_ranges = self.cut_text.get('1.0', 'end').strip().splitlines()
        if not video_path:
            self.append_log('❌ Chưa chọn video. Vui lòng chọn file video để cắt.')
            self.status.set('❌ Chưa chọn video. Vui lòng chọn file video để cắt.')
            return
        if not time_ranges or all(not rng.strip() for rng in time_ranges):
            self.append_log('❌ Chưa nhập khoảng thời gian cắt.')
            self.status.set('❌ Chưa nhập khoảng thời gian cắt.')
            return
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.status.set('Đang cắt video, vui lòng chờ...')
        self.clear_log()
        threading.Thread(target=self.cut_video_thread, args=(video_path, output_dir, time_ranges), daemon=True).start()

    def cut_video_thread(self, video_path, output_dir, time_ranges):
        basename = os.path.splitext(os.path.basename(video_path))[0]
        ext = os.path.splitext(video_path)[1]
        for idx, rng in enumerate(time_ranges):
            rng = rng.strip()
            if not rng:
                continue
            try:
                if '-' not in rng:
                    self.append_log(f'❌ Dòng {idx+1} không đúng định dạng: {rng}')
                    continue
                start, end = [s.strip() for s in rng.split('-', 1)]
                out_file = os.path.join(output_dir, f'{basename}_part{idx+1}{ext}')
                cmd = [
                    'ffmpeg', '-y', '-i', video_path,
                    '-ss', start, '-to', end,
                    '-c', 'copy', out_file
                ]
                self.append_log(f'🔪 Đang cắt: {start} - {end} -> {os.path.basename(out_file)}')
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.append_log(f'✅ Đã lưu: {os.path.basename(out_file)}')
                else:
                    self.append_log(f'❌ Lỗi ffmpeg: {result.stderr}')
            except Exception as e:
                self.append_log(f'❌ Lỗi khi cắt dòng {idx+1}: {e}')
        self.status.set('🎉 Đã hoàn thành cắt video!')

    def start_auto_cut_video(self):
        video_path = self.selected_video.get()
        output_dir = self.output_dir.get()
        seconds = self.auto_cut_seconds.get().strip()
        if not video_path:
            self.append_log('❌ Chưa chọn video. Vui lòng chọn file video để cắt.')
            self.status.set('❌ Chưa chọn video. Vui lòng chọn file video để cắt.')
            return
        if not seconds.isdigit() or int(seconds) <= 0:
            self.append_log('❌ Số giây không hợp lệ. Vui lòng nhập số nguyên dương.')
            self.status.set('❌ Số giây không hợp lệ. Vui lòng nhập số nguyên dương.')
            return
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.status.set('Đang cắt video tự động, vui lòng chờ...')
        self.clear_log()
        threading.Thread(target=self.auto_cut_video_thread, args=(video_path, output_dir, int(seconds)), daemon=True).start()

    def auto_cut_video_thread(self, video_path, output_dir, seconds):
        basename = os.path.splitext(os.path.basename(video_path))[0]
        ext = os.path.splitext(video_path)[1]
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.append_log('❌ Không thể mở video.')
                self.status.set('❌ Không thể mở video.')
                return
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            if duration == 0:
                self.append_log('❌ Không xác định được thời lượng video.')
                self.status.set('❌ Không xác định được thời lượng video.')
                return
            part = 1
            start_sec = 0
            while start_sec < duration:
                end_sec = min(start_sec + seconds, duration)
                start_str = self._sec_to_str(start_sec)
                end_str = self._sec_to_str(end_sec)
                out_file = os.path.join(output_dir, f'{basename}_auto_part{part}{ext}')
                cmd = [
                    'ffmpeg', '-y', '-i', video_path,
                    '-ss', start_str, '-to', end_str,
                    '-c', 'copy', out_file
                ]
                self.append_log(f'🔪 Đang cắt: {start_str} - {end_str} -> {os.path.basename(out_file)}')
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.append_log(f'✅ Đã lưu: {os.path.basename(out_file)}')
                else:
                    self.append_log(f'❌ Lỗi ffmpeg: {result.stderr}')
                part += 1
                start_sec += seconds
            self.status.set('🎉 Đã hoàn thành cắt video tự động!')
        except Exception as e:
            self.append_log(f'❌ Lỗi khi cắt tự động: {e}')
            self.status.set(f'❌ Lỗi khi cắt tự động: {e}')

    def _sec_to_str(self, sec):
        m = int(sec // 60)
        s = int(sec % 60)
        return f'{m:02d}:{s:02d}'

    def update_log_and_progress(self):
        try:
            while True:
                kind, value = self.log_queue.get_nowait()
                if kind == 'log':
                    self.append_log(value)
                elif kind == 'progress':
                    self.progress_value.set(value)
                elif kind == 'status':
                    self.status.set(value)
        except queue.Empty:
            pass
        self.after(200, self.update_log_and_progress)

    def append_log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='normal')

    def clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='normal')


def main():
    app = VideoRemoverApp()
    app.mainloop()

if __name__ == '__main__':
    main() 