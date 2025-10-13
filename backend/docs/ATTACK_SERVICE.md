# Attack Service Implementation

**파일**: `app/services/attack_service.py`
**버전**: 1.0.0
**작성일**: 2025-10-05

## 개요

`attack_service.py`는 적대적 공격 실행을 위한 오케스트레이션 레이어입니다. 다양한 전문 서비스들을 조정하여 통합된 공격 실행 인터페이스를 제공합니다.

---

## 서비스 구조

### 1. **AttackService**
2D/3D 공격 실행 및 메트릭 계산을 담당합니다.

#### 주요 메서드

##### `execute_2d_attack()`
```python
async def execute_2d_attack(
    db: AsyncSession,
    attack_id: UUID,
    target_images: Optional[List[UUID]] = None
) -> Dict[str, Any]:
    """2D 공격 실행 및 이미지 적용"""
```

**기능**:
- 공격 타입 감지 (PATCH or NOISE)
- 타겟 이미지 자동 선택
- 공격 실행 및 결과 반환

**응답 예시**:
```json
{
  "attack_id": "uuid-123",
  "attack_type": "patch",
  "patch_id": "patch-uuid",
  "patch_name": "Person Invisibility Patch",
  "target_class": "person",
  "processed_images": 150,
  "status": "completed",
  "storage_path": "/storage/attack_datasets/uuid-123",
  "message": "Patch attack applied to 150 images"
}
```

##### `calculate_attack_metrics()`
```python
async def calculate_attack_metrics(
    db: AsyncSession,
    attack_id: UUID,
    pre_attack_eval_id: Optional[UUID] = None,
    post_attack_eval_id: Optional[UUID] = None
) -> Dict[str, float]:
    """공격 성공률 및 통계 계산"""
```

**기능**:
- Pre-attack vs Post-attack 평가 비교
- mAP, Precision, Recall 감소율 계산
- 공격 효과성(Attack Effectiveness) 산출

**응답 예시**:
```json
{
  "attack_id": "uuid-123",
  "attack_type": "patch",
  "pre_attack_mAP_50": 0.85,
  "post_attack_mAP_50": 0.42,
  "mAP_50_drop": 0.43,
  "mAP_50_drop_percentage": 50.59,
  "pre_attack_precision": 0.88,
  "post_attack_precision": 0.45,
  "precision_drop": 0.43,
  "pre_attack_recall": 0.82,
  "post_attack_recall": 0.38,
  "recall_drop": 0.44,
  "attack_effectiveness": 0.506,
  "status": "completed"
}
```

##### `get_attack_summary()`
```python
async def get_attack_summary(
    db: AsyncSession,
    attack_id: UUID
) -> Dict[str, Any]:
    """포괄적인 공격 요약 정보"""
```

---

### 2. **InferenceService**
모델 추론 실행 및 배치 처리를 담당합니다.

#### 주요 메서드

##### `run_inference()`
```python
async def run_inference(
    db: AsyncSession,
    model_version_id: UUID,
    image_ids: List[UUID],
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45
) -> List[Dict[str, Any]]:
    """모델 추론 실행"""
```

**기능**:
- CustomModelService 통합
- 자동 모델 로딩
- 이미지별 추론 실행
- 에러 핸들링 및 결과 포맷팅

**응답 예시**:
```json
[
  {
    "image_id": "img-uuid-1",
    "file_name": "person_001.jpg",
    "detections": [
      {
        "class_id": 0,
        "class_name": "person",
        "confidence": 0.95,
        "bbox": {
          "x1": 100,
          "y1": 100,
          "x2": 300,
          "y2": 400
        }
      }
    ],
    "inference_time_ms": 35.2,
    "status": "success"
  }
]
```

##### `batch_inference()`
```python
async def batch_inference(
    db: AsyncSession,
    model_version_id: UUID,
    dataset_id: UUID,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    batch_size: int = 32
) -> Dict[str, Any]:
    """전체 데이터셋에 대한 배치 추론"""
```

**기능**:
- 데이터셋 전체 이미지 추론
- 배치 처리로 성능 최적화
- 통계 요약 제공

**응답 예시**:
```json
{
  "dataset_id": "dataset-uuid",
  "model_version_id": "model-uuid",
  "total_images": 150,
  "successful": 148,
  "failed": 2,
  "total_detections": 342,
  "avg_inference_time_ms": 38.5,
  "results": [...]
}
```

---

### 3. **DatasetService**
데이터셋 관리 및 통계 계산을 담당합니다.

#### 주요 메서드

##### `import_images_batch()`
```python
async def import_images_batch(
    db: AsyncSession,
    dataset_id: UUID,
    image_paths: List[str]
) -> schemas.Dataset2DResponse:
    """대량 이미지 임포트"""
```

##### `get_dataset_statistics()`
```python
async def get_dataset_statistics(
    db: AsyncSession,
    dataset_id: UUID
) -> Dict[str, Any]:
    """데이터셋 통계 계산"""
```

**응답 예시**:
```json
{
  "dataset_id": "dataset-uuid",
  "dataset_name": "COCO Person Training",
  "total_images": 150,
  "total_size_bytes": 524288000,
  "total_size_mb": 500.0,
  "avg_width": 1920.0,
  "avg_height": 1080.0,
  "format_distribution": {
    "image/jpeg": 145,
    "image/png": 5
  },
  "metadata": {...},
  "created_at": "2025-10-05T12:00:00Z",
  "status": "completed"
}
```

##### `get_class_distribution()`
```python
async def get_class_distribution(
    db: AsyncSession,
    dataset_id: UUID
) -> Dict[str, Any]:
    """클래스 분포 통계"""
```

**응답 예시**:
```json
{
  "dataset_id": "dataset-uuid",
  "dataset_name": "COCO Person Training",
  "classes": [
    {
      "class_name": "person",
      "count": 2134,
      "percentage": 65.75,
      "avg_confidence": 0.872
    },
    {
      "class_name": "car",
      "count": 1112,
      "percentage": 34.25,
      "avg_confidence": 0.843
    }
  ],
  "total_classes": 2,
  "source": "statistics_table"
}
```

---

## 사용 예시

### 1. 공격 실행
```python
from app.services.attack_service import attack_service
from uuid import UUID

# 공격 실행
result = await attack_service.execute_2d_attack(
    db=db_session,
    attack_id=UUID("attack-uuid"),
    target_images=None  # None이면 전체 이미지
)

print(f"공격 완료: {result['processed_images']}개 이미지 처리")
```

### 2. 공격 메트릭 계산
```python
# Pre/Post 평가 비교
metrics = await attack_service.calculate_attack_metrics(
    db=db_session,
    attack_id=UUID("attack-uuid"),
    pre_attack_eval_id=UUID("eval-pre-uuid"),
    post_attack_eval_id=UUID("eval-post-uuid")
)

print(f"mAP 감소: {metrics['mAP_50_drop_percentage']:.2f}%")
print(f"공격 효과성: {metrics['attack_effectiveness']:.2%}")
```

### 3. 배치 추론
```python
from app.services.attack_service import inference_service

# 전체 데이터셋 추론
result = await inference_service.batch_inference(
    db=db_session,
    model_version_id=UUID("model-uuid"),
    dataset_id=UUID("dataset-uuid"),
    batch_size=32
)

print(f"성공: {result['successful']}/{result['total_images']}")
print(f"평균 추론 시간: {result['avg_inference_time_ms']:.1f}ms")
```

### 4. 데이터셋 통계
```python
from app.services.attack_service import dataset_service

# 통계 계산
stats = await dataset_service.get_dataset_statistics(
    db=db_session,
    dataset_id=UUID("dataset-uuid")
)

print(f"총 이미지: {stats['total_images']}")
print(f"저장 공간: {stats['total_size_mb']}MB")
print(f"평균 해상도: {stats['avg_width']}x{stats['avg_height']}")

# 클래스 분포
distribution = await dataset_service.get_class_distribution(
    db=db_session,
    dataset_id=UUID("dataset-uuid")
)

for cls in distribution['classes']:
    print(f"{cls['class_name']}: {cls['count']}개 ({cls['percentage']:.1f}%)")
```

---

## 통합 서비스

`attack_service.py`는 다음 전문 서비스들을 통합합니다:

### 의존 서비스
1. **AdversarialPatchService** (`adversarial_patch_service.py`)
   - 패치 생성 및 적용

2. **NoiseAttackService** (`noise_attack_service.py`)
   - 노이즈 기반 공격

3. **CustomModelService** (`custom_model_service.py`)
   - 커스텀 모델 추론

4. **DatasetUploadService** (`dataset_service.py`)
   - 데이터셋 업로드 및 관리

---

## 에러 처리

모든 서비스는 표준 예외를 발생시킵니다:

```python
from app.core.exceptions import NotFoundError, ValidationError

try:
    result = await attack_service.execute_2d_attack(db, attack_id)
except NotFoundError as e:
    print(f"리소스를 찾을 수 없음: {e.resource}")
except ValidationError as e:
    print(f"검증 실패: {e.detail}")
```

---

## 글로벌 인스턴스

편의를 위해 글로벌 인스턴스를 제공합니다:

```python
# app/services/attack_service.py
attack_service = AttackService()
inference_service = InferenceService()
dataset_service = DatasetService()
```

**사용법**:
```python
from app.services.attack_service import (
    attack_service,
    inference_service,
    dataset_service
)
```

---

## 성능 최적화

### 배치 처리
- `batch_inference()`: 32개 이미지 단위 배치 처리
- `import_images_batch()`: 대량 이미지 임포트 최적화

### 캐싱
- 모델 로딩 상태 캐싱
- 데이터셋 메타데이터 활용

### 비동기 처리
- 모든 메서드가 `async/await` 지원
- SQLAlchemy AsyncSession 사용

---

## 개발 이력

- **v1.0.0** (2025-10-05): 초기 구현 완료
  - AttackService: 공격 실행 및 메트릭 계산
  - InferenceService: 모델 추론 및 배치 처리
  - DatasetService: 데이터셋 통계 및 관리

---

## 참고 문서

- [API_BY_SCENARIO.md](./API_BY_SCENARIO.md) - API 엔드포인트 가이드
- [PLUGIN_SYSTEM.md](./PLUGIN_SYSTEM.md) - 플러그인 시스템
- [complete_schema.sql](../../complete_schema.sql) - 데이터베이스 스키마
