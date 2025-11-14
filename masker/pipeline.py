"""
마스킹 파이프라인 정의.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

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


def group_boxes_by_line(
    boxes: Sequence[TextBox],
    tolerance: int = LINE_Y_TOLERANCE,
) -> List[List[TextBox]]:
    groups: List[Tuple[float, List[TextBox]]] = []
    for box in boxes:
        center_y = (box.bounding_box[1] + box.bounding_box[3]) / 2
        for idx, (group_center, group_boxes) in enumerate(groups):
            if abs(center_y - group_center) <= tolerance:
                group_boxes.append(box)
                # update center
                new_center = (group_center * (len(group_boxes) - 1) + center_y) / len(group_boxes)
                groups[idx] = (new_center, group_boxes)
                break
        else:
            groups.append((center_y, [box]))
    return [sorted(group_boxes, key=lambda b: b.bounding_box[0]) for _, group_boxes in groups]


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

    # 연속된 박스(예: 6자리 + 7자리, 혹은 더 많은 조각)를 묶어서 주민번호 구성
    line_groups = group_boxes_by_line(box_list)
    for group in line_groups:
        digits_list = [re.sub(r"\D", "", box.text) for box in group]
        for start in range(len(group)):
            combined_digits = ""
            combined_boxes: List[tuple[int, int, int, int]] = []
            for idx in range(start, len(group)):
                if not digits_list[idx]:
                    if combined_digits:
                        break
                    continue
                combined_digits += digits_list[idx]
                combined_boxes.append(group[idx].bounding_box)
                if len(combined_digits) >= 13:
                    normalized = combined_digits[:13]
                    if not normalized.isdigit():
                        break
                    merged_box = merge_boxes(tuple(combined_boxes))
                    matched_text = f"{normalized[:6]}-{normalized[6:]}"
                    LOGGER.debug(
                        "연속 다중 박스 매칭: boxes=%s -> %s",
                        [box.text for box in group[start : idx + 1]],
                        matched_text,
                    )
                    matches.append(
                        DetectionResult(
                            matched_text=matched_text,
                            bounding_boxes=[merged_box],
                        )
                    )
                    break

    return matches


class MaskingPipeline:
    """
    이미지 로드→전처리→OCR→주민번호 탐지→마스킹까지 수행.
    """

    def __init__(
        self,
        kernel_size: tuple[int, int] = (51, 51),
        padding: int = 6,
        *,
        min_width_for_ocr: int = 1000,
        tesseract_config: str | None = None,
    ) -> None:
        self.kernel_size = kernel_size
        self.padding = padding
        self.min_width_for_ocr = min_width_for_ocr
        self.tesseract_config = tesseract_config or "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789-"

    def process(self, input_path: str) -> Image.Image:
        LOGGER.info("입력 이미지 로드: %s", input_path)
        pil_image = load_image(input_path)
        processed = preprocess_for_ocr(pil_image, min_width=self.min_width_for_ocr)
        LOGGER.debug("전처리 완료 - shape=%s", getattr(processed, "shape", None))

        boxes = extract_text_boxes(processed, config=self.tesseract_config)
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

