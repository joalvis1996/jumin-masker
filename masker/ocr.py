"""
OCR 및 이미지 전처리 관련 함수 모음.

테스트 이미지 없이도 함수 호출부를 맞춰두기 위해,
입력 및 출력 타입을 명확히 정의해둔다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional

import cv2  # type: ignore
import numpy as np
from PIL import Image
import pytesseract


@dataclass
class TextBox:
    """OCR 결과의 단일 텍스트 박스."""

    text: str
    bounding_box: Tuple[int, int, int, int]
    confidence: float


def load_image(path: str) -> Image.Image:
    """이미지를 Pillow 객체로 로드."""
    return Image.open(path)


def preprocess_for_ocr(
    pil_image: Image.Image,
    *,
    min_width: int = 1000,
) -> np.ndarray:
    """
    OCR 성능 향상을 위한 기본 전처리.

    - 그레이스케일
    - 가우시안 블러를 통한 노이즈 제거
    - Otsu 이진화
    - 저해상도 이미지는 보간을 통해 확대
    - 대비 향상 (CLAHE)
    """
    bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    scale = max(1.0, min_width / float(width))
    if scale > 1.0:
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    
    # CLAHE (Contrast Limited Adaptive Histogram Equalization)로 대비 향상
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # 노이즈 제거를 위한 약한 블러
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # Otsu 이진화
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def extract_text_boxes(
    processed_image: np.ndarray,
    *,
    config: Optional[str] = None,
) -> List[TextBox]:
    """
    Tesseract OCR을 실행해 텍스트와 bounding box 리스트를 반환.

    반환 데이터는 후속 단계에서 주민번호 후보를 찾기 위한 기본 자료다.
    """
    data = pytesseract.image_to_data(
        processed_image,
        output_type=pytesseract.Output.DICT,
        config=config or "",
    )
    boxes: List[TextBox] = []
    n_boxes = len(data["text"])
    for i in range(n_boxes):
        text = data["text"][i].strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        boxes.append(TextBox(text=text, bounding_box=(x, y, x + w, y + h), confidence=conf))
    return boxes

