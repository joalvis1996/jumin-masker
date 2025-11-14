"""
jumin-masker 패키지 초기화 모듈.

현재는 OCR, 마스킹, 파이프라인 구성 요소를 느슨하게 엮은
프로토타입 수준이며, 향후 서비스 환경에 맞춰 확장할 예정이다.
"""

from .pipeline import MaskingPipeline, mask_image

__all__ = ["MaskingPipeline", "mask_image"]

