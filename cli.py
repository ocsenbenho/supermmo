from video_processing import process_video_optimized
from image_processing import process_single_image_chinese
from gui_utils import select_video_file, select_output_directory, reset_processing_settings
import os
import sys
import pytesseract as pt
import tkinter as tk
from tkinter import messagebox
#File này chạy trên terminal
def main():
    print("🎯 SCRUBTITLES OPTIMIZED FIXED - Xóa text triệt để")
    print("🇨🇳 Hỗ trợ đặc biệt cho tiếng Trung")
    print("⚡ Chỉ hỏi cài đặt MỘT LẦN cho mỗi video")
    print("=" * 70)
    try:
        languages = pt.get_languages()
        chinese_langs = [lang for lang in languages if 'chi' in lang.lower()]
        if chinese_langs:
            print(f"✅ Tesseract hỗ trợ tiếng Trung: {chinese_langs}")
        else:
            print("⚠️  Tesseract không hỗ trợ tiếng Trung, chỉ dùng Computer Vision")
    except Exception as e:
        print(f"⚠️  Không thể kiểm tra Tesseract: {e}")
    while True:
        reset_processing_settings()
        print("\n📂 Chọn file cần xử lý...")
        file_path = select_video_file()
        if not file_path:
            print("❌ Không có file nào được chọn")
            break
        print("📁 Chọn thư mục lưu kết quả...")
        output_dir = select_output_directory()
        if not output_dir:
            print("❌ Không có thư mục nào được chọn")
            continue
        file_ext = os.path.splitext(file_path)[1].lower()
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v'}
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'}
        if file_ext in video_exts:
            success = process_video_optimized(file_path, output_dir)
        elif file_ext in image_exts:
            success = process_single_image_chinese(file_path, output_dir)
        else:
            print(f"❌ Định dạng file không được hỗ trợ: {file_ext}")
            continue
        if success:
            print("\n🎊 XỬ LÝ HOÀN TẤT!")
            print("📁 Mở thư mục kết quả...")
            os.system(f'open "{output_dir}"')
        else:
            print("\n💥 Xử lý thất bại!")
        root = tk.Tk()
        root.withdraw()
        if sys.platform == "darwin":
            root.call('wm', 'attributes', '.', '-topmost', True)
        continue_choice = messagebox.askyesno(
            "Tiếp tục?",
            "Bạn có muốn xử lý file khác không?"
        )
        root.destroy()
        if not continue_choice:
            break
    print("\n👋 Cảm ơn bạn đã sử dụng SCRUBTITLES!")

if __name__ == "__main__":
    main() 