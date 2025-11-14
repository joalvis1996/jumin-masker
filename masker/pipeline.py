"""
마스킹 파이프라인 정의.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from PIL import Image

from .ocr import TextBox, extract_text_boxes, load_image, preprocess_for_ocr
from .mask import expand_boxes, mask_regions

RESIDENT_ID_PATTERN = re.compile(r"\d{6}[-\s]?\d{7}")
NUMERIC_ONLY_PATTERN = re.compile(r"\d{13}")
LINE_Y_TOLERANCE = 20
LOGGER = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """
    주민번호 탐지 결과.
    """

    matched_text: str
    bounding_boxes: List[tuple[int, int, int, int]]


def merge_boxes(box_list: Sequence[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    x1 = min(b[0] for b in box_list)
    y1 = min(b[1] for b in box_list)
    x2 = max(b[2] for b in box_list)
    y2 = max(b[3] for b in box_list)
    return (x1, y1, x2, y2)


def same_line(box_a: TextBox, box_b: TextBox, tolerance: int = LINE_Y_TOLERANCE) -> bool:
    ay = (box_a.bounding_box[1] + box_a.bounding_box[3]) / 2
    by = (box_b.bounding_box[1] + box_b.bounding_box[3]) / 2
    return abs(ay - by) <= tolerance


def find_resident_id_boxes(boxes: Iterable[TextBox]) -> List[DetectionResult]:
    """
    OCR 박스에서 주민번호 패턴과 매칭되는 영역을 탐지.
    """
    matches: List[DetectionResult] = []
    box_list = list(boxes)
    for box in box_list:
        text = box.text.strip()
        normalized_digits = re.sub(r"\D", "", text)

        if RESIDENT_ID_PATTERN.fullmatch(text):
            LOGGER.debug("정규식 직접 매칭: %s", text)
            matches.append(DetectionResult(matched_text=text, bounding_boxes=[box.bounding_box]))
            continue

        if NUMERIC_ONLY_PATTERN.fullmatch(normalized_digits):
            LOGGER.debug("숫자만 13자리 매칭: raw='%s', normalized='%s'", text, normalized_digits)
            matches.append(
                DetectionResult(
                    matched_text=f"{normalized_digits[:6]}-{normalized_digits[6:]}",
                    bounding_boxes=[box.bounding_box],
                )
            )

    # 연속된 박스(예: 6자리 + 7자리)를 묶어서 주민번호를 구성
    sorted_boxes = sorted(box_list, key=lambda b: (b.bounding_box[1], b.bounding_box[0]))
    for i in range(len(sorted_boxes) - 1):
        first = sorted_boxes[i]
        second = sorted_boxes[i + 1]
        if not same_line(first, second):
            continue

        first_digits = re.sub(r"\D", "", first.text)
        second_digits = re.sub(r"\D", "", second.text)

        if len(first_digits) == 6 and len(second_digits) == 7:
            merged_box = merge_boxes((first.bounding_box, second.bounding_box))
            matched_text = f"{first_digits}-{second_digits}"
            LOGGER.debug(
                "연속 박스 매칭: '%s' + '%s' -> %s",
                first.text,
                second.text,
                matched_text,
            )
            matches.append(
                DetectionResult(
                    matched_text=matched_text,
                    bounding_boxes=[merged_box],
                )
            )

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

