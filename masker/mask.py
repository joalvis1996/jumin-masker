"""
마스킹(블러) 관련 함수.
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import cv2  # type: ignore
import numpy as np
from PIL import Image

BoundingBox = Tuple[int, int, int, int]


def pil_to_bgr(pil_image: Image.Image) -> np.ndarray:
    """Pillow 이미지를 OpenCV BGR ndarray로 변환."""
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def bgr_to_pil(bgr_image: np.ndarray) -> Image.Image:
    """OpenCV BGR ndarray를 Pillow 이미지로 변환."""
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def mask_regions(
    pil_image: Image.Image,
    regions: Iterable[BoundingBox],
    kernel_size: Tuple[int, int] = (51, 51),
) -> Image.Image:
    """
    주어진 영역에 가우시안 블러를 적용해 마스킹된 Pillow 이미지를 반환.
    """
    bgr = pil_to_bgr(pil_image)
    for (x1, y1, x2, y2) in regions:
        roi = bgr[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        roi_blurred = cv2.GaussianBlur(roi, kernel_size, 0)
        bgr[y1:y2, x1:x2] = roi_blurred
    return bgr_to_pil(bgr)


def expand_boxes(
    boxes: Sequence[BoundingBox],
    padding: int = 4,
) -> Tuple[BoundingBox, ...]:
    """
    OCR bounding box 주변에 여유 padding을 주어 반환.
    """
    expanded = []
    for (x1, y1, x2, y2) in boxes:
        expanded.append(
            (
                max(0, x1 - padding),
                max(0, y1 - padding),
                x2 + padding,
                y2 + padding,
            )
        )
    return tuple(expanded)

