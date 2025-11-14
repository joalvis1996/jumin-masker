# jumin-masker

휴대폰 촬영본 또는 스캔본 이미지에서 주민등록번호를 자동으로 탐지하고 블러 처리하는 파이썬 기반 툴입니다.

## 구성

- `masker/ocr.py`: OpenCV 전처리 + Tesseract OCR 래퍼
- `masker/mask.py`: Bounding box 마스킹 유틸
- `masker/pipeline.py`: 전체 플로우 관리
- `mask_image.py`: CLI 엔트리 포인트

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> macOS 기준 Tesseract 엔진은 `brew install tesseract` 로 설치하세요.

## 사용법

```bash
python mask_image.py input.jpg output.jpg
```

현재는 주민번호 패턴(`\d{6}-\d{7}`)만을 대상으로 하며, 추후 패턴/후처리를 확장할 예정입니다.
