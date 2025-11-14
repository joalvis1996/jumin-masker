"""
마스킹 파이프라인 정의.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Iterable, List

from PIL import Image

from .ocr import TextBox, extract_text_boxes, load_image, preprocess_for_ocr
from .mask import expand_boxes, mask_regions

RESIDENT_ID_PATTERN = re.compile(r"\d{6}-\d{7}")
LOGGER = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """
    주민번호 탐지 결과.
    """

    matched_text: str
    bounding_boxes: List[tuple[int, int, int, int]]


def find_resident_id_boxes(boxes: Iterable[TextBox]) -> List[DetectionResult]:
    """
    OCR 박스에서 주민번호 패턴과 매칭되는 영역을 탐지.
    """
    matches: List[DetectionResult] = []
    for box in boxes:
        if RESIDENT_ID_PATTERN.fullmatch(box.text):
            matches.append(DetectionResult(matched_text=box.text, bounding_boxes=[box.bounding_box]))
    return matches


class MaskingPipeline:
    """
    이미지 로드→전처리→OCR→주민번호 탐지→마스킹까지 수행.
    """

    def __init__(self, kernel_size: tuple[int, int] = (51, 51), padding: int = 6) -> None:
        self.kernel_size = kernel_size
        self.padding = padding

    def process(self, input_path: str) -> Image.Image:
        LOGGER.info("입력 이미지 로드: %s", input_path)
        pil_image = load_image(input_path)
        processed = preprocess_for_ocr(pil_image)
        LOGGER.debug("전처리 완료 - shape=%s", getattr(processed, "shape", None))

        boxes = extract_text_boxes(processed)
        LOGGER.info("OCR 박스 수: %d", len(boxes))
        detections = find_resident_id_boxes(boxes)
        LOGGER.info("주민번호 후보 수: %d", len(detections))

        all_boxes = [bbox for detection in detections for bbox in detection.bounding_boxes]
        expanded = expand_boxes(all_boxes, padding=self.padding)
        LOGGER.debug("마스킹 대상 박스 수: %d", len(expanded))

        if not expanded:
            LOGGER.warning("마스킹 대상이 없습니다. 원본 이미지를 그대로 반환합니다.")

        return mask_regions(pil_image, expanded, kernel_size=self.kernel_size)


def mask_image(input_path: str, output_path: str) -> None:
    pipeline = MaskingPipeline()
    masked = pipeline.process(input_path)
    masked.save(output_path)
    LOGGER.info("출력 이미지 저장: %s", output_path)

