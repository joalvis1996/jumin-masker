"""
웹 서버 진입점: FastAPI를 사용한 주민번호 마스킹 서비스
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from masker import MaskingPipeline

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logging.getLogger("pytesseract").setLevel(logging.ERROR)

app = FastAPI(title="주민번호 마스킹 서비스", version="1.0.0")

# 파이프라인 인스턴스 (재사용)
pipeline = MaskingPipeline()


@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지"""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>주민번호 마스킹 서비스</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                padding: 40px;
                max-width: 800px;
                width: 100%;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 2em;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 0.9em;
            }
            .upload-area {
                border: 3px dashed #667eea;
                border-radius: 15px;
                padding: 40px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
                background: #f8f9ff;
            }
            .upload-area:hover {
                border-color: #764ba2;
                background: #f0f2ff;
            }
            .upload-area.dragover {
                border-color: #764ba2;
                background: #e8ebff;
            }
            #fileInput {
                display: none;
            }
            .upload-icon {
                font-size: 48px;
                margin-bottom: 20px;
            }
            .upload-text {
                color: #667eea;
                font-size: 1.1em;
                margin-bottom: 10px;
            }
            .upload-hint {
                color: #999;
                font-size: 0.9em;
            }
            .preview-section {
                margin-top: 30px;
                display: none;
            }
            .preview-section.active {
                display: block;
            }
            .preview-container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-top: 20px;
            }
            .preview-box {
                text-align: center;
            }
            .preview-box h3 {
                color: #333;
                margin-bottom: 10px;
                font-size: 1em;
            }
            .preview-image {
                max-width: 100%;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            }
            .button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 15px 40px;
                border-radius: 10px;
                font-size: 1em;
                cursor: pointer;
                margin-top: 20px;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
            .button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            .loading {
                display: none;
                text-align: center;
                margin-top: 20px;
            }
            .loading.active {
                display: block;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .error {
                color: #e74c3c;
                margin-top: 10px;
                padding: 10px;
                background: #fee;
                border-radius: 5px;
                display: none;
            }
            .error.active {
                display: block;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ 주민번호 마스킹 서비스</h1>
            <p class="subtitle">이미지에서 주민번호를 자동으로 찾아 마스킹합니다</p>
            
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📁</div>
                <div class="upload-text">이미지를 드래그하거나 클릭하여 업로드</div>
                <div class="upload-hint">PNG, JPG, JPEG 형식 지원</div>
                <input type="file" id="fileInput" accept="image/*">
            </div>
            
            <div class="error" id="error"></div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p style="margin-top: 10px; color: #666;">이미지 처리 중...</p>
            </div>
            
            <div class="preview-section" id="previewSection">
                <div class="preview-container">
                    <div class="preview-box">
                        <h3>원본 이미지</h3>
                        <img id="originalImage" class="preview-image" alt="원본">
                    </div>
                    <div class="preview-box">
                        <h3>마스킹된 이미지</h3>
                        <img id="maskedImage" class="preview-image" alt="마스킹됨">
                    </div>
                </div>
                <button class="button" id="downloadBtn">다운로드</button>
            </div>
        </div>
        
        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const previewSection = document.getElementById('previewSection');
            const originalImage = document.getElementById('originalImage');
            const maskedImage = document.getElementById('maskedImage');
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');
            const downloadBtn = document.getElementById('downloadBtn');
            
            let maskedImageBlob = null;
            
            // 파일 선택
            uploadArea.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));
            
            // 드래그 앤 드롭
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    handleFile(e.dataTransfer.files[0]);
                }
            });
            
            async function handleFile(file) {
                if (!file || !file.type.startsWith('image/')) {
                    showError('이미지 파일만 업로드 가능합니다.');
                    return;
                }
                
                error.classList.remove('active');
                previewSection.classList.remove('active');
                loading.classList.add('active');
                
                // 원본 이미지 미리보기
                const reader = new FileReader();
                reader.onload = (e) => {
                    originalImage.src = e.target.result;
                };
                reader.readAsDataURL(file);
                
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    
                    const response = await fetch('/mask', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || '처리 중 오류가 발생했습니다.');
                    }
                    
                    maskedImageBlob = await response.blob();
                    maskedImage.src = URL.createObjectURL(maskedImageBlob);
                    
                    previewSection.classList.add('active');
                } catch (err) {
                    showError(err.message);
                } finally {
                    loading.classList.remove('active');
                }
            }
            
            function showError(message) {
                error.textContent = message;
                error.classList.add('active');
            }
            
            downloadBtn.addEventListener('click', () => {
                if (maskedImageBlob) {
                    const url = URL.createObjectURL(maskedImageBlob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'masked_image.png';
                    a.click();
                    URL.revokeObjectURL(url);
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/mask")
async def mask_image_endpoint(file: UploadFile = File(...)):
    """
    이미지를 업로드받아 주민번호를 마스킹한 후 결과를 반환합니다.
    """
    # 파일 타입 검증
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
    
    try:
        # 업로드된 파일을 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_input:
            content = await file.read()
            tmp_input.write(content)
            tmp_input_path = tmp_input.name
        
        # 마스킹 처리
        masked_image = pipeline.process(tmp_input_path)
        
        # 결과를 메모리에 저장
        output_buffer = io.BytesIO()
        masked_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        
        # 임시 파일 삭제
        Path(tmp_input_path).unlink()
        
        # 결과 반환
        return Response(
            content=output_buffer.getvalue(),
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=masked_image.png"}
        )
    
    except Exception as e:
        logging.error(f"이미지 처리 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"이미지 처리 중 오류가 발생했습니다: {str(e)}")


@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "service": "jumin-masker"}


if __name__ == "__main__":
    import os
    import uvicorn
    
    # Render는 PORT 환경 변수를 제공합니다
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
