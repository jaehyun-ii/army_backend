# Patch Generation Performance Optimization

## 노트북과 백엔드의 주요 차이점

### 1. ✅ **Device 설정 (가장 중요!) - 수정 완료**

| 구분 | 노트북 | 백엔드 (이전) | 백엔드 (수정 후) |
|------|--------|--------------|-----------------|
| Device | CUDA (GPU) | CPU 강제 사용 | CUDA (GPU) 자동 감지 |
| 속도 | 빠름 | **매우 느림** | 빠름 |
| 성능 차이 | 기준 | **10~50배 느림** | 기준과 동일 |

**수정 내용:**
```python
# Before (line 550)
device_type="cpu",  # ❌ 강제 CPU 사용

# After
device_type = "cuda" if torch.cuda.is_available() else "cpu"  # ✅ GPU 자동 감지
yolo_model.model.to(device_type)
```

### 2. ✅ **Attack Losses - 수정 완료**

| 구분 | 노트북 | 백엔드 (이전) | 백엔드 (수정 후) |
|------|--------|--------------|-----------------|
| Loss Functions | 4개 (total, cls, box, dfl) | 1개 (total만) | 4개 (노트북과 동일) |

**수정 내용:**
```python
# Before
attack_losses=("loss_total",)

# After
attack_losses=("loss_total", "loss_cls", "loss_box", "loss_dfl")
```

### 3. **데이터 로딩 방식 (구조적 차이)**

| 구분 | 노트북 | 백엔드 |
|------|--------|--------|
| 소스 | 파일 시스템 직접 접근 | 데이터베이스 쿼리 |
| 이미지 수 | 10개 (테스트용) | 전체 데이터셋 (최대 100개) |
| 속도 | 빠름 | DB 오버헤드 있음 |

**백엔드 특징:**
- DB에서 각 이미지마다 쿼리 실행
- 어노테이션도 별도 쿼리
- 더 많은 이미지를 처리할 수 있지만 오버헤드 존재

## 성능 예상치

### 50 iterations 기준

| 환경 | 10개 이미지 | 100개 이미지 |
|------|-------------|--------------|
| **노트북 (GPU)** | ~2-3분 | ~20-30분 |
| **백엔드 (CPU)** | ~20-30분 | ~3-5시간 |
| **백엔드 (GPU)** ✅ | ~2-3분 | ~20-30분 |

### 500 iterations 기준 (고품질 패치)

| 환경 | 10개 이미지 | 100개 이미지 |
|------|-------------|--------------|
| **노트북 (GPU)** | ~20-30분 | ~3-4시간 |
| **백엔드 (CPU)** | ~3-5시간 | ~30-50시간 |
| **백엔드 (GPU)** ✅ | ~20-30분 | ~3-4시간 |

## 추가 최적화 방법

### 1. 이미지 수 제한 (API 레벨)

테스트를 위해 이미지 수를 제한할 수 있습니다:

```python
# patch_service.py의 _collect_target_images 수정
target_images = []
MAX_TRAINING_IMAGES = 10  # 최대 10개만 사용

for img_record in images_db:
    if len(target_images) >= MAX_TRAINING_IMAGES:
        break
    # ... 나머지 코드
```

### 2. Iteration 수 조정

| Iterations | 품질 | 속도 | 용도 |
|-----------|------|------|------|
| 50 | 낮음 | 빠름 | 빠른 테스트 |
| 100-200 | 중간 | 보통 | 일반 용도 |
| 500-1000 | 높음 | 느림 | 프로덕션 |

### 3. Patch Size 조정

| Patch Size | 메모리 | 속도 | 효과 |
|-----------|--------|------|------|
| 100x100 | 낮음 | 빠름 | 작은 패치 |
| 150x150 | 중간 | 보통 | 권장 |
| 200x200 | 높음 | 느림 | 큰 패치 |

### 4. Learning Rate 조정

| Learning Rate | 수렴 속도 | 안정성 |
|--------------|-----------|--------|
| 1.0 | 느림 | 높음 |
| 5.0 | 빠름 (권장) | 중간 |
| 10.0+ | 매우 빠름 | 낮음 (불안정) |

## 메모리 관리

### GPU 메모리 부족 시

```python
# 1. 이미지 수 줄이기
MAX_TRAINING_IMAGES = 5

# 2. Batch size는 1 유지 (필수)
batch_size = 1

# 3. Patch size 줄이기
patch_size = 100

# 4. 메모리 정리 추가
import torch
torch.cuda.empty_cache()
```

## 백엔드 재시작

수정 사항을 적용하려면 백엔드를 재시작해야 합니다:

```bash
# 현재 실행 중인 백엔드 종료 (Ctrl+C)
# 또는 프로세스 찾아서 종료
ps aux | grep "python -m app.main"
kill <PID>

# 백엔드 재시작
cd /home/jaehyun/army/army_ai/backend
python -m app.main
```

## GPU 확인

GPU가 사용 가능한지 확인:

```bash
# NVIDIA GPU 확인
nvidia-smi

# PyTorch에서 CUDA 사용 가능 확인
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

## 예상 로그

수정 후 패치 생성 시 다음과 같은 로그가 출력됩니다:

```
2025-11-06 02:30:15 - app.services.patch_service - INFO - Using CUDA for patch generation (faster)
2025-11-06 02:30:15 - app.services.patch_service - INFO - ART estimator loaded: <class 'art.estimators.object_detection.pytorch_yolo.PyTorchYolo'>
2025-11-06 02:30:16 - app.services.patch_service - INFO - 패치 훈련 시작: 50 iterations, learning_rate=5.0
2025-11-06 02:30:16 - app.services.patch_service - INFO - Starting patch generation with 50 iterations...
2025-11-06 02:30:16 - app.services.patch_service - INFO - [ART] Iteration 1/50, loss: 0.8234
...
2025-11-06 02:32:45 - app.services.patch_service - INFO - [ART] Iteration 50/50, loss: 0.2341
2025-11-06 02:32:45 - app.services.patch_service - INFO - Patch generation completed
2025-11-06 02:32:45 - app.services.patch_service - INFO - 패치 생성 완료: shape=(3, 200, 200)
```

**예상 시간:** 50 iterations, 10 images → **약 2-3분** (이전: 20-30분)

## 문제 해결

### GPU를 사용하는데도 느린 경우

1. **이미지 수가 너무 많음**
   - COCO Person 100 데이터셋은 100개의 이미지
   - 테스트 시 10개 정도로 제한 권장

2. **DB 쿼리 오버헤드**
   - 각 이미지와 어노테이션마다 별도 DB 쿼리
   - 배치 쿼리로 최적화 가능 (향후 개선)

3. **Iteration 수가 너무 많음**
   - 500 iterations → 50 iterations로 줄여서 테스트

### GPU 메모리 부족 (CUDA out of memory)

```python
# patch_service.py의 _collect_target_images에서
target_images = target_images[:10]  # 최대 10개로 제한
```

또는 테스트 스크립트에서 더 작은 데이터셋 사용

## 벤치마크 결과 (예상)

### 이전 (CPU)
- 50 iterations, 10 images: **~25분**
- 500 iterations, 10 images: **~4시간**

### 수정 후 (GPU)
- 50 iterations, 10 images: **~2.5분** (10배 향상)
- 500 iterations, 10 images: **~25분** (10배 향상)

### 노트북 (GPU)
- 50 iterations, 10 images: **~2-3분**
- 500 iterations, 10 images: **~20-30분**

**결론:** 수정 후 백엔드는 노트북과 거의 동일한 성능을 보입니다.
