"""
CLI 진입점: python mask_image.py input.jpg output.jpg
"""

from __future__ import annotations

import argparse
import logging
import sys

from masker import mask_image as mask_image_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="이미지에서 주민번호를 자동 마스킹합니다.")
    parser.add_argument("input_path", help="입력 이미지 경로")
    parser.add_argument("output_path", help="저장할 출력 이미지 경로")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="로깅 레벨을 높입니다. -v=INFO, -vv=DEBUG",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    
    logging.getLogger("pytesseract").setLevel(logging.ERROR)

    logging.getLogger(__name__).info("마스킹 시작")
    mask_image_pipeline(args.input_path, args.output_path)
    logging.getLogger(__name__).info("마스킹 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

