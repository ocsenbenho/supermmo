import cv2
import os
import numpy as np
import time
import sys
import subprocess
from masking import create_advanced_mask
from inpainting import advanced_inpaint
from gui_utils import get_processing_method, RegionSelector
from settings import PROCESSING_MODE, CHINESE_MODE
from parallel_utils import run_parallel_map

def get_video_codec_for_macos():
    codecs_to_try = [
        ('mp4v', '.mp4', 'MPEG-4'),
        ('avc1', '.mp4', 'H.264 AVC'),
        ('MJPG', '.avi', 'Motion JPEG'),
        ('XVID', '.avi', 'Xvid'),
    ]
    return codecs_to_try

def test_video_writer(width, height, fps, output_path, codec):
    try:
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if writer.isOpened():
            test_frame = np.zeros((height, width, 3), dtype=np.uint8)
            writer.write(test_frame)
            writer.release()
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            else:
                if os.path.exists(output_path):
                    os.remove(output_path)
                return False
        else:
            writer.release()
            return False
    except Exception as e:
        print(f"⚠️  Test codec {codec} failed: {e}")
        return False

def _process_single_frame(args):
    # Helper cho multiprocessing: (frame_idx, frame_path, regions, method, height, width, CHINESE_MODE)
    frame_idx, frame_path, regions, method, height, width, chinese_mode = args
    try:
        img = cv2.imread(frame_path)
        if img is None:
            return (frame_idx, False, f"Không thể đọc frame {frame_idx}")
        if method == False:
            mask = create_advanced_mask(img, regions=regions, auto_detect=False)
        else:
            mask = create_advanced_mask(img, regions=None, auto_detect=True)
        cleanedImg = advanced_inpaint(img, mask)
        if cleanedImg.shape[:2] != (height, width):
            cleanedImg = cv2.resize(cleanedImg, (width, height))
        cv2.imwrite(frame_path, cleanedImg, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return (frame_idx, True, None)
    except Exception as e:
        return (frame_idx, False, str(e))

def process_video_optimized(video_path, output_dir, log_callback=None, progress_callback=None):
    global PROCESSING_MODE, CHINESE_MODE
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)
    def update_progress(percent):
        if progress_callback:
            progress_callback(percent)
    log(f"🎬 Đang xử lý: {os.path.basename(video_path)}")
    vid = cv2.VideoCapture(video_path)
    if not vid.isOpened():
        log(f"❌ Không thể mở video: {video_path}")
        return False
    fps = vid.get(cv2.CAP_PROP_FPS)
    width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
    log(f"📊 Video: {width}x{height}, {fps:.2f} FPS, {total_frames} frames")
    if fps <= 0 or width <= 0 or height <= 0 or total_frames <= 0:
        log("❌ Thông tin video không hợp lệ")
        vid.release()
        return False
    if PROCESSING_MODE is None:
        method = get_processing_method()
        if method is None:
            vid.release()
            return False
        PROCESSING_MODE = method
        log(f"✅ Đã chọn phương pháp: {'Tự động' if PROCESSING_MODE else 'Thủ công'}")
        log("🔄 Sẽ áp dụng cho toàn bộ video...")
    else:
        method = PROCESSING_MODE
    regions = []
    if method == False:
        log("👆 Chọn vùng cần xóa từ frame đầu tiên...")
        ret, first_frame = vid.read()
        if not ret:
            log("❌ Không thể đọc frame đầu tiên")
            vid.release()
            return False
        vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
        selector = RegionSelector()
        regions = selector.select_regions(first_frame)
        if not regions:
            log("❌ Không có vùng nào được chọn")
            vid.release()
            return False
        log(f"✅ Đã chọn {len(regions)} vùng để xóa cho TOÀN BỘ VIDEO")
    if CHINESE_MODE:
        log("🇨🇳 Chế độ: TIẾNG TRUNG TỐI ƯU")
    elif CHINESE_MODE == False:
        log("🌐 Chế độ: THÔNG THƯỜNG")
    work_dir = os.path.join(output_dir, 'Temp')
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
        log(f"📁 Tạo thư mục: {work_dir}")
    start_time = time.time()
    # 1. Trích xuất tất cả frame ra file tạm
    frame_paths = []
    frame_counter = 0
    log("🔄 Đang trích xuất các frame...")
    while frame_counter < total_frames:
        ret, img = vid.read()
        if not ret:
            log(f"⚠️  Không thể đọc frame {frame_counter}")
            break
        frame_filename = os.path.join(work_dir, f"frame{frame_counter:06d}.jpg")
        cv2.imwrite(frame_filename, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        frame_paths.append(frame_filename)
        frame_counter += 1
        if progress_callback and total_frames > 0:
            update_progress(frame_counter / total_frames * 10)  # 0-10% cho bước extract
    vid.release()
    if not frame_paths:
        log("❌ Không có frame nào được trích xuất")
        return False
    log(f"✅ Đã trích xuất {len(frame_paths)} frames")
    # 2. Xử lý song song các frame
    log("⚡ Đang xử lý song song các frame...")
    args_list = [
        (idx, path, regions, method, height, width, CHINESE_MODE)
        for idx, path in enumerate(frame_paths)
    ]
    total = len(args_list)
    def progress_wrapper(idx, total):
        if progress_callback:
            update_progress(10 + (idx / total) * 80)  # 10-90% cho xử lý frame
    results = []
    for i, r in enumerate(run_parallel_map(_process_single_frame, args_list, desc="Frame")):
        results.append(r)
        progress_wrapper(i+1, total)
    # Kiểm tra lỗi
    fail_count = sum(1 for r in results if not (isinstance(r, tuple) and r[1]))
    if fail_count > 0:
        log(f"❌ Có {fail_count} frame lỗi khi xử lý!")
    else:
        log(f"✅ Đã xử lý xong tất cả frames!")
    update_progress(90)
    # 3. Gộp lại thành video
    log("🎬 Đang tạo video từ các frames...")
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    codecs_to_try = get_video_codec_for_macos()
    video_writer = None
    output_path = None
    successful_codec = None
    for codec, ext, desc in codecs_to_try:
        test_output = os.path.join(output_dir, f"{video_name}_test{ext}")
        log(f"🧪 Testing codec: {codec} ({desc})")
        if test_video_writer(width, height, fps, test_output, codec):
            log(f"✅ Codec {codec} hoạt động tốt!")
            suffix = "_chinese_optimized" if CHINESE_MODE else "_optimized"
            output_path = os.path.join(output_dir, f"{video_name}{suffix}{ext}")
            successful_codec = codec
            if os.path.exists(test_output):
                os.remove(test_output)
            break
        else:
            log(f"❌ Codec {codec} không hoạt động")
            if os.path.exists(test_output):
                os.remove(test_output)
    if not successful_codec:
        log("❌ Không tìm thấy codec nào hoạt động")
        return False
    try:
        fourcc = cv2.VideoWriter_fourcc(*successful_codec)
        video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not video_writer.isOpened():
            log("❌ Không thể tạo video writer")
            return False
        log(f"📹 Đang ghi video với codec: {successful_codec}")
        for i, frame_path in enumerate(sorted(frame_paths)):
            if i % 30 == 0:
                progress = (i / len(frame_paths)) * 100
                log(f"📹 Ghi video: {progress:.1f}%")
            frame = cv2.imread(frame_path)
            if frame is not None:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                if len(frame.shape) == 3 and frame.shape[2] == 3:
                    video_writer.write(frame)
                else:
                    log(f"⚠️  Frame {i} có format không đúng")
            if progress_callback and len(frame_paths) > 0:
                update_progress(90 + (i / len(frame_paths)) * 10)  # 90-100% cho ghi video
        video_writer.release()
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log(f"✅ Video đã được tạo: {os.path.getsize(output_path)} bytes")
        else:
            log("❌ File video không được tạo hoặc rỗng")
            return False
    except Exception as e:
        log(f"❌ Lỗi tạo video: {e}")
        if video_writer:
            video_writer.release()
        return False
    try:
        import shutil
        shutil.rmtree(work_dir)
        log("🗑️  Đã xóa files tạm")
    except Exception as e:
        log(f"⚠️  Không thể xóa thư mục tạm: {e}")
    processing_time = time.time() - start_time
    log(f"⏱️  Thời gian xử lý: {processing_time:.2f} giây")
    log(f"🎉 Hoàn thành! Video đã lưu tại: {output_path}")
    try:
        test_vid = cv2.VideoCapture(output_path)
        if test_vid.isOpened():
            frame_count = int(test_vid.get(cv2.CAP_PROP_FRAME_COUNT))
            test_vid.release()
            log(f"✅ Video có thể đọc được: {frame_count} frames")
        else:
            log("⚠️  Video có thể không mở được trong một số player")
    except Exception as e:
        log(f"⚠️  Không thể verify video: {e}")
    update_progress(100)
    return True

def convert_video_with_ffmpeg(input_path, output_path):
    try:
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            '-crf', '23',
            '-y',
            output_path
        ]
        print("🔄 Đang convert video bằng ffmpeg...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Convert thành công bằng ffmpeg!")
            return True
        else:
            print(f"❌ Lỗi ffmpeg: {result.stderr}")
            return False
    except FileNotFoundError:
        print("⚠️  Không tìm thấy ffmpeg. Cài đặt: brew install ffmpeg")
        return False
    except Exception as e:
        print(f"❌ Lỗi convert: {e}")
        return False

def remove_music_from_video(input_video, output_video, keep_vocals=True, temp_dir='temp_remove_music'):
    """
    Remove music background from a video using Spleeter.
    input_video: path to input video file
    output_video: path to output video file
    keep_vocals: if True, keep only vocals; if False, mute all audio
    temp_dir: temporary directory for intermediate files
    """
    import shutil
    import ffmpeg
    # 1. Tạo thư mục tạm
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    audio_path = os.path.join(temp_dir, 'audio.wav')
    # 2. Tách audio từ video
    subprocess.run([
        'ffmpeg', '-y', '-i', input_video, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_path
    ], check=True)
    # 3. Dùng spleeter tách nhạc nền
    # Yêu cầu: pip install spleeter
    # Nếu chưa cài: pip install spleeter
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
        # Ghép lại video với vocals
        subprocess.run([
            'ffmpeg', '-y', '-i', input_video, '-i', vocal_path, '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', output_video
        ], check=True)
    else:
        # Mute toàn bộ audio
        subprocess.run([
            'ffmpeg', '-y', '-i', input_video, '-an', output_video
        ], check=True)
    # 6. Xoá thư mục tạm
    shutil.rmtree(temp_dir, ignore_errors=True)
    return output_video

# Hướng dẫn cài đặt Spleeter:
# pip install spleeter
# pip install ffmpeg-python
# Cần cài ffmpeg vào PATH (https://ffmpeg.org/download.html) 