# RetinaNet

## 개요
RetinaNet은 Focal Loss를 사용하는 단일 스테이지 객체 탐지 모델로, 클래스 불균형 문제를 해결합니다.

## 파일
- `adapter.py` - RetinaNet 어댑터 구현
- `config.yaml` - 모델 설정 파일

## 특징
- ✅ **Focal Loss 사용**
- ✅ **클래스 불균형 해결**
- ✅ **ResNet-50 FPN 백본**
- ✅ **단일 스테이지 탐지기**
- ✅ **COCO 91 클래스 지원**

## 성능
- **mAP50**: 0.572
- **mAP50-95**: 0.361
- **추론 시간**: 35ms
- **모델 크기**: 145MB

## 의존성
```bash
pip install torch torchvision
```

## 사용 예시
```python
from retinanet.adapter import RetinaNetDetector

# 어댑터 초기화
detector = RetinaNetDetector(config_path='retinanet/config.yaml')

# 로컬 가중치 사용 (기본값, 즉시 사용 가능)
detector.load_model()  # retinanet_resnet50_fpn_coco.pth 사용

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

## Focal Loss
RetinaNet의 핵심 기술인 Focal Loss는 다음과 같이 정의됩니다:

```
FL(pt) = -αt(1 - pt)^γ log(pt)
```

- **α**: 클래스 균형 파라미터
- **γ**: focusing 파라미터 (기본값: 2)
- **pt**: 모델의 예측 확률

이를 통해 쉬운 negative 샘플의 기여도를 줄이고, hard negative에 집중합니다.

## 아키텍처
```
Input Image
    ↓
ResNet-50 Backbone
    ↓
Feature Pyramid Network (FPN)
    ↓
Classification Subnet (4x Conv + Sigmoid)
    ↓
Box Regression Subnet (4x Conv + Linear)
    ↓
Detections
```

## 장점
1. **클래스 불균형 해결**: Focal Loss로 hard example에 집중
2. **단일 스테이지**: Faster R-CNN보다 빠름
3. **높은 정확도**: 단일 스테이지 중 우수한 성능
4. **다양한 스케일**: FPN으로 여러 크기 객체 탐지

## 단점
1. **중간 속도**: YOLO보다 느리고 Faster R-CNN보다 빠름
2. **큰 모델**: 145MB
3. **복잡한 Loss**: Focal Loss 하이퍼파라미터 튜닝 필요

## 사용 케이스
- 클래스 불균형이 심한 데이터셋
- 정확도와 속도의 균형이 필요한 경우
- 작은 객체 탐지

## 하이퍼파라미터
`config.yaml`에서 설정 가능:
- `conf_threshold`: 0.5 (신뢰도 임계값)
- `iou_threshold`: 0.5 (NMS IOU 임계값)
- `nms_threshold`: 0.5 (NMS 임계값)

## 라이센스
BSD-3-Clause
