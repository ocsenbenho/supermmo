import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
from video_processing import remove_music_from_video

def run_remove_music(input_path, output_path, keep_vocals, log_callback):
    try:
        log_callback(f'🔄 Đang xử lý: {input_path}')
        result = remove_music_from_video(input_path, output_path, keep_vocals)
        log_callback(f'✅ Đã lưu file: {result}')
    except Exception as e:
        log_callback(f'❌ Lỗi: {e}')

class RemoveMusicApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Remove Music from Video')
        self.geometry('500x300')
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.keep_vocals = tk.BooleanVar(value=True)
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text='Chọn file video:').pack(pady=5)
        frame1 = tk.Frame(self)
        frame1.pack(fill='x', padx=10)
        tk.Entry(frame1, textvariable=self.input_path, width=40).pack(side='left', padx=5)
        tk.Button(frame1, text='Chọn...', command=self.choose_input).pack(side='left')

        tk.Label(self, text='Chọn file lưu kết quả:').pack(pady=5)
        frame2 = tk.Frame(self)
        frame2.pack(fill='x', padx=10)
        tk.Entry(frame2, textvariable=self.output_path, width=40).pack(side='left', padx=5)
        tk.Button(frame2, text='Chọn...', command=self.choose_output).pack(side='left')

        tk.Checkbutton(self, text='Chỉ giữ lại giọng nói (vocal)', variable=self.keep_vocals).pack(pady=5)
        tk.Button(self, text='Remove nhạc nền', command=self.start_remove_music, bg='#4CAF50', fg='white').pack(pady=10)
        self.log_text = tk.Text(self, height=7, state='normal')
        self.log_text.pack(fill='both', padx=10, pady=5)

    def choose_input(self):
        path = filedialog.askopenfilename(title='Chọn file video', filetypes=[('Video files', '*.mp4;*.mkv;*.avi;*.mov'), ('All files', '*.*')])
        if path:
            self.input_path.set(path)
            if not self.output_path.get():
                out = os.path.splitext(path)[0] + '_no_music.mp4'
                self.output_path.set(out)

    def choose_output(self):
        path = filedialog.asksaveasfilename(title='Chọn file lưu', defaultextension='.mp4', filetypes=[('MP4 files', '*.mp4'), ('All files', '*.*')])
        if path:
            self.output_path.set(path)

    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='normal')

    def start_remove_music(self):
        inp = self.input_path.get()
        outp = self.output_path.get()
        keep = self.keep_vocals.get()
        if not inp or not outp:
            messagebox.showerror('Thiếu thông tin', 'Vui lòng chọn file video và file lưu kết quả!')
            return
        self.log('🔄 Bắt đầu xử lý...')
        threading.Thread(target=run_remove_music, args=(inp, outp, keep, self.log), daemon=True).start()

if __name__ == '__main__':
    app = RemoveMusicApp()
    app.mainloop() 