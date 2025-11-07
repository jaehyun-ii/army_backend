# 공격 관련 구현 계획서 (최종판)

**작성일**: 2025-01-05  
**버전**: 3.0 (패치/노이즈 워크플로우 분리)  
**목적**: 패치와 노이즈 공격의 서로 다른 워크플로우를 반영한 구현 계획

---

## 📋 핵심 차이점 이해

### Noise 공격 (FGSM, PGD)
**워크플로우: 단일 스텝**
```
Input: base_dataset + model + noise_params
  ↓
Apply noise directly to images (per-image attack)
  ↓
Output: attacked_dataset
```

### Patch 공격 (AdversarialPatch, DPatch, RobustDPatch)
**워크플로우: 2-스텝**
```
Step 1: Patch Generation
Input: training_images + model + patch_params
  ↓
Generate universal adversarial patch
  ↓
Output: patch file (saved to DB as Patch2D)

Step 2: Patch Application
Input: base_dataset + patch_id
  ↓
Apply patch to all images
  ↓
Output: attacked_dataset
```

---

## 1. 데이터베이스 스키마 확인

### Patch2D 테이블
```sql
CREATE TABLE patches_2d (
    id UUID PRIMARY KEY,
    name VARCHAR(200),
    target_model_id UUID REFERENCES od_models(id),
    source_dataset_id UUID REFERENCES datasets_2d(id),  -- 패치 생성에 사용된 데이터셋
    target_class VARCHAR(200),
    method VARCHAR(200),  -- "patch", "dpatch", "robust_dpatch"
    hyperparameters JSONB,
    patch_metadata JSONB,
    storage_key TEXT,  -- 패치 파일 경로
    file_name VARCHAR(1024),
    ...
);
```

### AttackDataset2D 테이블
```sql
CREATE TABLE attack_datasets_2d (
    id UUID PRIMARY KEY,
    name VARCHAR(200),
    attack_type attack_type_enum,  -- 'patch' or 'noise'
    target_model_id UUID REFERENCES od_models(id),
    base_dataset_id UUID REFERENCES datasets_2d(id),  -- 공격 대상 데이터셋
    target_class VARCHAR(200),
    patch_id UUID REFERENCES patches_2d(id),  -- patch 공격인 경우에만 사용
    parameters JSONB,
    ...
    
    CONSTRAINT chk_attack_patch_id_required CHECK (
        (attack_type = 'patch' AND patch_id IS NOT NULL) OR 
        (attack_type <> 'patch' AND patch_id IS NULL)
    )
);
```

---

## 2. API 설계

### 2.1 Noise 공격 API (단일 스텝)

#### POST /api/v1/attack-datasets/noise
**목적**: FGSM/PGD 공격을 base_dataset에 적용하여 attacked_dataset 생성

**Request:**
```json
{
  "attack_name": "PGD_Person_Attack",
  "attack_method": "pgd",  // "fgsm" or "pgd"
  "base_dataset_id": "uuid-dataset-123",
  "model_id": "uuid-model-456",
  "epsilon": 8.0,
  "alpha": 2.0,  // PGD only
  "iterations": 10,  // PGD only
  "session_id": "sse-session-789"
}
```

**Response:**
```json
{
  "attack_dataset": {
    "id": "uuid-attack-abc",
    "name": "PGD_Person_Attack",
    "attack_type": "noise",
    "target_model_id": "uuid-model-456",
    "base_dataset_id": "uuid-dataset-123",
    "parameters": {
      "attack_method": "pgd",
      "epsilon": 8.0,
      "alpha": 2.0,
      "iterations": 10,
      "processed_images": 150,
      "output_dataset_id": "uuid-output-def"
    }
  },
  "output_dataset_id": "uuid-output-def",
  "storage_path": "/storage/attack_datasets/PGD_Person_Attack_20250105/",
  "statistics": {
    "processed_images": 150,
    "failed_images": 0,
    "avg_perturbation_l_inf": 0.031
  }
}
```

---

### 2.2 Patch 공격 API (2-스텝)

#### Step 1: Patch 생성

##### POST /api/v1/patches/generate
**목적**: 훈련 이미지로부터 universal adversarial patch 생성

**Request:**
```json
{
  "patch_name": "Person_Invisibility_Patch",
  "attack_method": "robust_dpatch",  // "patch", "dpatch", "robust_dpatch"
  "source_dataset_id": "uuid-training-dataset-123",  // 패치 생성용 데이터셋
  "model_id": "uuid-model-456",
  "target_class": "person",
  "patch_size": 100,
  "learning_rate": 5.0,
  "iterations": 500,
  "session_id": "sse-session-789"
}
```

**Response:**
```json
{
  "patch": {
    "id": "uuid-patch-xyz",
    "name": "Person_Invisibility_Patch",
    "target_model_id": "uuid-model-456",
    "source_dataset_id": "uuid-training-dataset-123",
    "target_class": "person",
    "method": "robust_dpatch",
    "hyperparameters": {
      "patch_size": 100,
      "learning_rate": 5.0,
      "iterations": 500
    },
    "storage_key": "patches/patch-xyz.png",
    "file_name": "patch-xyz.png"
  },
  "patch_file_path": "/storage/patches/patch-xyz.png",
  "training_statistics": {
    "training_images": 50,
    "training_time_seconds": 120.5
  }
}
```

#### Step 2: Patch 적용

##### POST /api/v1/attack-datasets/patch
**목적**: 기존 patch를 base_dataset에 적용하여 attacked_dataset 생성

**Request:**
```json
{
  "attack_name": "Person_Patch_Attack_Dataset",
  "patch_id": "uuid-patch-xyz",  // Step 1에서 생성된 패치
  "base_dataset_id": "uuid-target-dataset-456",  // 패치 적용 대상
  "session_id": "sse-session-890"
}
```

**Response:**
```json
{
  "attack_dataset": {
    "id": "uuid-attack-def",
    "name": "Person_Patch_Attack_Dataset",
    "attack_type": "patch",
    "target_model_id": "uuid-model-456",  // patch에서 상속
    "base_dataset_id": "uuid-target-dataset-456",
    "target_class": "person",  // patch에서 상속
    "patch_id": "uuid-patch-xyz",
    "parameters": {
      "processed_images": 200,
      "output_dataset_id": "uuid-output-ghi"
    }
  },
  "output_dataset_id": "uuid-output-ghi",
  "storage_path": "/storage/attack_datasets/Person_Patch_Attack_Dataset_20250105/",
  "statistics": {
    "processed_images": 200,
    "failed_images": 0
  }
}
```

---

## 3. 서비스 설계

### 3.1 NoiseAttackService (신규)

```python
class NoiseAttackService:
    """
    Noise 공격 데이터셋 생성 서비스 (FGSM, PGD).
    단일 스텝: base_dataset → attacked_dataset
    """
    
    async def create_noise_attack_dataset(
        self,
        db: AsyncSession,
        attack_name: str,
        attack_method: str,  # "fgsm" or "pgd"
        base_dataset_id: UUID,
        model_id: UUID,
        epsilon: float,
        alpha: Optional[float] = None,
        iterations: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[AttackDataset2D, UUID]:
        """
        워크플로우:
        1. base_dataset 이미지 로드
        2. model → estimator 로드
        3. ART 공격 객체 생성 (FastGradientMethod or ProjectedGradientDescent)
        4. 각 이미지에 노이즈 적용
        5. 공격된 이미지를 output_dataset에 저장
        6. AttackDataset2D 레코드 생성 (attack_type='noise', patch_id=NULL)
        
        Returns:
            (attack_dataset, output_dataset_id)
        """
        logger = SSELogger(...)
        
        # 1. 리소스 로드
        await logger.status("데이터셋 로딩 중...")
        images = await self._load_images(db, base_dataset_id)
        
        await logger.status("모델 로딩 중...")
        estimator = await self._load_estimator(db, model_id)
        
        # 2. ART 공격 생성
        if attack_method == "fgsm":
            from app.ai.attacks.evasion import FastGradientMethod
            attack = FastGradientMethod(
                estimator=estimator,
                eps=epsilon / 255.0,
            )
        elif attack_method == "pgd":
            from app.ai.attacks.evasion import ProjectedGradientDescent
            attack = ProjectedGradientDescent(
                estimator=estimator,
                eps=epsilon / 255.0,
                eps_step=alpha / 255.0,
                max_iter=iterations,
            )
        
        # 3. 이미지별 공격 적용
        attacked_images = []
        for idx, img in enumerate(images):
            await logger.progress(f"{idx+1}/{len(images)}", current=idx+1, total=len(images))
            adv_img = attack.generate(x=np.expand_dims(img, axis=0))
            attacked_images.append(adv_img[0])
        
        # 4. Output dataset 생성
        output_dataset = await self._create_output_dataset(
            db, f"{attack_name}_output", attacked_images
        )
        
        # 5. AttackDataset2D 생성
        attack_dataset = await crud.attack_dataset_2d.create(
            db,
            obj_in=AttackDataset2DCreate(
                name=attack_name,
                attack_type=AttackType.NOISE,
                target_model_id=model_id,
                base_dataset_id=base_dataset_id,
                patch_id=None,  # Noise 공격은 patch 없음
                parameters={
                    "attack_method": attack_method,
                    "epsilon": epsilon,
                    "alpha": alpha,
                    "iterations": iterations,
                    "processed_images": len(attacked_images),
                    "output_dataset_id": str(output_dataset.id),
                }
            )
        )
        
        await logger.success("완료!", processed=len(attacked_images))
        return attack_dataset, output_dataset.id
```

### 3.2 PatchService (신규)

```python
class PatchService:
    """
    Patch 생성 및 관리 서비스.
    Step 1: 패치 생성
    """
    
    async def generate_patch(
        self,
        db: AsyncSession,
        patch_name: str,
        attack_method: str,  # "patch", "dpatch", "robust_dpatch"
        source_dataset_id: UUID,
        model_id: UUID,
        target_class: str,
        patch_size: int,
        learning_rate: float,
        iterations: int,
        session_id: Optional[str] = None,
    ) -> Patch2D:
        """
        워크플로우:
        1. source_dataset에서 target_class 이미지 수집
        2. model → estimator 로드
        3. ART 패치 객체 생성 (AdversarialPatchPyTorch, DPatch, RobustDPatch)
        4. 패치 생성 (training)
        5. 패치 파일 저장 (/storage/patches/)
        6. Patch2D 레코드 생성
        
        Returns:
            Patch2D 레코드
        """
        logger = SSELogger(...)
        
        # 1. target_class 이미지 수집
        await logger.status(f"'{target_class}' 이미지 수집 중...")
        training_images = await self._collect_target_images(
            db, source_dataset_id, target_class
        )
        
        # 2. Estimator 로드
        estimator = await self._load_estimator(db, model_id)
        
        # 3. ART 패치 클래스 선택
        if attack_method == "patch":
            from app.ai.attacks.evasion import AdversarialPatchPyTorch
            patch_attack = AdversarialPatchPyTorch(
                estimator=estimator,
                patch_shape=(3, patch_size, patch_size),
                learning_rate=learning_rate,
                max_iter=iterations,
            )
        elif attack_method == "dpatch":
            from app.ai.attacks.evasion import DPatch
            patch_attack = DPatch(...)
        elif attack_method == "robust_dpatch":
            from app.ai.attacks.evasion import RobustDPatch
            patch_attack = RobustDPatch(...)
        
        # 4. 패치 생성
        await logger.status(f"패치 생성 중 ({iterations} iterations)...")
        x_train = np.stack(training_images, axis=0)
        patch = patch_attack.generate(x=x_train)
        
        # 5. 패치 저장
        patch_dir = self.storage_root / "patches"
        patch_dir.mkdir(parents=True, exist_ok=True)
        patch_filename = f"{patch_name}_{uuid.uuid4().hex[:8]}.png"
        patch_path = patch_dir / patch_filename
        
        cv2.imwrite(str(patch_path), cv2.cvtColor(patch, cv2.COLOR_RGB2BGR))
        
        # 6. DB 레코드 생성
        patch_record = await crud.patch_2d.create(
            db,
            obj_in=Patch2DCreate(
                name=patch_name,
                target_model_id=model_id,
                source_dataset_id=source_dataset_id,
                target_class=target_class,
                method=attack_method,
                hyperparameters={
                    "patch_size": patch_size,
                    "learning_rate": learning_rate,
                    "iterations": iterations,
                },
                storage_key=f"patches/{patch_filename}",
                file_name=patch_filename,
            )
        )
        
        await logger.success("패치 생성 완료!", patch_id=str(patch_record.id))
        return patch_record


class PatchAttackService:
    """
    Patch 적용 서비스.
    Step 2: 기존 패치를 데이터셋에 적용
    """
    
    async def apply_patch_to_dataset(
        self,
        db: AsyncSession,
        attack_name: str,
        patch_id: UUID,
        base_dataset_id: UUID,
        session_id: Optional[str] = None,
    ) -> Tuple[AttackDataset2D, UUID]:
        """
        워크플로우:
        1. patch 레코드 로드 (Patch2D)
        2. 패치 파일 로드
        3. base_dataset 이미지 로드
        4. 각 이미지에 패치 적용 (중앙 배치 or 랜덤 위치)
        5. Output dataset 생성
        6. AttackDataset2D 레코드 생성 (attack_type='patch', patch_id=patch_id)
        
        Returns:
            (attack_dataset, output_dataset_id)
        """
        logger = SSELogger(...)
        
        # 1. Patch 로드
        await logger.status("패치 로딩 중...")
        patch_record = await crud.patch_2d.get(db, id=patch_id)
        if not patch_record:
            raise NotFoundError(f"Patch {patch_id} not found")
        
        patch_path = self.storage_root / patch_record.storage_key
        patch = cv2.imread(str(patch_path))
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        
        # 2. Base dataset 이미지 로드
        await logger.status("데이터셋 로딩 중...")
        images = await self._load_images(db, base_dataset_id)
        
        # 3. 패치 적용
        patched_images = []
        for idx, img in enumerate(images):
            await logger.progress(f"{idx+1}/{len(images)}", current=idx+1, total=len(images))
            
            # 중앙 배치
            patched_img = self._apply_patch_center(img, patch)
            patched_images.append(patched_img)
        
        # 4. Output dataset 생성
        output_dataset = await self._create_output_dataset(
            db, f"{attack_name}_output", patched_images
        )
        
        # 5. AttackDataset2D 생성
        attack_dataset = await crud.attack_dataset_2d.create(
            db,
            obj_in=AttackDataset2DCreate(
                name=attack_name,
                attack_type=AttackType.PATCH,
                target_model_id=patch_record.target_model_id,
                base_dataset_id=base_dataset_id,
                target_class=patch_record.target_class,
                patch_id=patch_id,
                parameters={
                    "processed_images": len(patched_images),
                    "output_dataset_id": str(output_dataset.id),
                }
            )
        )
        
        await logger.success("패치 적용 완료!", processed=len(patched_images))
        return attack_dataset, output_dataset.id
```

---

## 4. API 엔드포인트 구현

### 4.1 Noise 공격 엔드포인트

```python
# app/api/v1/endpoints/attack_datasets.py

from app.services.noise_attack_service import NoiseAttackService

router = APIRouter()
noise_attack_service = NoiseAttackService()

@router.post("/noise", status_code=status.HTTP_201_CREATED)
async def create_noise_attack_dataset(
    attack_name: str = Body(...),
    attack_method: str = Body(...),  # "fgsm" or "pgd"
    base_dataset_id: UUID = Body(...),
    model_id: UUID = Body(...),
    epsilon: float = Body(8.0, ge=0.1, le=255.0),
    alpha: Optional[float] = Body(None, ge=0.01, le=50.0),
    iterations: Optional[int] = Body(None, ge=1, le=100),
    session_id: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """
    FGSM/PGD 노이즈 공격으로 attacked dataset 생성 (단일 스텝).
    """
    attack_dataset, output_dataset_id = await noise_attack_service.create_noise_attack_dataset(
        db=db,
        attack_name=attack_name,
        attack_method=attack_method,
        base_dataset_id=base_dataset_id,
        model_id=model_id,
        epsilon=epsilon,
        alpha=alpha,
        iterations=iterations,
        session_id=session_id,
    )
    
    return {
        "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_dataset),
        "output_dataset_id": str(output_dataset_id),
        "storage_path": attack_dataset.parameters.get("storage_path"),
        "statistics": {
            "processed_images": attack_dataset.parameters.get("processed_images"),
        }
    }
```

### 4.2 Patch 생성 엔드포인트

```python
# app/api/v1/endpoints/patches.py

from app.services.patch_service import PatchService

router = APIRouter()
patch_service = PatchService()

@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_patch(
    patch_name: str = Body(...),
    attack_method: str = Body(...),  # "patch", "dpatch", "robust_dpatch"
    source_dataset_id: UUID = Body(...),
    model_id: UUID = Body(...),
    target_class: str = Body(...),
    patch_size: int = Body(100, ge=50, le=300),
    learning_rate: float = Body(5.0, ge=0.1, le=20.0),
    iterations: int = Body(500, ge=50, le=2000),
    session_id: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Universal adversarial patch 생성.
    """
    patch = await patch_service.generate_patch(
        db=db,
        patch_name=patch_name,
        attack_method=attack_method,
        source_dataset_id=source_dataset_id,
        model_id=model_id,
        target_class=target_class,
        patch_size=patch_size,
        learning_rate=learning_rate,
        iterations=iterations,
        session_id=session_id,
    )
    
    return {
        "patch": schemas.Patch2DResponse.model_validate(patch),
        "patch_file_path": f"/storage/{patch.storage_key}",
    }
```

### 4.3 Patch 적용 엔드포인트

```python
# app/api/v1/endpoints/attack_datasets.py

from app.services.patch_attack_service import PatchAttackService

patch_attack_service = PatchAttackService()

@router.post("/patch", status_code=status.HTTP_201_CREATED)
async def apply_patch_to_dataset(
    attack_name: str = Body(...),
    patch_id: UUID = Body(...),
    base_dataset_id: UUID = Body(...),
    session_id: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2: 기존 patch를 base_dataset에 적용하여 attacked dataset 생성.
    """
    attack_dataset, output_dataset_id = await patch_attack_service.apply_patch_to_dataset(
        db=db,
        attack_name=attack_name,
        patch_id=patch_id,
        base_dataset_id=base_dataset_id,
        session_id=session_id,
    )
    
    return {
        "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_dataset),
        "output_dataset_id": str(output_dataset_id),
        "storage_path": attack_dataset.parameters.get("storage_path"),
    }
```

---

## 5. 파일 구조

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── attack_datasets.py   # Noise + Patch apply
│   │           └── patches.py            # Patch generate
│   ├── services/
│   │   ├── noise_attack_service.py      # FGSM, PGD (단일 스텝)
│   │   ├── patch_service.py             # Patch 생성 (Step 1)
│   │   └── patch_attack_service.py      # Patch 적용 (Step 2)
│   └── ai/
│       └── attacks/
│           └── evasion/                  # ✅ 이미 존재 (재사용)
```

---

## 6. 구현 순서 (수정)

### Phase 1: Noise 공격 (3일)
1. `NoiseAttackService` 구현
2. FGSM, PGD 통합
3. API 엔드포인트
4. 테스트

### Phase 2: Patch 생성 (3일)
1. `PatchService` 구현
2. AdversarialPatch, DPatch, RobustDPatch 통합
3. API 엔드포인트
4. 테스트

### Phase 3: Patch 적용 (2일)
1. `PatchAttackService` 구현
2. Patch 적용 로직
3. API 엔드포인트
4. 테스트

### Phase 4: 통합 (2일)
1. E2E 테스트
2. SSE 로깅 검증
3. 문서화

**총 일정: 10일 (2주)**

---

## 7. 워크플로우 예시

### Noise 공격 (단일 스텝)
```bash
# 1. FGSM 공격 데이터셋 생성
POST /api/v1/attack-datasets/noise
{
  "attack_name": "FGSM_COCO_Attack",
  "attack_method": "fgsm",
  "base_dataset_id": "dataset-123",
  "model_id": "yolo-456",
  "epsilon": 8.0
}

# 결과: attacked_dataset 생성 완료
```

### Patch 공격 (2-스텝)
```bash
# Step 1: Patch 생성
POST /api/v1/patches/generate
{
  "patch_name": "Person_Invisibility",
  "attack_method": "robust_dpatch",
  "source_dataset_id": "training-dataset-123",
  "model_id": "yolo-456",
  "target_class": "person",
  "patch_size": 100,
  "learning_rate": 5.0,
  "iterations": 500
}
# 결과: patch-xyz 생성

# Step 2: Patch 적용
POST /api/v1/attack-datasets/patch
{
  "attack_name": "Person_Attack_Dataset",
  "patch_id": "patch-xyz",
  "base_dataset_id": "target-dataset-789"
}
# 결과: attacked_dataset 생성 완료
```

---

**작성자**: Claude (AI Assistant)  
**주요 변경**: 패치/노이즈 워크플로우 분리, 2-스텝 패치 구조 명확화  
**예상 기간**: 10일 (2주)
