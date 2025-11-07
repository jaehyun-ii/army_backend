"""
Test ART PyTorchYolo directly
"""
import numpy as np
from ultralytics import YOLO
from art.estimators.object_detection import PyTorchYolo
from art.attacks.evasion import FastGradientMethod

# Load model
model_path = "/home/jaehyun/army/army_ai/database/storage/models/YOLOv8n_Noise_2962/1.0.0/yolov8n.pt"
yolo_model = YOLO(model_path)

print(f"Model loaded: {type(yolo_model)}")
print(f"Internal model: {type(yolo_model.model)}")

# Create ART estimator
# is_ultralytics=True is REQUIRED for YOLOv8+
# model_name is also required when using is_ultralytics=True
# channels_first=False because we provide NCHW input directly
estimator = PyTorchYolo(
    model=yolo_model.model,
    input_shape=(3, 640, 640),
    channels_first=False,  # We provide NCHW directly (workaround for ART bug)
    clip_values=(0, 255),
    attack_losses=("loss_total",),
    device_type="cpu",
    is_ultralytics=True,  # REQUIRED for YOLOv8+
    model_name="yolov8",  # Required with is_ultralytics
)

print(f"✓ ART estimator created: {type(estimator)}")
print(f"  Is BaseEstimator: {hasattr(estimator, 'model')}")

# Create FGSM attack
attack = FastGradientMethod(
    estimator=estimator,
    norm=np.inf,
    eps=8.0,
    targeted=False,
    batch_size=1,
)

print(f"✓ Attack created: {type(attack)}")

# Test with random image (MUST match model input_shape: 640x640)
x_hwc = np.random.randint(0, 256, size=(640, 640, 3), dtype=np.uint8).astype(np.float32)
x_nchw = np.transpose(x_hwc[np.newaxis, :, :, :], (0, 3, 1, 2))  # (1, C, H, W)
print(f"\nTest image shape (NCHW): {x_nchw.shape}, dtype: {x_nchw.dtype}, range: [{x_nchw.min()}, {x_nchw.max()}]")

try:
    x_adv = attack.generate(x=x_nchw)
    print(f"✓ Attack succeeded!")
    print(f"  Output shape: {x_adv.shape}, dtype: {x_adv.dtype}")
    print(f"  Max perturbation: {np.abs(x_adv - x_nchw).max()}")
except Exception as e:
    print(f"✗ Attack failed: {e}")
    import traceback
    traceback.print_exc()
