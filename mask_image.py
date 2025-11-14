"""
CLI 진입점: python mask_image.py input.jpg output.jpg
"""

from __future__ import annotations

import argparse
import sys

from masker import mask_image as mask_image_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="이미지에서 주민번호를 자동 마스킹합니다.")
    parser.add_argument("input_path", help="입력 이미지 경로")
    parser.add_argument("output_path", help="저장할 출력 이미지 경로")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mask_image_pipeline(args.input_path, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

