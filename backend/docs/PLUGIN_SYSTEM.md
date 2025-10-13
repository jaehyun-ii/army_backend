# Attack Plugin System

공격 기법을 플러그인 형태로 확장 가능하도록 설계된 시스템입니다.

## 개요

세 가지 타입의 공격 플러그인을 지원합니다:

1. **2D 패치 생성 (Patch2DGenerationPlugin)**: 2D 이미지에 적용할 적대적 패치 생성
2. **2D 노이즈 공격 (Noise2DAttackPlugin)**: 2D 이미지에 적대적 노이즈 추가
3. **3D 패치 생성 (Patch3DGenerationPlugin)**: 물리적 변환에 강건한 3D 패치 생성

## 플러그인 구조

### 베이스 클래스

#### 1. Patch2DGenerationPlugin
**위치**: `app/plugins/patch_2d_base.py`

**주요 메서드**:
- `generate_patch()`: 적대적 패치 생성
- `optimize_patch()`: 경사 하강법으로 패치 최적화
- `initialize_patch()`: 패치 초기화 (random, gray, noise)

**설정 파라미터**:
```python
{
    "patch_size": 100,           # 패치 크기 (픽셀)
    "area_ratio": 0.3,          # bbox 대비 패치 면적 비율
    "epsilon": 0.6,             # 섭동 예산
    "alpha": 0.03,              # 학습률
    "iterations": 100,          # 학습 반복 횟수
    "batch_size": 8,            # 배치 크기
    "target_class": "person"    # 타겟 클래스
}
```

#### 2. Noise2DAttackPlugin
**위치**: `app/plugins/noise_2d_base.py`

**하위 클래스**:
- `GradientBasedNoise2DPlugin`: 경사 기반 노이즈 (FGSM, PGD)
- `RandomNoise2DPlugin`: 랜덤 노이즈 (Gaussian, Uniform)

**주요 메서드**:
- `generate_noise()`: 적대적 노이즈 생성
- `apply_noise()`: 이미지에 노이즈 적용
- `compute_noise_stats()`: 노이즈 통계 계산

**설정 파라미터**:
```python
# FGSM/PGD
{
    "epsilon": 8.0,             # 노이즈 강도
    "alpha": 2.0,               # 스텝 크기 (PGD)
    "iterations": 10,           # 반복 횟수 (PGD)
    "targeted": false,          # 타겟 공격 여부
    "model_version_id": "..."   # 모델 ID
}

# Gaussian
{
    "mean": 0.0,                # 평균
    "std": 25.0                 # 표준편차
}

# Uniform
{
    "min_val": -25.0,           # 최소값
    "max_val": 25.0             # 최대값
}
```

#### 3. Patch3DGenerationPlugin
**위치**: `app/plugins/patch_3d_base.py`

**주요 메서드**:
- `generate_patch()`: 3D 강건 패치 생성
- `apply_transformation()`: 3D 변환 적용 (rotation, scale, perspective)
- `optimize_patch_3d()`: EOT(Expectation Over Transformation)로 최적화
- `apply_printability_constraint()`: 인쇄 가능 색상 제약
- `apply_smoothness_regularization()`: 부드러움 정규화

**설정 파라미터**:
```python
{
    "patch_size": [100, 100],           # 패치 크기 [H, W]
    "enable_rotation": true,             # 회전 변환 활성화
    "enable_scale": true,                # 크기 변환 활성화
    "enable_perspective": true,          # 원근 변환 활성화
    "rotation_range": [-30, 30],         # 회전 범위 (도)
    "scale_range": [0.8, 1.2],          # 크기 범위
    "epsilon": 0.6,
    "alpha": 0.03,
    "iterations": 200,
    "printable_colors": false,           # 인쇄 가능 색상 제약
    "smoothness_weight": 0.0             # 부드러움 가중치
}
```

## 구현된 플러그인

### 2D 패치 생성

#### GlobalPGDPatch2D
**플러그인 이름**: `global_pgd_2d`
**파일**: `app/plugins/attacks/global_pgd_patch_2d.py`
**설명**: Global PGD 알고리즘 기반 2D 패치 생성

**특징**:
- 여러 이미지에 걸쳐 최적화
- 객체 탐지 모델 공격
- 섭동 예산 제약

### 2D 노이즈 공격

#### FGSMNoise2D
**플러그인 이름**: `fgsm_2d`
**파일**: `app/plugins/attacks/fgsm_noise_2d.py`
**설명**: Fast Gradient Sign Method 노이즈 공격

**특징**:
- 단일 스텝 공격
- 빠른 생성 속도
- 타겟/언타겟 공격 지원

#### PGDNoise2D
**플러그인 이름**: `pgd_2d`
**파일**: `app/plugins/attacks/pgd_noise_2d.py`
**설명**: Projected Gradient Descent 노이즈 공격

**특징**:
- 반복적 공격
- FGSM보다 강력
- 엡실론 볼 투영

#### GaussianNoise2D
**플러그인 이름**: `gaussian_2d`
**파일**: `app/plugins/attacks/gaussian_noise_2d.py`
**설명**: 가우시안 분포 노이즈

**특징**:
- 모델 불필요
- 빠른 생성
- 통계적 특성

#### UniformNoise2D
**플러그인 이름**: `uniform_2d`
**파일**: `app/plugins/attacks/uniform_noise_2d.py`
**설명**: 균등 분포 노이즈

**특징**:
- 모델 불필요
- 균일한 노이즈 분포
- 범위 조절 가능

### 3D 패치 생성

#### RPAttackPatch3D
**플러그인 이름**: `rpattack_3d`
**파일**: `app/plugins/attacks/rpattack_patch_3d.py`
**설명**: Robust Physical Attack 3D 패치

**특징**:
- 회전, 크기, 원근 변환에 강건
- EOT (Expectation Over Transformation) 사용
- 물리적 환경에서 효과적

## API 엔드포인트

### 플러그인 목록 조회

#### 모든 플러그인 조회
```http
GET /api/v1/attack-plugins/plugins
```

**응답**:
```json
{
  "total": 6,
  "plugins": [
    {
      "name": "global_pgd_2d",
      "version": "1.0.0",
      "category": "patch",
      "description": "Global PGD-based 2D patch generation",
      "requires_model": true,
      "requires_gradient": true,
      "supports_targeted": true,
      "config_schema": {...}
    },
    ...
  ]
}
```

#### 2D 패치 플러그인 조회
```http
GET /api/v1/attack-plugins/patch-2d
```

#### 2D 노이즈 플러그인 조회
```http
GET /api/v1/attack-plugins/noise-2d
```

#### 3D 패치 플러그인 조회
```http
GET /api/v1/attack-plugins/patch-3d
```

#### 특정 플러그인 정보
```http
GET /api/v1/attack-plugins/plugins/{plugin_name}
```

#### 카테고리별 필터링
```http
GET /api/v1/attack-plugins/plugins?category=patch
GET /api/v1/attack-plugins/plugins?category=noise
GET /api/v1/attack-plugins/plugins?requires_model=true
```

## 새 플러그인 작성 방법

### 1. 베이스 클래스 상속

```python
# 2D 패치 플러그인 예시
from app.plugins.patch_2d_base import Patch2DGenerationPlugin

class MyPatch2D(Patch2DGenerationPlugin):
    name = "my_patch_2d"
    version = "1.0.0"
    description = "My custom 2D patch generation method"

    async def generate_patch(self, model_path, image_bbox_list, target_class_id, config, **kwargs):
        # 구현
        pass

    async def optimize_patch(self, patch, model, images, bboxes, target_class_id, config, **kwargs):
        # 구현
        pass
```

### 2. 플러그인 파일 저장

파일을 `app/plugins/attacks/` 디렉토리에 저장:
```
app/plugins/attacks/my_patch_2d.py
```

### 3. 자동 등록

애플리케이션 시작 시 자동으로 발견되고 등록됩니다:
- `main.py`의 `startup_event`에서 `discover_plugins()` 호출
- `app/plugins/attacks/` 디렉토리의 모든 플러그인 자동 로드

## 플러그인 사용 예시

### Python 코드에서 사용

```python
from app.plugins import attack_plugin_registry

# 플러그인 가져오기
plugin = attack_plugin_registry.get_plugin("global_pgd_2d")

# 설정 준비
from app.plugins.patch_2d_base import Patch2DConfig

config = Patch2DConfig(
    patch_size=100,
    area_ratio=0.3,
    epsilon=0.6,
    target_class="person",
    model_version_id="...",
    base_dataset_id="...",
    output_dataset_name="attack_output"
)

# 플러그인 실행
result = await plugin.execute(config, db_session)
```

### API를 통한 사용

1. 사용 가능한 플러그인 확인:
```bash
curl http://localhost:8000/api/v1/attack-plugins/patch-2d
```

2. 플러그인 설정 스키마 확인:
```bash
curl http://localhost:8000/api/v1/attack-plugins/plugins/global_pgd_2d
```

3. 공격 실행 (기존 adversarial 엔드포인트 사용)

## 테스트

플러그인 시스템 테스트:
```bash
pytest tests/test_attack_plugins.py -v
```

**테스트 항목**:
- ✅ 플러그인 목록 조회
- ✅ 2D 패치 플러그인 필터링
- ✅ 2D 노이즈 플러그인 필터링
- ✅ 3D 패치 플러그인 필터링
- ✅ 플러그인 메타데이터 검증
- ✅ 카테고리별 필터링
- ✅ 모델 요구사항 필터링

## 확장성

플러그인 시스템의 장점:

1. **모듈화**: 각 공격 기법이 독립적인 플러그인
2. **확장 용이**: 새 플러그인 추가가 간단
3. **일관된 인터페이스**: 모든 플러그인이 동일한 API 사용
4. **자동 발견**: 파일 추가만으로 자동 등록
5. **타입 안정성**: Pydantic 스키마로 설정 검증
6. **문서화**: JSON 스키마로 자동 문서 생성

## 다음 단계

플러그인 시스템을 활용한 추가 기능:

1. **서비스 통합**: 기존 서비스에서 플러그인 시스템 사용
2. **UI 통합**: 프론트엔드에서 플러그인 선택 및 설정
3. **벤치마크**: 플러그인별 성능 비교
4. **파라미터 튜닝**: 자동 하이퍼파라미터 최적화
5. **앙상블**: 여러 플러그인 조합
