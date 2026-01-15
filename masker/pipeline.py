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

# OCR 오류로 인한 문자 변환 맵 (자주 혼동되는 문자)
# 주민번호 맥락에서 더 자주 나타나는 변환 우선
CHAR_TO_DIGIT = {
    'O': '0', 'o': '0', 'Q': '0', 'D': '0',
    'I': '1', 'l': '1', '|': '1',
    'S': '5', 's': '5',
    'B': '5',  # 주민번호에서는 B가 5로 더 자주 혼동됨 (8보다)
    'G': '6', '6': '6',
    'Z': '2', 'z': '2',
    '8': '8',  # B는 5로, 8은 그대로
}


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


def normalize_ocr_text(text: str) -> str:
    """
    OCR 오류로 인한 문자를 숫자로 변환 시도.
    예: "BO1111" -> "801111" (B->8, O->0)
    """
    result = []
    for char in text:
        if char.isdigit():
            result.append(char)
        elif char in CHAR_TO_DIGIT:
            result.append(CHAR_TO_DIGIT[char])
        elif char in ['-', ' ']:
            result.append(char)
    return ''.join(result)


def find_resident_id_boxes(boxes: Iterable[TextBox]) -> List[DetectionResult]:
    """
    OCR 박스에서 주민번호 패턴과 매칭되는 영역을 탐지.
    """
    matches: List[DetectionResult] = []
    box_list = list(boxes)
    for box in box_list:
        text = box.text.strip()
        
        # 원본 텍스트로 먼저 시도
        if RESIDENT_ID_PATTERN.fullmatch(text):
            LOGGER.debug("정규식 직접 매칭: %s", text)
            matches.append(DetectionResult(matched_text=text, bounding_boxes=[box.bounding_box]))
            continue
        
        # OCR 오류 보정 후 시도
        normalized_text = normalize_ocr_text(text)
        if normalized_text != text:
            if RESIDENT_ID_PATTERN.fullmatch(normalized_text):
                LOGGER.debug("OCR 보정 후 매칭: '%s' -> '%s'", text, normalized_text)
                matches.append(DetectionResult(matched_text=normalized_text, bounding_boxes=[box.bounding_box]))
                continue
        
        normalized_digits = re.sub(r"\D", "", normalized_text)

        if NUMERIC_ONLY_PATTERN.fullmatch(normalized_digits):
            LOGGER.debug("숫자만 13자리 매칭: raw='%s', normalized='%s'", text, normalized_digits)
            matches.append(
                DetectionResult(
                    matched_text=f"{normalized_digits[:6]}-{normalized_digits[6:]}",
                    bounding_boxes=[box.bounding_box],
                )
            )
            continue
        
        # 11-13자리 숫자가 포함된 경우 (OCR 오류로 일부가 문자로 인식됨)
        if 11 <= len(normalized_digits) <= 13 and normalized_digits.isdigit():
            matched_text = f"{normalized_digits[:6]}-{normalized_digits[6:13]}"
            LOGGER.debug("11-13자리 숫자 매칭 (OCR 보정): raw='%s', normalized='%s' -> %s", text, normalized_digits, matched_text)
            matches.append(
                DetectionResult(
                    matched_text=matched_text,
                    bounding_boxes=[box.bounding_box],
                )
            )
            continue
        
        # 7자리 숫자 박스는 주민번호 뒷자리일 가능성이 높음
        if len(normalized_digits) == 7 and normalized_digits.isdigit():
            LOGGER.debug("7자리 숫자 발견 (주민번호 뒷자리 후보): %s", text)

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
                # 13자리 이상이면 검사
                if len(combined_digits) >= 13:
                    normalized = combined_digits[:13]
                    if normalized.isdigit():
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
                    else:
                        # 숫자가 아닌 문자가 포함된 경우 중단
                        break
    
    # 7자리 숫자 박스 근처에 다른 숫자 박스가 있는지 확인 (주민번호 뒷자리 + 앞자리)
    for i, box1 in enumerate(box_list):
        digits1 = re.sub(r"\D", "", box1.text)
        if len(digits1) == 7 and digits1.isdigit():
            # 같은 라인에서 앞쪽 박스 찾기
            box1_y_center = (box1.bounding_box[1] + box1.bounding_box[3]) / 2
            box1_x_start = box1.bounding_box[0]
            
            # box1 왼쪽에 있는 모든 박스들을 거리순으로 정렬
            candidates = []
            for j, box2 in enumerate(box_list):
                if i == j:
                    continue
                box2_y_center = (box2.bounding_box[1] + box2.bounding_box[3]) / 2
                box2_x_end = box2.bounding_box[2]
                # 같은 라인에 있고, box2가 box1보다 왼쪽에 있으면
                if abs(box1_y_center - box2_y_center) <= LINE_Y_TOLERANCE:
                    if box2_x_end < box1_x_start:
                        distance = box1_x_start - box2_x_end
                        digits2 = re.sub(r"\D", "", box2.text)
                        if digits2:  # 숫자가 포함되어 있으면
                            candidates.append((distance, box2, digits2))
            
            # 가장 가까운 박스부터 시도
            candidates.sort(key=lambda x: x[0])
            for distance, box2, digits2 in candidates:
                combined = digits2 + digits1
                # 13자리 이상이면 앞 13자리만 사용
                if len(combined) >= 13:
                    normalized = combined[:13]
                    if normalized.isdigit():
                        merged_box = merge_boxes((box2.bounding_box, box1.bounding_box))
                        matched_text = f"{normalized[:6]}-{normalized[6:]}"
                        LOGGER.debug(
                            "7자리 + 앞자리 매칭: boxes=['%s', '%s'] -> %s (거리=%d)",
                            box2.text, box1.text, matched_text, distance,
                        )
                        matches.append(
                            DetectionResult(
                                matched_text=matched_text,
                                bounding_boxes=[merged_box],
                            )
                        )
                        break
                # 6-12자리면 주민번호일 가능성 (앞자리가 일부만 인식됨)
                elif len(combined) >= 6:
                    # 주민번호 앞자리는 보통 6자리이므로, 6자리 + 7자리 = 13자리가 되어야 함
                    # 하지만 OCR 오류로 일부만 인식될 수 있으므로, 6자리 이상이면 시도
                    if len(digits2) >= 3:  # 최소 3자리는 있어야 함
                        # 박스 영역을 합쳐서 마스킹 (정확한 번호는 모르지만 영역은 알 수 있음)
                        merged_box = merge_boxes((box2.bounding_box, box1.bounding_box))
                        # 추정 주민번호 (앞자리 일부 + 뒷자리)
                        estimated = f"{digits2[:min(6, len(digits2))]}-{digits1}"
                        LOGGER.debug(
                            "7자리 + 앞자리 부분 매칭: boxes=['%s', '%s'] -> %s (거리=%d, 추정)",
                            box2.text, box1.text, estimated, distance,
                        )
                        matches.append(
                            DetectionResult(
                                matched_text=estimated,
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
        self.tesseract_config = tesseract_config or "--oem 3 --psm 11"

    def process(self, input_path: str) -> Image.Image:
        LOGGER.info("입력 이미지 로드: %s", input_path)
        pil_image = load_image(input_path)
        processed, scale = preprocess_for_ocr(pil_image, min_width=self.min_width_for_ocr)
        LOGGER.debug("전처리 완료 - shape=%s, scale=%.2f", getattr(processed, "shape", None), scale)

        boxes = extract_text_boxes(processed, config=self.tesseract_config)
        LOGGER.info("OCR 박스 수: %d", len(boxes))
        if LOGGER.isEnabledFor(logging.DEBUG):
            for box in boxes:
                LOGGER.debug("OCR 박스: text='%s', bbox=%s, conf=%.1f", box.text, box.bounding_box, box.confidence)
        detections = find_resident_id_boxes(boxes)
        LOGGER.info("주민번호 후보 수: %d", len(detections))

        all_boxes = [bbox for detection in detections for bbox in detection.bounding_boxes]
        
        # 스케일된 좌표를 원본 좌표로 변환
        if scale > 1.0:
            all_boxes = [
                (int(x1 / scale), int(y1 / scale), int(x2 / scale), int(y2 / scale))
                for (x1, y1, x2, y2) in all_boxes
            ]
            LOGGER.debug("좌표를 원본 스케일로 변환 (scale=%.2f)", scale)
        
        expanded = expand_boxes(all_boxes, padding=self.padding)
        LOGGER.debug("마스킹 대상 박스 수: %d", len(expanded))
        if LOGGER.isEnabledFor(logging.DEBUG) and expanded:
            for bbox in expanded:
                LOGGER.debug("마스킹 박스: %s", bbox)

        if not expanded:
            LOGGER.warning("마스킹 대상이 없습니다. 원본 이미지를 그대로 반환합니다.")

        return mask_regions(pil_image, expanded, kernel_size=self.kernel_size)


def mask_image(input_path: str, output_path: str) -> None:
    pipeline = MaskingPipeline()
    masked = pipeline.process(input_path)
    masked.save(output_path)
    LOGGER.info("출력 이미지 저장: %s", output_path)

