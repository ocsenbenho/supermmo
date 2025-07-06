import numpy as np
import soundfile as sf
import os
import tempfile
import subprocess

def synth_singing_bowl(frequency, t, sample_rate):
    """
    Mô phỏng tiếng singing bowl: tổng hợp nhiều overtone, decay, rung nhẹ.
    """
    overtones = [
        (1.0, 1.0),    # (tỉ lệ tần số, tỉ lệ biên độ)
        (2.01, 0.4),
        (2.74, 0.25),
        (3.99, 0.15),
    ]
    sound = np.zeros_like(t)
    for ratio, amp in overtones:
        decay = np.exp(-t * 1.2)  # decay nhanh dần
        vibrato = 0.995 + 0.005 * np.sin(2 * np.pi * 5 * t)  # rung nhẹ
        sound += amp * np.sin(2 * np.pi * frequency * ratio * t * vibrato) * decay
    return sound

def generate_relax_music(
    output_path,
    frequency=432,
    duration_sec=300,
    sample_rate=44100,
    file_format='wav',
    fade_in_sec=3,
    fade_out_sec=3,
    add_white_noise=False,
    noise_level=0.01,
    sound_type='sine'  # 'sine', 'singing_bowl'
):
    """
    Sinh nhạc thư giãn dạng sóng sine hoặc singing bowl với các tuỳ chọn.
    - output_path: Đường dẫn file xuất ra (không có đuôi sẽ tự thêm)
    - frequency: Tần số (Hz)
    - duration_sec: Thời lượng (giây)
    - sample_rate: Sample rate (Hz)
    - file_format: 'wav' hoặc 'mp3'
    - fade_in_sec, fade_out_sec: Thời gian fade in/out (giây)
    - add_white_noise: Thêm white noise nhẹ nếu True
    - noise_level: Độ lớn white noise (0-1)
    - sound_type: 'sine' (sóng sine thuần), 'singing_bowl' (chuông ngân)
    """
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    if sound_type == 'singing_bowl':
        audio = synth_singing_bowl(frequency, t, sample_rate)
    else:
        audio = np.sin(2 * np.pi * frequency * t)

    # Fade in/out
    fade_in = np.linspace(0, 1, int(sample_rate * fade_in_sec))
    fade_out = np.linspace(1, 0, int(sample_rate * fade_out_sec))
    audio[:len(fade_in)] *= fade_in
    audio[-len(fade_out):] *= fade_out

    # White noise
    if add_white_noise:
        noise = np.random.normal(0, noise_level, audio.shape)
        audio += noise
        audio = np.clip(audio, -1, 1)

    # Normalize
    audio = audio / np.max(np.abs(audio))

    # Đảm bảo output_path có đúng đuôi
    if not output_path.lower().endswith('.' + file_format):
        output_path += '.' + file_format

    if file_format == 'wav':
        sf.write(output_path, audio, sample_rate, subtype='PCM_16')
        return output_path
    elif file_format == 'mp3':
        # Ghi tạm file wav rồi convert sang mp3 bằng ffmpeg nếu có
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
            sf.write(tmp_wav.name, audio, sample_rate, subtype='PCM_16')
            tmp_wav_path = tmp_wav.name
        cmd = [
            'ffmpeg', '-y',
            '-i', tmp_wav_path,
            '-vn',
            '-ar', str(sample_rate),
            '-ac', '2',
            '-b:a', '192k',
            output_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except Exception as e:
            os.remove(tmp_wav_path)
            raise RuntimeError(f'Lỗi convert mp3: {e}')
        os.remove(tmp_wav_path)
        return output_path
    else:
        raise ValueError('Chỉ hỗ trợ wav hoặc mp3') 