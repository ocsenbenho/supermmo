import os
import subprocess
import json

class VideoCutter:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.ffmpeg_cmd = self._find_ffmpeg()
        
    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
    
    def _find_ffmpeg(self):
        """Tìm ffmpeg command"""
        # Thử system ffmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=3)
            return 'ffmpeg'
        except:
            pass
        
        # Thử local ffmpeg
        local_paths = ['./ffmpeg.exe', './ffmpeg'] if os.name == 'nt' else ['./ffmpeg']
        for path in local_paths:
            if os.path.exists(path):
                return path
        
        return 'ffmpeg'  # fallback
    
    def get_video_duration(self, video_path):
        """Lấy thời lượng video"""
        try:
            cmd = [self.ffmpeg_cmd, '-i', video_path, '-hide_banner']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    duration_str = line.split('Duration:')[1].split(',')[0].strip()
                    time_parts = duration_str.split(':')
                    if len(time_parts) == 3:
                        hours = float(time_parts[0])
                        minutes = float(time_parts[1])
                        seconds = float(time_parts[2])
                        return hours * 3600 + minutes * 60 + seconds
            return 0
        except:
            return 0
    
    def format_time(self, seconds):
        """Chuyển giây thành HH:MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def cut_by_duration(self, video_path, output_dir, segment_seconds):
        """Cắt video theo số giây mỗi đoạn"""
        duration = self.get_video_duration(video_path)
        if duration == 0:
            self.log('❌ Không thể lấy thông tin video')
            return False
        
        basename = os.path.splitext(os.path.basename(video_path))[0]
        ext = os.path.splitext(video_path)[1]
        
        self.log(f'📹 Video: {self.format_time(duration)}, cắt thành đoạn {segment_seconds}s')
        
        part = 1
        start = 0
        success_count = 0
        
        while start < duration:
            end = min(start + segment_seconds, duration)
            output_file = os.path.join(output_dir, f'{basename}_part{part:03d}{ext}')
            
            if self._cut_segment(video_path, output_file, start, end - start):
                success_count += 1
                self.log(f'✅ Đã tạo: {os.path.basename(output_file)}')
            else:
                self.log(f'❌ Lỗi tạo đoạn {part}')
            
            part += 1
            start += segment_seconds
        
        self.log(f'🎉 Hoàn thành! Tạo được {success_count}/{part-1} đoạn')
        return success_count > 0
    
    def cut_by_time_ranges(self, video_path, output_dir, time_ranges):
        """Cắt video theo danh sách thời gian
        time_ranges: [('00:00:10', '00:01:30'), ('00:02:00', '00:03:15'), ...]
        """
        basename = os.path.splitext(os.path.basename(video_path))[0]
        ext = os.path.splitext(video_path)[1]
        success_count = 0
        
        for i, (start_time, end_time) in enumerate(time_ranges, 1):
            output_file = os.path.join(output_dir, f'{basename}_segment{i:03d}{ext}')
            
            if self._cut_by_time(video_path, output_file, start_time, end_time):
                success_count += 1
                self.log(f'✅ Đã tạo: {os.path.basename(output_file)}')
            else:
                self.log(f'❌ Lỗi tạo đoạn {i}: {start_time}-{end_time}')
        
        self.log(f'🎉 Hoàn thành! Tạo được {success_count}/{len(time_ranges)} đoạn')
        return success_count > 0
    
    def _cut_segment(self, input_path, output_path, start_seconds, duration_seconds):
        """Cắt một đoạn video"""
        try:
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-ss', str(start_seconds),
                '-i', input_path,
                '-t', str(duration_seconds),
                '-c', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0 and os.path.exists(output_path)
        except:
            return False
    
    def _cut_by_time(self, input_path, output_path, start_time, end_time):
        """Cắt video theo thời gian HH:MM:SS"""
        try:
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-ss', start_time,
                '-to', end_time,
                '-i', input_path,
                '-c', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0 and os.path.exists(output_path)
        except:
            return False
    
    def extract_audio(self, video_path, output_dir, format='mp3'):
        """Trích xuất audio từ video"""
        basename = os.path.splitext(os.path.basename(video_path))[0]
        output_file = os.path.join(output_dir, f'{basename}.{format}')
        
        try:
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-i', video_path,
                '-vn', '-acodec', 'mp3' if format == 'mp3' else 'copy',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                self.log(f'✅ Đã trích xuất audio: {os.path.basename(output_file)}')
                return True
            else:
                self.log('❌ Lỗi trích xuất audio')
                return False
        except:
            self.log('❌ Exception khi trích xuất audio')
            return False
    
    def check_ffmpeg(self):
        """Kiểm tra ffmpeg có sẵn không"""
        try:
            result = subprocess.run([self.ffmpeg_cmd, '-version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False