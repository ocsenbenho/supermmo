import cv2
import os
import numpy as np
from masking import create_advanced_mask
from inpainting import advanced_inpaint
from gui_utils import preview_mask
from settings import CHINESE_MODE

def process_single_image_chinese(image_path, output_dir):
    print(f"🖼️  Đang xử lý ảnh: {os.path.basename(image_path)}")
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Không thể đọc ảnh: {image_path}")
        return False
    mask = create_advanced_mask(img, regions=None, auto_detect=True)
    if not preview_mask(img, mask):
        print("❌ Hủy xử lý")
        return False
    result = advanced_inpaint(img, mask)
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    suffix = "_chinese_optimized" if CHINESE_MODE else "_text_removed"
    output_path = os.path.join(output_dir, f"{image_name}{suffix}.jpg")
    cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"✅ Đã lưu ảnh tại: {output_path}")
    return True 