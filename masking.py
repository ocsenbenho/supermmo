import numpy as np
import cv2
from ocr_utils import setup_tesseract_chinese, detect_chinese_text_ocr, contains_chinese_characters
from settings import CHINESE_MODE
from gui_utils import get_chinese_processing_mode

def create_advanced_mask_original(img, regions=None, auto_detect=True):
    mask = np.zeros(img.shape[:2], np.uint8)
    if regions:
        print("🎯 Xử lý theo vùng đã chọn...")
        for i, region in enumerate(regions):
            x1, y1 = region[0]
            x2, y2 = region[1]
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            region_mask = np.zeros(img.shape[:2], np.uint8)
            region_mask[y1:y2, x1:x2] = 255
            roi = img[y1:y2, x1:x2]
            if roi.size > 0:
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                lower_white = np.array([0, 0, 200])
                upper_white = np.array([180, 30, 255])
                white_mask = cv2.inRange(hsv_roi, lower_white, upper_white)
                lower_yellow = np.array([20, 100, 100])
                upper_yellow = np.array([30, 255, 255])
                yellow_mask = cv2.inRange(hsv_roi, lower_yellow, upper_yellow)
                color_mask = cv2.bitwise_or(white_mask, yellow_mask)
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray_roi, 50, 150)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                morph_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, kernel)
                morph_mask = cv2.dilate(morph_mask, kernel, iterations=2)
                combined_mask = cv2.bitwise_or(morph_mask, edges)
                mask[y1:y2, x1:x2] = combined_mask
                print(f"✅ Xử lý vùng {i+1}: ({x1},{y1}) -> ({x2},{y2})")
    elif auto_detect:
        print("🤖 Tự động phát hiện text nâng cao...")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        masks = []
        for thresh in [220, 240, 250]:
            _, thresh_mask = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
            masks.append(thresh_mask)
        adaptive_mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        masks.append(adaptive_mask)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        masks.append(white_mask)
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([30, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        masks.append(yellow_mask)
        combined = np.zeros_like(gray)
        for m in masks:
            combined = cv2.bitwise_or(combined, m)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.dilate(combined, kernel, iterations=3)
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 100:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                if 0.1 < aspect_ratio < 10:
                    mask[y:y+h, x:x+w] = combined[y:y+h, x:x+w]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.erode(mask, kernel, iterations=1)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    return mask

def create_chinese_optimized_mask(img):
    mask = np.zeros(img.shape[:2], np.uint8)
    print("\ud83c\udde8\ud83c\uddf3 \u0110ang ph\u00e1t hi\u1ec7n text ti\u1ebfng Trung...")
    lang = setup_tesseract_chinese()
    if lang:
        print("\ud83c\udf24 S\u1eed d\u1ee5ng OCR \u0111\u1ec3 ph\u00e1t hi\u1ec7n text...")
        chinese_regions, confidences = detect_chinese_text_ocr(img, lang)
        for i, (x, y, w, h) in enumerate(chinese_regions):
            confidence = confidences[i]
            if confidence > 20:
                mask[y:y+h, x:x+w] = 255
                print(f"\u2705 OCR - V\u00f9ng text: ({x},{y},{w},{h}) - confidence: {confidence}%")
    print("\ud83d\udc41\ufe0f  S\u1eed d\u1ee5ng Computer Vision...")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    visual_masks = []
    for thresh in [180, 200, 220, 240, 250]:
        _, thresh_mask = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        visual_masks.append(thresh_mask)
    adaptive_configs = [
        (cv2.ADAPTIVE_THRESH_MEAN_C, 11, 2),
        (cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 11, 2),
        (cv2.ADAPTIVE_THRESH_MEAN_C, 15, 2),
        (cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 15, 2)
    ]
    for method, block_size, C in adaptive_configs:
        adaptive_mask = cv2.adaptiveThreshold(gray, 255, method, cv2.THRESH_BINARY, block_size, C)
        visual_masks.append(adaptive_mask)
    color_ranges = [
        ([0, 0, 160], [180, 60, 255]),
        ([15, 80, 80], [35, 255, 255]),
        ([0, 100, 100], [10, 255, 255]),
        ([170, 100, 100], [180, 255, 255]),
        ([40, 80, 80], [80, 255, 255]),
        ([100, 80, 80], [130, 255, 255])
    ]
    for lower, upper in color_ranges:
        lower = np.array(lower)
        upper = np.array(upper)
        color_mask = cv2.inRange(hsv, lower, upper)
        visual_masks.append(color_mask)
    edges = cv2.Canny(gray, 30, 100)
    visual_masks.append(edges)
    combined_visual = np.zeros_like(gray)
    for vm in visual_masks:
        combined_visual = cv2.bitwise_or(combined_visual, vm)
    kernels = [
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ]
    for kernel in kernels:
        combined_visual = cv2.morphologyEx(combined_visual, cv2.MORPH_CLOSE, kernel)
        combined_visual = cv2.dilate(combined_visual, kernel, iterations=1)
    contours, _ = cv2.findContours(combined_visual, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 30:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            if 0.1 < aspect_ratio < 15 and w > 5 and h > 5:
                padding = 5
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img.shape[1] - x, w + 2*padding)
                h = min(img.shape[0] - y, h + 2*padding)
                mask[y:y+h, x:x+w] = 255
                print(f"\u2705 CV - V\u00f9ng text: ({x},{y},{w},{h})")
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.dilate(mask, kernel, iterations=2)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    return mask

def create_advanced_mask(img, regions=None, auto_detect=True):
    from settings import CHINESE_MODE
    if CHINESE_MODE is None:
        from gui_utils import get_chinese_processing_mode
        chinese_mode = get_chinese_processing_mode()
        if chinese_mode is None:
            return np.zeros(img.shape[:2], np.uint8)
    else:
        chinese_mode = CHINESE_MODE
    if chinese_mode:
        return create_chinese_optimized_mask(img)
    else:
        return create_advanced_mask_original(img, regions, auto_detect) 