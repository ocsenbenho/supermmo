import pytesseract as pt
from pytesseract import Output
import numpy as np
import cv2

def setup_tesseract_chinese():
    try:
        languages = pt.get_languages()
        chinese_langs = [lang for lang in languages if 'chi' in lang.lower()]
        print(f"🔤 Ngôn ngữ tiếng Trung có sẵn: {chinese_langs}")
        if 'chi_sim' in languages:
            return 'chi_sim'
        elif 'chi_tra' in languages:
            return 'chi_tra'
        elif any('chi' in lang for lang in languages):
            return [lang for lang in languages if 'chi' in lang][0]
        else:
            print("⚠️  Không tìm thấy ngôn ngữ tiếng Trung, sử dụng Computer Vision")
            return None
    except Exception as e:
        print(f"⚠️  Lỗi kiểm tra ngôn ngữ: {e}")
        return None

def contains_chinese_characters(text):
    chinese_ranges = [
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0x20000, 0x2A6DF),
        (0x3000, 0x303F),
        (0xFF00, 0xFFEF),
    ]
    for char in text:
        char_code = ord(char)
        for start, end in chinese_ranges:
            if start <= char_code <= end:
                return True
    return False

def detect_chinese_text_ocr(img, lang='chi_sim'):
    try:
        if lang is None:
            return [], []
        custom_config = f'--oem 3 --psm 6 -l {lang}'
        data = pt.image_to_data(img, config=custom_config, output_type=Output.DICT)
        chinese_regions = []
        confidences = []
        n_boxes = len(data['level'])
        for i in range(n_boxes):
            confidence = int(data['conf'][i])
            text = data['text'][i].strip()
            if confidence > 25 and text:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                if contains_chinese_characters(text) or len(text) > 0:
                    padding = 8
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    w = min(img.shape[1] - x, w + 2*padding)
                    h = min(img.shape[0] - y, h + 2*padding)
                    chinese_regions.append((x, y, w, h))
                    confidences.append(confidence)
                    print(f"🔍 Phát hiện text: '{text}' (confidence: {confidence}%)")
        return chinese_regions, confidences
    except Exception as e:
        print(f"⚠️  Lỗi OCR: {e}")
        return [], [] 