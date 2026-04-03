from typing import Tuple

import numpy as np
from PIL import Image


def _safe_bbox(x: int, y: int, w: int, h: int, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
    x1 = max(0, min(x, img_w - 1))
    y1 = max(0, min(y, img_h - 1))
    x2 = max(x1 + 1, min(x + w, img_w))
    y2 = max(y1 + 1, min(y + h, img_h))
    return x1, y1, x2, y2


def crop_regions(image: Image.Image, bbox: dict, expand_ratio: float = 0.25):
    img_arr = np.array(image.convert("RGB"))
    img_h, img_w = img_arr.shape[:2]

    x = int(bbox.get("x", 0))
    y = int(bbox.get("y", 0))
    w = int(bbox.get("width", 1))
    h = int(bbox.get("height", 1))

    x1, y1, x2, y2 = _safe_bbox(x, y, w, h, img_w, img_h)
    crop_main = img_arr[y1:y2, x1:x2]

    ex = int(w * expand_ratio)
    ey = int(h * expand_ratio)
    nx1, ny1, nx2, ny2 = _safe_bbox(x - ex, y - ey, w + 2 * ex, h + 2 * ey, img_w, img_h)
    crop_nearby = img_arr[ny1:ny2, nx1:nx2]

    return crop_main, crop_nearby
