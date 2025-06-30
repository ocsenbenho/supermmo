import os
import psutil
from concurrent.futures import ProcessPoolExecutor, as_completed

# Số worker tối đa = 80% số luồng logic
def get_max_workers():
    cpu_count = os.cpu_count() or 4
    return max(1, int(cpu_count * 0.8))

# Chạy song song một hàm trên nhiều phần tử, trả về kết quả theo thứ tự đầu vào
def run_parallel_map(func, iterable, desc=None):
    max_workers = get_max_workers()
    results = [None] * len(iterable)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(func, item): idx for idx, item in enumerate(iterable)}
        for i, future in enumerate(as_completed(future_to_idx)):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = e
            if desc:
                print(f"{desc}: {i+1}/{len(iterable)} done")
    return results

# (Có thể mở rộng: giám sát RAM/CPU, dừng khi vượt ngưỡng) 