import os
import subprocess
import shutil

def remove_music_from_video_smart(input_video, output_video, keep_vocals=True, temp_dir='temp_remove_music'):
    """
    Remove music background from a video using Spleeter.
    input_video: path to input video file
    output_video: path to output video file
    keep_vocals: if True, keep only vocals; if False, mute all audio
    temp_dir: temporary directory for intermediate files
    """
    # 1. Tạo thư mục tạm
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    audio_path = os.path.join(temp_dir, 'audio.wav')
    # 2. Tách audio từ video
    subprocess.run([
        'ffmpeg', '-y', '-i', input_video, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_path
    ], check=True)
    # 3. Dùng spleeter tách nhạc nền
    spleeter_out = os.path.join(temp_dir, 'spleeter_output')
    if not os.path.exists(spleeter_out):
        os.makedirs(spleeter_out)
    subprocess.run([
        'spleeter', 'separate', '-p', 'spleeter:2stems', '-o', spleeter_out, audio_path
    ], check=True)
    # 4. Lấy file vocal (giọng nói)
    base = os.path.splitext(os.path.basename(audio_path))[0]
    vocal_path = os.path.join(spleeter_out, base, 'vocals.wav')
    # 5. Ghép lại video với audio đã remove nhạc nền
    if keep_vocals and os.path.exists(vocal_path):
        subprocess.run([
            'ffmpeg', '-y', '-i', input_video, '-i', vocal_path, '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', output_video
        ], check=True)
    else:
        subprocess.run([
            'ffmpeg', '-y', '-i', input_video, '-an', output_video
        ], check=True)
    shutil.rmtree(temp_dir, ignore_errors=True)
    return output_video

# Hướng dẫn cài đặt Spleeter:
# pip install spleeter
# pip install ffmpeg-python
# Cần cài ffmpeg vào PATH (https://ffmpeg.org/download.html) 