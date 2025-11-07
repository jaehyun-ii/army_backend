# Comprehensive Patch Attack Testing

This document explains how to test all supported patch generation methods in the system.

## Supported Patch Methods

The system supports **3 patch generation methods**:

1. **`patch`** - AdversarialPatchPyTorch
   - General adversarial patch with transformations
   - Supports rotation, scaling, and various transformations
   - Best for general-purpose patch attacks

2. **`dpatch`** - DPatch
   - Object detector specific patch attack
   - Optimized for object detection models
   - Based on the DPatch paper

3. **`robust_dpatch`** - RobustDPatch
   - Robust version of DPatch
   - Resilient to cropping, rotation, and brightness changes
   - Uses Expectation Over Transformation (EOT)
   - More robust but slower to generate

## Test Script

The comprehensive test script `test_patch_only.py` tests all three methods automatically.

### Features

- Tests all 3 patch generation methods sequentially
- Uses the same dataset and model for fair comparison
- Generates patches and applies them to the dataset
- Provides detailed progress output and timing information
- Comprehensive results summary at the end

### Test Configuration

Each method is tested with the following parameters:

```python
# AdversarialPatchPyTorch
{
    "attack_method": "patch",
    "patch_size": 200,
    "learning_rate": 5.0,
    "iterations": 50,
}

# DPatch
{
    "attack_method": "dpatch",
    "patch_size": 150,
    "learning_rate": 5.0,
    "iterations": 50,
}

# RobustDPatch
{
    "attack_method": "robust_dpatch",
    "patch_size": 150,
    "learning_rate": 5.0,
    "iterations": 50,
}
```

## Running the Test

### Prerequisites

1. Backend server must be running:
   ```bash
   cd /home/jaehyun/army/army_ai/backend
   python -m app.main
   ```

2. Required dataset and model files:
   - Dataset: `/home/jaehyun/datasets/coco_person_100/`
   - Model: `/home/jaehyun/army/test_model/yolov8/yolov8n.pt`

### Execute Test

```bash
cd /home/jaehyun/army/army_ai/backend
python test_patch_only.py
```

### Expected Output

The test will:

1. **Setup Phase**
   - Upload COCO Person 100 dataset
   - Upload YOLOv8n model

2. **Testing Phase** - For each method:
   - Generate adversarial patch (this takes several minutes)
   - Apply patch to dataset
   - Report results

3. **Summary Phase**
   - Display results for all methods
   - Show success/failure counts
   - Provide timing information

### Example Output

```
================================================================================
COMPREHENSIVE PATCH ATTACK TEST
Testing all patch generation methods
================================================================================

[SETUP] Uploading YOLO Dataset...
--------------------------------------------------------------------------------
✓ Dataset uploaded: <uuid>
  - Name: COCO_Person_100_AllPatches_1234
  - Images: 100

[SETUP] Uploading Model...
--------------------------------------------------------------------------------
✓ Model uploaded: <uuid>
  - Name: YOLOv8n_AllPatches_5678

================================================================================
TESTING ALL PATCH METHODS
================================================================================

================================================================================
TEST [1/3]: PATCH
Description: AdversarialPatchPyTorch (general patch with transformations)
================================================================================

[Step 1] Generating PATCH Patch...
--------------------------------------------------------------------------------
Parameters:
  - Patch size: 200x200
  - Learning rate: 5.0
  - Iterations: 50
This may take several minutes...
✓ Patch generated: <patch-uuid>
  - Elapsed time: 123.4s
  - Patch file: /storage/patches/Person_patch_1234_20251106_120000.png

[Step 2] Applying PATCH Patch to Dataset...
--------------------------------------------------------------------------------
✓ Patch applied to dataset
  - Attack dataset ID: <attack-dataset-uuid>
  - Output dataset ID: <output-dataset-uuid>
  - Processed: 100
  - Failed: 0

✓ PATCH test completed successfully!

... (similar output for dpatch and robust_dpatch) ...

================================================================================
COMPREHENSIVE TEST RESULTS
================================================================================

✓ Dataset: <dataset-uuid>
✓ Model: <model-uuid>

Patch Method Results:
--------------------------------------------------------------------------------

✓ PATCH
  - Patch ID: <patch-uuid-1>
  - Attack Dataset ID: <attack-dataset-uuid-1>
  - Output Dataset ID: <output-dataset-uuid-1>
  - Processed images: 100
  - Failed images: 0
  - Elapsed time: 123.4s

✓ DPATCH
  - Patch ID: <patch-uuid-2>
  - Attack Dataset ID: <attack-dataset-uuid-2>
  - Output Dataset ID: <output-dataset-uuid-2>
  - Processed images: 100
  - Failed images: 0
  - Elapsed time: 145.2s

✓ ROBUST_DPATCH
  - Patch ID: <patch-uuid-3>
  - Attack Dataset ID: <attack-dataset-uuid-3>
  - Output Dataset ID: <output-dataset-uuid-3>
  - Processed images: 100
  - Failed images: 0
  - Elapsed time: 189.7s

================================================================================
OVERALL: 3/3 tests passed
================================================================================

✓ All patch methods tested successfully!

================================================================================
NEXT STEPS:
================================================================================
1. Compare detection results on original vs patched images
2. Evaluate attack success rate for each method
3. Compare effectiveness of different patch methods
4. Visualize patched images with detection boxes
================================================================================
```

## Test Duration

Expected test duration:

- **Setup**: ~1-2 minutes (dataset + model upload)
- **Patch generation**: ~2-5 minutes per method (depends on iterations)
- **Patch application**: ~30 seconds per method
- **Total**: ~10-20 minutes for all 3 methods with 50 iterations

To reduce test time, you can modify the `iterations` parameter in the `PATCH_METHODS` configuration (minimum: 50).

## Output Files

After successful execution, you will have:

1. **3 Patch files** in `/storage/patches/`:
   - `Person_patch_XXXX_timestamp.png` (AdversarialPatchPyTorch)
   - `Person_dpatch_XXXX_timestamp.png` (DPatch)
   - `Person_robust_dpatch_XXXX_timestamp.png` (RobustDPatch)

2. **3 Attack datasets** with patched images

3. **3 Output datasets** containing the images with patches applied

## Implementation Details

### Code Location

- **Test script**: `test_patch_only.py`
- **Patch service**: `app/services/patch_service.py`
- **API endpoint**: `app/api/v1/endpoints/patches.py`
- **Patch implementations**: `app/ai/attacks/evasion/`
  - `adversarial_patch/adversarial_patch_pytorch.py` (patch method)
  - `dpatch.py` (dpatch method)
  - `dpatch_robust.py` (robust_dpatch method)

### API Reference

**Generate Patch Endpoint:**
```
POST /api/v1/patches/generate
```

**Request Body:**
```json
{
  "patch_name": "Person_Patch_1234",
  "attack_method": "patch|dpatch|robust_dpatch",
  "source_dataset_id": "<dataset-uuid>",
  "model_id": "<model-uuid>",
  "target_class": "person",
  "patch_size": 150,
  "learning_rate": 5.0,
  "iterations": 50
}
```

**Apply Patch Endpoint:**
```
POST /api/v1/attack-datasets/patch
```

**Request Body:**
```json
{
  "attack_name": "Patched_Dataset_1234",
  "patch_id": "<patch-uuid>",
  "base_dataset_id": "<dataset-uuid>"
}
```

## Troubleshooting

### Backend not running
```bash
cd /home/jaehyun/army/army_ai/backend
python -m app.main
```

### Dataset not found
Verify the dataset path exists:
```bash
ls -la /home/jaehyun/datasets/coco_person_100/
```

### Model not found
Verify the model path exists:
```bash
ls -la /home/jaehyun/army/test_model/yolov8/yolov8n.pt
```

### Timeout errors
- Increase iterations reduces quality but speeds up generation
- Minimum iterations: 50 (API validation)
- Recommended iterations: 100-500
- Production iterations: 500-1000+

### Memory issues
- Reduce patch_size (e.g., 100 instead of 200)
- Reduce batch size in patch_service.py
- Use smaller dataset for testing

## Next Steps

After running the comprehensive test:

1. **Evaluate attack effectiveness**
   - Run detection on original images
   - Run detection on patched images
   - Calculate detection rate reduction

2. **Compare methods**
   - Compare attack success rates
   - Analyze visual quality of patches
   - Measure robustness to transformations

3. **Optimize parameters**
   - Experiment with different patch sizes
   - Try different learning rates
   - Increase iterations for better quality

4. **Visualize results**
   - Create before/after comparison images
   - Visualize detection bounding boxes
   - Analyze which objects are successfully evaded
