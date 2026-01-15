#!/bin/bash
# Render 빌드 스크립트: Tesseract OCR 및 시스템 의존성 설치

set -e  # 오류 발생 시 중단

echo "🔧 시스템 의존성 설치 중..."

# 패키지 목록 업데이트
apt-get update

# Tesseract OCR 및 한국어 언어팩 설치
apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-kor \
    libtesseract-dev

# OpenCV 시스템 의존성
apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1

# Python 의존성 설치 (requirements.txt는 Render가 자동으로 처리)
echo "✅ 시스템 의존성 설치 완료"
