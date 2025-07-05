import cv2
import numpy as np
from settings import CHINESE_MODE

def advanced_inpaint_original(img, mask):
    result1 = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)
    result2 = cv2.inpaint(img, mask, 5, cv2.INPAINT_NS)
    alpha = 0.7
    result = cv2.addWeighted(result1, alpha, result2, 1-alpha, 0)
    kernel = np.ones((3,3), np.float32) / 9
    result = cv2.filter2D(result, -1, kernel)
    return result

def feather_mask(mask, feather=15):
    # Làm mờ cạnh mask để blend tự nhiên
    mask = mask.astype(np.float32) / 255.0
    mask = cv2.GaussianBlur(mask, (feather|1, feather|1), 0)
    mask = np.clip(mask, 0, 1)
    return mask

def chinese_optimized_inpaint(img, mask):
    # Inpaint đa tỉ lệ
    mask = (mask > 32).astype(np.uint8) * 255
    result1 = cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)
    result2 = cv2.inpaint(img, mask, 7, cv2.INPAINT_NS)
    # Inpaint ở tỉ lệ nhỏ hơn để lấy texture lớn
    small_img = cv2.resize(img, (img.shape[1]//2, img.shape[0]//2))
    small_mask = cv2.resize(mask, (mask.shape[1]//2, mask.shape[0]//2))
    small_result = cv2.inpaint(small_img, small_mask, 3, cv2.INPAINT_TELEA)
    result3 = cv2.resize(small_result, (img.shape[1], img.shape[0]))
    # Kết hợp kết quả
    alpha, beta, gamma = 0.5, 0.3, 0.2
    result = cv2.addWeighted(result1, alpha, result2, beta, 0)
    result = cv2.addWeighted(result, 1-gamma, result3, gamma, 0)
    # Làm mịn vùng mask
    mask_blur = feather_mask(mask, feather=21)
    result_smooth = cv2.edgePreservingFilter(result, flags=1, sigma_s=60, sigma_r=0.4)
    result_smooth = cv2.bilateralFilter(result_smooth, 15, 80, 80)
    # Blend vùng inpaint với ảnh gốc bằng alpha mask mờ cạnh
    img = img.astype(np.float32)
    result_smooth = result_smooth.astype(np.float32)
    mask_blur3 = np.repeat(mask_blur[:, :, None], 3, axis=2)
    blended = img * (1 - mask_blur3) + result_smooth * mask_blur3
    blended = np.clip(blended, 0, 255).astype(np.uint8)
    return blended

def advanced_inpaint(img, mask):
    from settings import CHINESE_MODE
    if CHINESE_MODE:
        return chinese_optimized_inpaint(img, mask)
    else:
        return advanced_inpaint_original(img, mask) 