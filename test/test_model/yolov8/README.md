# YOLOv8 (Ultralytics)

## 개요
YOLOv8은 Ultralytics에서 개발한 최신 YOLO 시리즈 모델로, 실시간 객체 탐지에 최적화되어 있습니다.

## 파일
- `adapter.py` - YOLOv8 어댑터 구현
- `config.yaml` - 모델 설정 파일
- `yolov8n.pt` - 사전 학습된 nano 모델 가중치 (6.2MB)

## 특징
- ✅ **가장 빠른 추론 속도**: 3.2ms
- ✅ **경량 모델**: 6.2MB (nano 버전)
- ✅ **실시간 탐지 최적화**
- ✅ **단일 스테이지 탐지기**
- ✅ **COCO 80 클래스 지원**

## 성능
- **mAP50**: 0.529
- **mAP50-95**: 0.373
- **추론 시간**: 3.2ms
- **모델 크기**: 6.2MB

## 의존성
```bash
pip install ultralytics
```

## 사용 예시
```python
from yolov8.adapter import YOLOv8Detector

# 어댑터 초기화
detector = YOLOv8Detector(config_path='yolov8/config.yaml')

# 모델 로드
detector.load_model('yolov8/yolov8n.pt')

# 이미지 탐지
import cv2
image = cv2.imread('image.jpg')
result = detector.detect(image, conf_threshold=0.25, iou_threshold=0.45)

# 결과 출력
for detection in result.detections:
    print(f"{detection.class_name}: {detection.confidence:.2f}")
    print(f"  Box: {detection.bbox}")
```

## 모델 변형
YOLOv8은 다양한 크기의 모델을 제공합니다:

| 모델 | 크기 | mAP50-95 | 속도 |
|------|------|----------|------|
| YOLOv8n | 6.2MB | 0.373 | 3.2ms |
| YOLOv8s | 22MB | 0.445 | 4.5ms |
| YOLOv8m | 52MB | 0.500 | 8.2ms |
| YOLOv8l | 87MB | 0.529 | 12.3ms |
| YOLOv8x | 136MB | 0.541 | 16.8ms |

## 설정
`config.yaml`에서 다음을 설정할 수 있습니다:
- `input_size`: 입력 이미지 크기 (기본: 640x640)
- `conf_threshold`: 신뢰도 임계값 (기본: 0.25)
- `iou_threshold`: IOU 임계값 (기본: 0.45)
- `class_names`: 클래스 이름 목록

## 라이센스
AGPL-3.0
