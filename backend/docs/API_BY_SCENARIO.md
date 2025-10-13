# 프론트엔드 시나리오별 API 정리

**작성일:** 2025-10-05
**버전:** 1.0

이 문서는 5개의 프론트엔드 시나리오에서 사용되는 백엔드 API를 정리한 문서입니다.

---

## 📑 목차

1. [시나리오 1: 2D 적대적 패치 생성](#시나리오-1-2d-적대적-패치-생성)
2. [시나리오 2: 노이즈 공격 데이터셋 생성](#시나리오-2-노이즈-공격-데이터셋-생성)
3. [시나리오 3: 모델 평가 및 비교](#시나리오-3-모델-평가-및-비교)
4. [시나리오 4: 실시간 카메라 탐지](#시나리오-4-실시간-카메라-탐지)
5. [시나리오 5: 실험 관리](#시나리오-5-실험-관리)
6. [공통 API](#공통-api)
7. [API 엔드포인트 전체 목록](#api-엔드포인트-전체-목록)

---

## 시나리오 1: 2D 적대적 패치 생성

### 페이지: `/attacks/adversarial-patch/create`

### 사용 API

#### 1.1 초기 로드

| API | Method | 설명 | 응답 시간 |
|-----|--------|------|-----------|
| `/api/v1/datasets-2d` | GET | 2D 데이터셋 목록 조회 | ~50ms |
| `/api/v1/models` | GET | 모델 목록 조회 | ~30ms |
| `/api/v1/datasets-2d/{dataset_id}/top-classes` | GET | 데이터셋의 상위 클래스 조회 (메타데이터 기반) | ~10ms |

**예시 요청:**
```javascript
// 1. 데이터셋 목록
GET /api/v1/datasets-2d?skip=0&limit=100
Authorization: Bearer {token}

// 2. 모델 목록
GET /api/v1/models?skip=0&limit=100
Authorization: Bearer {token}

// 3. 상위 클래스 조회 (데이터셋 선택 후)
GET /api/v1/datasets-2d/{dataset_id}/top-classes?limit=5
Authorization: Bearer {token}

// 응답 예시
{
  "dataset_id": "abc123",
  "dataset_name": "COCO Person Training Set",
  "total_images": 150,
  "top_classes": [
    {
      "class_name": "person",
      "count": 2134,
      "percentage": 65.75,
      "avg_confidence": 0.872,
      "image_count": 145
    }
  ],
  "source": "metadata",
  "cached": true
}
```

#### 1.2 패치 생성 실행

| API | Method | 설명 | 응답 시간 |
|-----|--------|------|-----------|
| `/api/v1/adversarial-patch/patches/generate` | POST | 적대적 패치 생성 요청 (비동기) | ~100ms (작업 시작) |

**예시 요청:**
```javascript
POST /api/v1/adversarial-patch/patches/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "patch_name": "Person Invisibility Patch v1",
  "source_dataset_id": "abc123",
  "target_model_id": "xyz789",
  "target_class": "person",
  "description": "Patch to make person invisible to YOLO model"
}

// 응답
{
  "patch_id": "patch-uuid-123",
  "status": "queued",
  "estimated_time_seconds": 180,
  "message": "Patch generation started"
}
```

#### 1.3 진행 상태 조회

| API | Method | 설명 | 폴링 간격 |
|-----|--------|------|-----------|
| `/api/v1/adversarial-patch/patches/{patch_id}` | GET | 패치 생성 상태 조회 | 2초마다 |

**예시 요청:**
```javascript
GET /api/v1/adversarial-patch/patches/{patch_id}
Authorization: Bearer {token}

// 응답 (진행 중)
{
  "patch_id": "patch-uuid-123",
  "patch_name": "Person Invisibility Patch v1",
  "status": "training",  // queued, training, completed, failed
  "progress_percentage": 45,
  "current_epoch": 9,
  "total_epochs": 20,
  "elapsed_time_seconds": 135,
  "estimated_remaining_seconds": 165
}

// 응답 (완료)
{
  "patch_id": "patch-uuid-123",
  "status": "completed",
  "progress_percentage": 100,
  "patch_file_url": "/api/v1/adversarial-patch/patches/{patch_id}/download",
  "attack_success_rate": 0.87,
  "total_time_seconds": 180
}
```

#### 1.4 패치 다운로드

| API | Method | 설명 | 응답 타입 |
|-----|--------|------|-----------|
| `/api/v1/adversarial-patch/patches/{patch_id}/download` | GET | 생성된 패치 이미지 다운로드 | image/png |

#### 1.5 공격 데이터셋 생성 (패치 적용)

| API | Method | 설명 | 응답 시간 |
|-----|--------|------|-----------|
| `/api/v1/adversarial-patch/attack-datasets/generate` | POST | 패치를 데이터셋에 적용하여 공격 데이터셋 생성 | ~100ms (작업 시작) |

**예시 요청:**
```javascript
POST /api/v1/adversarial-patch/attack-datasets/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "patch_id": "patch-uuid-123",
  "source_dataset_id": "abc123",
  "scale_factor": 0.3,
  "position": "random",
  "output_name": "COCO Person with Patch Attack"
}

// 응답
{
  "attack_dataset_id": "attack-uuid-456",
  "status": "processing",
  "total_images": 150,
  "processed_images": 0
}
```

---

## 시나리오 2: 노이즈 공격 데이터셋 생성

### 페이지: `/attacks/noise-attack/create`

### 사용 API

#### 2.1 초기 로드

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/datasets-2d` | GET | 2D 데이터셋 목록 조회 |
| `/api/v1/models` | GET | 모델 목록 조회 |

#### 2.2 노이즈 공격 실행

| API | Method | 설명 | 공격 타입 |
|-----|--------|------|-----------|
| `/api/v1/noise-attack/attacks/fgsm` | POST | FGSM 공격 실행 | Fast Gradient Sign Method |
| `/api/v1/noise-attack/attacks/pgd` | POST | PGD 공격 실행 | Projected Gradient Descent |
| `/api/v1/noise-attack/attacks/gaussian` | POST | Gaussian 노이즈 공격 실행 | Random Noise |

**예시 요청 (FGSM):**
```javascript
POST /api/v1/noise-attack/attacks/fgsm
Authorization: Bearer {token}
Content-Type: application/json

{
  "attack_name": "FGSM Attack on COCO Person",
  "source_dataset_id": "abc123",
  "target_model_id": "xyz789",
  "description": "FGSM attack to test model robustness"
}

// 응답
{
  "attack_id": "attack-uuid-789",
  "attack_type": "fgsm",
  "status": "queued",
  "estimated_time_seconds": 120
}
```

**예시 요청 (PGD):**
```javascript
POST /api/v1/noise-attack/attacks/pgd
Authorization: Bearer {token}
Content-Type: application/json

{
  "attack_name": "PGD Attack on COCO Person",
  "source_dataset_id": "abc123",
  "target_model_id": "xyz789",
  "description": "PGD iterative attack"
}
```

**예시 요청 (Gaussian):**
```javascript
POST /api/v1/noise-attack/attacks/gaussian
Authorization: Bearer {token}
Content-Type: application/json

{
  "attack_name": "Gaussian Noise Attack",
  "source_dataset_id": "abc123",
  "description": "Random gaussian noise perturbation"
}
```

#### 2.3 진행 상태 조회

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/noise-attack/attack-datasets/{attack_id}` | GET | 공격 데이터셋 생성 상태 조회 |

**예시 요청:**
```javascript
GET /api/v1/noise-attack/attack-datasets/{attack_id}
Authorization: Bearer {token}

// 응답 (진행 중)
{
  "attack_id": "attack-uuid-789",
  "attack_type": "fgsm",
  "status": "processing",
  "progress_percentage": 67,
  "processed_images": 100,
  "total_images": 150,
  "elapsed_time_seconds": 45
}

// 응답 (완료)
{
  "attack_id": "attack-uuid-789",
  "status": "completed",
  "progress_percentage": 100,
  "output_dataset_id": "dataset-attacked-123",
  "attack_success_rate": 0.92,
  "average_perturbation": 0.05
}
```

#### 2.4 공격 데이터셋 다운로드

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/noise-attack/attack-datasets/{attack_id}/download` | GET | 공격 데이터셋 다운로드 (ZIP) |

---

## 시나리오 3: 모델 평가 및 비교

### 페이지: `/evaluation/run`

### 사용 API

#### 3.1 초기 로드

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/models` | GET | 모델 목록 조회 |
| `/api/v1/datasets-2d` | GET | 2D 데이터셋 목록 조회 |

#### 3.2 평가 실행 (Pre-Attack)

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/evaluation/runs` | POST | 평가 실행 요청 |

**예시 요청:**
```javascript
POST /api/v1/evaluation/runs
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "YOLOv8 Pre-Attack Evaluation",
  "phase": "pre_attack",  // pre_attack or post_attack
  "model_version_id": "model-uuid-123",
  "base_dataset_id": "dataset-uuid-456",
  "params": {}
}

// 응답
{
  "id": "eval-run-uuid-789",
  "name": "YOLOv8 Pre-Attack Evaluation",
  "status": "queued",  // queued, running, completed, failed
  "phase": "pre_attack",
  "created_at": "2025-10-05T12:00:00Z"
}
```

#### 3.3 평가 실행 (Post-Attack)

**예시 요청:**
```javascript
POST /api/v1/evaluation/runs
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "YOLOv8 Post-Attack Evaluation",
  "phase": "post_attack",
  "model_version_id": "model-uuid-123",
  "attack_dataset_id": "attack-dataset-uuid-999",  // 공격 데이터셋
  "params": {}
}
```

#### 3.4 진행 상태 조회

| API | Method | 설명 | 폴링 간격 |
|-----|--------|------|-----------|
| `/api/v1/evaluation/runs/{run_id}` | GET | 평가 진행 상태 조회 | 2초마다 |

**예시 요청:**
```javascript
GET /api/v1/evaluation/runs/{run_id}
Authorization: Bearer {token}

// 응답 (진행 중)
{
  "id": "eval-run-uuid-789",
  "name": "YOLOv8 Pre-Attack Evaluation",
  "status": "running",
  "phase": "pre_attack",
  "progress_percentage": 45,
  "processed_images": 68,
  "total_images": 150
}

// 응답 (완료)
{
  "id": "eval-run-uuid-789",
  "status": "completed",
  "metrics_summary": {
    "mAP_50": 0.85,
    "mAP_50_95": 0.72,
    "precision": 0.88,
    "recall": 0.82,
    "f1_score": 0.85
  },
  "ended_at": "2025-10-05T12:05:30Z"
}
```

#### 3.5 평가 결과 비교

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/evaluation/runs/compare` | POST | Pre vs Post 평가 결과 비교 |

**예시 요청:**
```javascript
POST /api/v1/evaluation/runs/compare
Authorization: Bearer {token}
Content-Type: application/json

{
  "pre_attack_run_id": "eval-run-pre-123",
  "post_attack_run_id": "eval-run-post-456"
}

// 응답
{
  "pre_attack": {
    "run_id": "eval-run-pre-123",
    "mAP_50": 0.85,
    "mAP_50_95": 0.72,
    "precision": 0.88,
    "recall": 0.82
  },
  "post_attack": {
    "run_id": "eval-run-post-456",
    "mAP_50": 0.42,  // ↓ 50% 감소
    "mAP_50_95": 0.31,
    "precision": 0.45,
    "recall": 0.38
  },
  "delta": {
    "mAP_50_drop": -0.43,
    "mAP_50_95_drop": -0.41,
    "precision_drop": -0.43,
    "recall_drop": -0.44,
    "attack_effectiveness": 0.51  // 51% 성능 저하
  }
}
```

#### 3.6 평가 목록 조회

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/evaluation/runs` | GET | 평가 실행 이력 조회 |

**예시 요청:**
```javascript
GET /api/v1/evaluation/runs?model_version_id={model_id}&page=1&page_size=20
Authorization: Bearer {token}

// 응답
{
  "items": [
    {
      "id": "eval-run-uuid-789",
      "name": "YOLOv8 Pre-Attack Evaluation",
      "status": "completed",
      "phase": "pre_attack",
      "created_at": "2025-10-05T12:00:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

---

## 시나리오 4: 실시간 카메라 탐지

### 페이지: `/realtime/camera`

### 사용 API

#### 4.1 초기 로드

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/realtime/cameras` | GET | 등록된 카메라 목록 조회 |
| `/api/v1/realtime/webcam/list` | GET | 사용 가능한 웹캠 목록 조회 |
| `/api/v1/models` | GET | 모델 목록 조회 |

**예시 요청:**
```javascript
// 1. 등록된 카메라 목록
GET /api/v1/realtime/cameras?skip=0&limit=100
Authorization: Bearer {token}

// 응답
[
  {
    "id": "camera-uuid-123",
    "name": "Front Door Camera",
    "stream_uri": "rtsp://192.168.1.100:554/stream",
    "resolution": {"width": 1920, "height": 1080},
    "is_active": true
  }
]

// 2. 웹캠 목록 (로컬 웹캠)
GET /api/v1/realtime/webcam/list
Authorization: Bearer {token}

// 응답
{
  "cameras": [
    {
      "device": "/dev/video0",
      "name": "Integrated Webcam",
      "backend": "V4L2"
    },
    {
      "device": "/dev/video1",
      "name": "USB Camera",
      "backend": "V4L2"
    }
  ],
  "count": 2
}
```

#### 4.2 카메라 정보 조회

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/realtime/webcam/info` | GET | 웹캠 상세 정보 조회 |

**예시 요청:**
```javascript
GET /api/v1/realtime/webcam/info?device=/dev/video0
Authorization: Bearer {token}

// 응답
{
  "device": "/dev/video0",
  "name": "Integrated Webcam",
  "backend": "V4L2",
  "resolutions": [
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 720},
    {"width": 640, "height": 480}
  ],
  "fps_options": [30, 60]
}
```

#### 4.3 탐지 세션 시작

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/realtime/runs` | POST | 실시간 탐지 세션 생성 |
| `/api/v1/realtime/webcam/start/{run_id}` | POST | 웹캠 캡처 및 탐지 시작 |

**예시 요청:**
```javascript
// 1. 세션 생성
POST /api/v1/realtime/runs
Authorization: Bearer {token}
Content-Type: application/json

{
  "camera_id": "camera-uuid-123",
  "model_version_id": "model-uuid-456"
}

// 응답
{
  "id": "run-uuid-789",
  "camera_id": "camera-uuid-123",
  "model_version_id": "model-uuid-456",
  "status": "created",
  "started_at": "2025-10-05T12:00:00Z"
}

// 2. 웹캠 캡처 시작
POST /api/v1/realtime/webcam/start/{run_id}?model_version_id={model_id}&device=/dev/video0
Authorization: Bearer {token}

// 응답
{
  "run_id": "run-uuid-789",
  "status": "running",
  "device": "/dev/video0",
  "message": "Webcam capture and detection started"
}
```

#### 4.4 실시간 프레임 수신 (WebSocket)

| API | Protocol | 설명 | 메시지 타입 |
|-----|----------|------|-------------|
| `/api/v1/realtime/ws/frames` | WebSocket | 실시간 프레임 스트리밍 | Binary (JPEG) |

**예시 코드:**
```javascript
// WebSocket 연결
const ws = new WebSocket('ws://localhost:8000/api/v1/realtime/ws/frames');

ws.onopen = () => {
  // 구독 요청
  ws.send(JSON.stringify({
    action: 'subscribe',
    run_id: 'run-uuid-789'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'subscribed') {
    console.log('Subscribed to frames:', data.run_id);
  } else if (data.frame_id) {
    // 프레임 데이터 수신
    displayFrame(data);
  }
};

// 수신 메시지 예시
{
  "frame_id": "frame-uuid-123",
  "run_id": "run-uuid-789",
  "seq_no": 1234,
  "captured_at": "2025-10-05T12:00:01.234Z",
  "frame_data": "base64_encoded_jpeg_data",
  "metadata": {
    "width": 1920,
    "height": 1080,
    "format": "jpeg"
  }
}
```

#### 4.5 실시간 탐지 결과 수신 (WebSocket)

| API | Protocol | 설명 | 메시지 타입 |
|-----|----------|------|-------------|
| `/api/v1/realtime/ws/detections` | WebSocket | 실시간 탐지 결과 스트리밍 | JSON |

**예시 코드:**
```javascript
// WebSocket 연결
const ws = new WebSocket('ws://localhost:8000/api/v1/realtime/ws/detections');

ws.onopen = () => {
  // 구독 요청 (특정 클래스만 필터링 가능)
  ws.send(JSON.stringify({
    action: 'subscribe',
    run_id: 'run-uuid-789',
    filter_classes: ['person', 'car']  // 선택적
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'subscribed') {
    console.log('Subscribed to detections');
  } else if (data.inference_id) {
    // 탐지 결과 수신
    displayDetections(data);
  }
};

// 수신 메시지 예시
{
  "inference_id": "inference-uuid-456",
  "frame_id": "frame-uuid-123",
  "run_id": "run-uuid-789",
  "timestamp": "2025-10-05T12:00:01.234Z",
  "detections": [
    {
      "class_name": "person",
      "confidence": 0.95,
      "bbox": {
        "x1": 100,
        "y1": 100,
        "x2": 300,
        "y2": 400
      }
    },
    {
      "class_name": "car",
      "confidence": 0.88,
      "bbox": {
        "x1": 500,
        "y1": 200,
        "x2": 800,
        "y2": 500
      }
    }
  ],
  "latency_ms": 45,
  "fps": 30.0
}
```

#### 4.6 통계 조회

| API | Method | 설명 | 폴링 간격 |
|-----|--------|------|-----------|
| `/api/v1/realtime/stats/current` | GET | 현재 시스템 통계 조회 | 1초마다 |

**예시 요청:**
```javascript
GET /api/v1/realtime/stats/current
Authorization: Bearer {token}

// 응답
{
  "timestamp": "2025-10-05T12:00:01Z",
  "cpu": {
    "usage_percent": 45.2,
    "temperature": 68.5
  },
  "gpu": {
    "usage_percent": 78.3,
    "memory_used_mb": 3456,
    "memory_total_mb": 8192,
    "temperature": 72.0
  },
  "memory": {
    "used_mb": 12345,
    "total_mb": 32768,
    "usage_percent": 37.6
  },
  "inference": {
    "fps": 28.5,
    "avg_latency_ms": 35.2,
    "detections_per_second": 12.3
  }
}
```

#### 4.7 탐지 중지

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/realtime/webcam/stop/{run_id}` | POST | 웹캠 캡처 및 탐지 중지 |

**예시 요청:**
```javascript
POST /api/v1/realtime/webcam/stop/{run_id}
Authorization: Bearer {token}

// 응답
{
  "run_id": "run-uuid-789",
  "status": "stopped",
  "total_frames": 8520,
  "total_detections": 1234,
  "duration_seconds": 284,
  "avg_fps": 30.0
}
```

---

## 시나리오 5: 실험 관리

### 페이지: `/experiments`

### 사용 API

#### 5.1 실험 생성

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/experiments` | POST | 새 실험 생성 |

**예시 요청:**
```javascript
POST /api/v1/experiments
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "YOLOv8 Adversarial Robustness Test",
  "description": "Testing YOLOv8 robustness against various adversarial attacks",
  "hypothesis": "YOLOv8n is vulnerable to FGSM attacks on person class",
  "tags": ["yolov8", "fgsm", "person"]
}

// 응답
{
  "id": "experiment-uuid-123",
  "name": "YOLOv8 Adversarial Robustness Test",
  "status": "planning",
  "created_at": "2025-10-05T12:00:00Z"
}
```

#### 5.2 실험 목록 조회

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/experiments` | GET | 실험 목록 조회 |

**예시 요청:**
```javascript
GET /api/v1/experiments?skip=0&limit=20
Authorization: Bearer {token}

// 응답
{
  "items": [
    {
      "id": "experiment-uuid-123",
      "name": "YOLOv8 Adversarial Robustness Test",
      "status": "running",
      "created_at": "2025-10-05T12:00:00Z",
      "eval_run_count": 4
    }
  ],
  "total": 15,
  "page": 1
}
```

#### 5.3 실험 상세 조회

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/experiments/{experiment_id}` | GET | 실험 상세 정보 및 평가 결과 조회 |

**예시 요청:**
```javascript
GET /api/v1/experiments/{experiment_id}
Authorization: Bearer {token}

// 응답
{
  "id": "experiment-uuid-123",
  "name": "YOLOv8 Adversarial Robustness Test",
  "status": "completed",
  "description": "Testing YOLOv8 robustness...",
  "eval_runs": [
    {
      "id": "eval-run-1",
      "name": "Pre-Attack Baseline",
      "phase": "pre_attack",
      "metrics": {
        "mAP_50": 0.85
      }
    },
    {
      "id": "eval-run-2",
      "name": "FGSM Attack",
      "phase": "post_attack",
      "metrics": {
        "mAP_50": 0.42
      }
    }
  ],
  "summary": {
    "total_eval_runs": 4,
    "avg_attack_effectiveness": 0.48
  },
  "created_at": "2025-10-05T12:00:00Z",
  "completed_at": "2025-10-05T13:30:00Z"
}
```

#### 5.4 실험 수정

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/experiments/{experiment_id}` | PUT | 실험 정보 수정 |

#### 5.5 실험 삭제

| API | Method | 설명 |
|-----|--------|------|
| `/api/v1/experiments/{experiment_id}` | DELETE | 실험 삭제 (soft delete) |

---

## 공통 API

### 데이터셋 관리

| API | Method | 설명 | 사용 시나리오 |
|-----|--------|------|--------------|
| `/api/v1/datasets-2d` | GET | 2D 데이터셋 목록 조회 | 1, 2, 3 |
| `/api/v1/datasets-2d/{dataset_id}` | GET | 데이터셋 상세 조회 | 1, 2, 3 |
| `/api/v1/datasets-2d` | POST | 새 데이터셋 생성 | - |
| `/api/v1/datasets-2d/{dataset_id}/images` | GET | 데이터셋 이미지 목록 | 1, 2 |
| `/api/v1/datasets-2d/{dataset_id}/top-classes` | GET | 상위 클래스 조회 | 1, 2 |
| `/api/v1/dataset-service/upload-folder` | POST | 폴더 업로드 | - |

### 모델 관리

| API | Method | 설명 | 사용 시나리오 |
|-----|--------|------|--------------|
| `/api/v1/models` | GET | 모델 목록 조회 | 1, 2, 3, 4 |
| `/api/v1/models/{model_id}` | GET | 모델 상세 조회 | - |
| `/api/v1/custom-models/upload` | POST | 커스텀 모델 업로드 | - |

### 시스템 모니터링

| API | Method | 설명 | 사용 시나리오 |
|-----|--------|------|--------------|
| `/api/v1/system/all` | GET | 전체 시스템 메트릭 조회 | 4 |
| `/api/v1/system/cpu` | GET | CPU 사용률 조회 | 4 |
| `/api/v1/system/gpu` | GET | GPU 사용률 조회 | 4 |
| `/api/v1/system/memory` | GET | 메모리 사용률 조회 | 4 |

---

## API 엔드포인트 전체 목록

### 2D 데이터셋 (Datasets 2D)
```
GET    /api/v1/datasets-2d
POST   /api/v1/datasets-2d
GET    /api/v1/datasets-2d/{dataset_id}
PUT    /api/v1/datasets-2d/{dataset_id}
DELETE /api/v1/datasets-2d/{dataset_id}
GET    /api/v1/datasets-2d/{dataset_id}/images
GET    /api/v1/datasets-2d/{dataset_id}/top-classes
POST   /api/v1/datasets-2d/images
GET    /api/v1/datasets-2d/images/{image_id}
DELETE /api/v1/datasets-2d/images/{image_id}
```

### 3D 데이터셋 (Datasets 3D)
```
GET    /api/v1/datasets-3d
POST   /api/v1/datasets-3d
GET    /api/v1/datasets-3d/{dataset_id}
PUT    /api/v1/datasets-3d/{dataset_id}
DELETE /api/v1/datasets-3d/{dataset_id}
POST   /api/v1/datasets-3d/patches
GET    /api/v1/datasets-3d/patches/{patch_id}
DELETE /api/v1/datasets-3d/patches/{patch_id}
POST   /api/v1/datasets-3d/attacks
GET    /api/v1/datasets-3d/attacks/{attack_id}
DELETE /api/v1/datasets-3d/attacks/{attack_id}
```

### 데이터셋 서비스
```
POST   /api/v1/dataset-service/upload-folder
GET    /api/v1/dataset-service/statistics/{dataset_id}
```

### 모델 관리
```
GET    /api/v1/models
POST   /api/v1/models
GET    /api/v1/models/{model_id}
POST   /api/v1/models/versions
GET    /api/v1/models/versions/{version_id}
POST   /api/v1/models/artifacts
```

### 커스텀 모델
```
POST   /api/v1/custom-models/upload
GET    /api/v1/custom-models/{model_id}
DELETE /api/v1/custom-models/{model_id}
POST   /api/v1/custom-models/{model_id}/load
POST   /api/v1/custom-models/{model_id}/unload
POST   /api/v1/custom-models/{model_id}/predict
```

### 적대적 패치 (Adversarial Patch)
```
POST   /api/v1/adversarial-patch/patches/generate
GET    /api/v1/adversarial-patch/patches
GET    /api/v1/adversarial-patch/patches/{patch_id}
GET    /api/v1/adversarial-patch/patches/{patch_id}/download
DELETE /api/v1/adversarial-patch/patches/{patch_id}
POST   /api/v1/adversarial-patch/attack-datasets/generate
GET    /api/v1/adversarial-patch/attack-datasets
GET    /api/v1/adversarial-patch/attack-datasets/{attack_id}
GET    /api/v1/adversarial-patch/attack-datasets/{attack_id}/download
DELETE /api/v1/adversarial-patch/attack-datasets/{attack_id}
WS     /api/v1/adversarial-patch/ws/patches/{patch_id}/training
```

### 노이즈 공격 (Noise Attack)
```
POST   /api/v1/noise-attack/attacks/fgsm
POST   /api/v1/noise-attack/attacks/pgd
POST   /api/v1/noise-attack/attacks/gaussian
GET    /api/v1/noise-attack/attack-datasets
GET    /api/v1/noise-attack/attack-datasets/{attack_id}
GET    /api/v1/noise-attack/attack-datasets/{attack_id}/download
DELETE /api/v1/noise-attack/attack-datasets/{attack_id}
```

### 플러그인 공격 (Plugin Attack)
```
GET    /api/v1/plugin-attack/plugins
GET    /api/v1/plugin-attack/plugins/{plugin_name}
POST   /api/v1/plugin-attack/execute/{plugin_name}
POST   /api/v1/plugin-attack/batch-execute
```

### 평가 (Evaluation)
```
POST   /api/v1/evaluation/runs
GET    /api/v1/evaluation/runs
GET    /api/v1/evaluation/runs/{run_id}
PATCH  /api/v1/evaluation/runs/{run_id}
DELETE /api/v1/evaluation/runs/{run_id}
POST   /api/v1/evaluation/runs/compare
POST   /api/v1/evaluation/items
GET    /api/v1/evaluation/items/{item_id}
POST   /api/v1/evaluation/items/bulk
```

### 실시간 성능 측정 (Realtime)
```
# 카메라
GET    /api/v1/realtime/cameras
POST   /api/v1/realtime/cameras
GET    /api/v1/realtime/cameras/{camera_id}
PUT    /api/v1/realtime/cameras/{camera_id}
DELETE /api/v1/realtime/cameras/{camera_id}

# 캡처 세션
POST   /api/v1/realtime/runs
GET    /api/v1/realtime/runs
GET    /api/v1/realtime/runs/{run_id}
PUT    /api/v1/realtime/runs/{run_id}
DELETE /api/v1/realtime/runs/{run_id}

# 프레임
POST   /api/v1/realtime/frames
GET    /api/v1/realtime/frames
GET    /api/v1/realtime/frames/{frame_id}
PUT    /api/v1/realtime/frames/{frame_id}
DELETE /api/v1/realtime/frames/{frame_id}

# 추론 결과
POST   /api/v1/realtime/inferences
GET    /api/v1/realtime/inferences
GET    /api/v1/realtime/inferences/{inference_id}
PUT    /api/v1/realtime/inferences/{inference_id}
DELETE /api/v1/realtime/inferences/{inference_id}

# 웹캠
GET    /api/v1/realtime/webcam/list
GET    /api/v1/realtime/webcam/info
POST   /api/v1/realtime/webcam/start/{run_id}
GET    /api/v1/realtime/webcam/stream/{run_id}
GET    /api/v1/realtime/webcam/stream-mjpeg/{run_id}
POST   /api/v1/realtime/webcam/stop/{run_id}

# 통계
GET    /api/v1/realtime/stats/current
GET    /api/v1/realtime/stats/stream

# WebSocket
WS     /api/v1/realtime/ws/frames
WS     /api/v1/realtime/ws/detections
```

### 실험 (Experiments)
```
POST   /api/v1/experiments
GET    /api/v1/experiments
GET    /api/v1/experiments/{experiment_id}
PUT    /api/v1/experiments/{experiment_id}
DELETE /api/v1/experiments/{experiment_id}
```

### 벤치마크 (Benchmarks)
```
POST   /api/v1/benchmarks
GET    /api/v1/benchmarks
GET    /api/v1/benchmarks/{benchmark_id}
DELETE /api/v1/benchmarks/{benchmark_id}
```

### 시스템 메트릭 (System Metrics)
```
GET    /api/v1/system/all
GET    /api/v1/system/cpu
GET    /api/v1/system/gpu
GET    /api/v1/system/memory
GET    /api/v1/system/disk
```

---

## API 응답 형식

### 성공 응답
```json
{
  "id": "resource-uuid",
  "name": "Resource Name",
  "status": "success",
  "data": {
    // 리소스 데이터
  },
  "created_at": "2025-10-05T12:00:00Z"
}
```

### 에러 응답
```json
{
  "detail": "Error message description",
  "status_code": 400
}
```

### 페이지네이션 응답
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

---

## 인증

모든 API 요청은 JWT 토큰을 사용한 Bearer 인증이 필요합니다.

```javascript
headers: {
  'Authorization': `Bearer ${access_token}`,
  'Content-Type': 'application/json'
}
```

---

## 요약

### 시나리오별 주요 API

| 시나리오 | 주요 API | API 개수 |
|----------|----------|----------|
| 1. 패치 생성 | `/adversarial-patch/*` | 8개 |
| 2. 노이즈 공격 | `/noise-attack/*` | 6개 |
| 3. 모델 평가 | `/evaluation/*` | 9개 |
| 4. 실시간 탐지 | `/realtime/*` | 25개 (+ WebSocket 2개) |
| 5. 실험 관리 | `/experiments/*` | 5개 |
| **공통 API** | `datasets, models, system` | 15개 |

### 전체 통계
- **Total Endpoints:** ~100개
- **WebSocket Endpoints:** 3개
- **GET:** ~50개
- **POST:** ~35개
- **PUT/PATCH:** ~8개
- **DELETE:** ~12개

---

**문서 버전:** 1.0
**마지막 업데이트:** 2025-10-05
**작성자:** Backend Team
