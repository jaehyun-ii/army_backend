# Faster R-CNN

## 개요
Faster R-CNN은 2단계 객체 탐지 모델로, Region Proposal Network(RPN)와 ROI Head를 사용하여 높은 정확도를 제공합니다.

## 파일
- `adapter.py` - Faster R-CNN 어댑터 구현
- `config.yaml` - 모델 설정 파일

## 특징
- ✅ **2단계 탐지기** (RPN + ROI Head)
- ✅ **ResNet-50 FPN 백본**
- ✅ **높은 정확도**
- ✅ **torchvision 통합**
- ✅ **COCO 91 클래스 지원**

## 성능
- **mAP50**: 0.583
- **mAP50-95**: 0.373
- **추론 시간**: 40ms
- **모델 크기**: 160MB

## 의존성
```bash
pip install torch torchvision
```

## 사용 예시
```python
from faster_rcnn.adapter import FasterRCNNDetector

# 어댑터 초기화
detector = FasterRCNNDetector(config_path='faster_rcnn/config.yaml')

# 로컬 가중치 사용 (기본값, 즉시 사용 가능)
detector.load_model()  # fasterrcnn_resnet50_fpn_coco.pth 사용

# 또는 torchvision 사전 학습 모델 로드
# detector.load_model('pretrained')

# 또는 커스텀 모델 로드
# detector.load_model('/path/to/model.pth')

# 이미지 탐지
import cv2
image = cv2.imread('image.jpg')
result = detector.detect(image, conf_threshold=0.5)

# 결과 출력
for detection in result.detections:
    print(f"{detection.class_name}: {detection.confidence:.2f}")
```

## 아키텍처
```
Input Image
    ↓
ResNet-50 Backbone
    ↓
Feature Pyramid Network (FPN)
    ↓
Region Proposal Network (RPN)
    ↓
ROI Align
    ↓
ROI Head (Classification + Box Regression)
    ↓
Detections
```

## 장점
1. **높은 정확도**: 2단계 구조로 정밀한 탐지
2. **ROI Pooling**: 정확한 feature extraction
3. **FPN**: 다양한 스케일의 객체 탐지
4. **안정적**: 검증된 아키텍처

## 단점
1. **느린 속도**: 2단계 처리로 인한 지연
2. **큰 모델 크기**: 160MB
3. **복잡한 구조**: 학습 및 튜닝이 어려움

## 모델 변형
| 백본 | mAP50-95 | 속도 |
|------|----------|------|
| ResNet-50 FPN | 0.373 | 40ms |
| MobileNetV3 FPN | 0.329 | 22ms |

## 사용 케이스
- 정확도가 중요한 경우
- 실시간성이 덜 중요한 경우
- 작은 객체 탐지가 필요한 경우

## 라이센스
BSD-3-Clause
