# jumin-masker

휴대폰 촬영본 또는 스캔본 이미지에서 주민등록번호를 자동으로 탐지하고 블러 처리하는 파이썬 기반 툴입니다.

## 구성

- `masker/ocr.py`: OpenCV 전처리 + Tesseract OCR 래퍼
- `masker/mask.py`: Bounding box 마스킹 유틸
- `masker/pipeline.py`: 전체 플로우 관리
- `mask_image.py`: CLI 엔트리 포인트
- `app.py`: 웹 서비스 (FastAPI)

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> macOS 기준 Tesseract 엔진은 `brew install tesseract` 로 설치하세요.

## 사용법

### CLI 사용

```bash
python mask_image.py input.jpg output.jpg
```

### 웹 서비스 (로컬)

```bash
python app.py
# 또는
python run_server.py
```

브라우저에서 `http://localhost:8000` 접속

## Render 배포

### 1. GitHub에 코드 푸시

```bash
git add .
git commit -m "Render 배포 준비"
git push origin main
```

### 2. Render 대시보드에서 배포

1. [Render](https://render.com)에 가입/로그인
2. "New +" → "Web Service" 선택
3. GitHub 저장소 연결
4. `render.yaml` 파일이 있으면 자동으로 Dockerfile을 사용하여 설정이 적용됩니다.

또는 수동으로 설정:
   - **Name**: jumin-masker (또는 원하는 이름)
   - **Dockerfile Path**: `Dockerfile`
   - **Plan**: Starter (무료 플랜)

> **참고**: Render의 Python buildpack은 시스템 패키지 설치를 지원하지 않으므로, Tesseract OCR 설치를 위해 Dockerfile을 사용합니다.

### 3. 배포 완료

배포가 완료되면 Render가 제공하는 URL로 접속할 수 있습니다 (예: `https://jumin-masker.onrender.com`)

## 기능

- 주민번호 패턴(`\d{6}-\d{7}`) 자동 탐지
- OCR 오류 보정 (B→5, O→0 등)
- 가우시안 블러를 통한 마스킹
- 웹 인터페이스 제공
- REST API 제공
