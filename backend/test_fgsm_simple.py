"""
Simple FGSM test following the notebook approach
"""
import numpy as np
from ultralytics import YOLO
from art.estimators.object_detection import PyTorchYolo
from art.attacks.evasion import FastGradientMethod
from PIL import Image

# Load model
model_path = "/home/jaehyun/army/test_model/yolov8/yolov8n.pt"
yolo_model = YOLO(model_path)

print(f"✓ Model loaded: {type(yolo_model)}")

# Create ART estimator (following notebook approach)
estimator = PyTorchYolo(
    model=yolo_model.model,
    input_shape=(3, 640, 640),
    channels_first=True,  # PyTorch uses NCHW
    clip_values=(0, 255),
    attack_losses=("loss_total",),
    device_type="cpu",
    is_ultralytics=True,
    model_name="yolov8",
)

print(f"✓ ART estimator created: {type(estimator)}")

# Load test image and convert to NCHW (following notebook approach)
img_path = "/home/jaehyun/datasets/coco_person_100/images/000000395388.jpg"
img = Image.open(img_path).convert('RGB')
img = img.resize((640, 640), Image.BICUBIC)
img_array = np.array(img)  # (H, W, C)

# Convert to NCHW (following notebook approach)
img_array = img_array.transpose(2, 0, 1)  # (H, W, C) -> (C, H, W)
img_array = np.expand_dims(img_array, axis=0).astype(np.float32)  # -> (1, C, H, W)

print(f"✓ Image loaded: shape={img_array.shape}, range=[{img_array.min()}, {img_array.max()}]")

# Create FGSM attack
attack = FastGradientMethod(
    estimator=estimator,
    norm=np.inf,
    eps=8.0,
    targeted=False,
    batch_size=1,
)

print(f"✓ Attack created: {type(attack)}")

# Generate adversarial example
print("\nGenerating adversarial example...")
try:
    x_adv = attack.generate(x=img_array)
    print(f"✓ Attack succeeded!")
    print(f"  Output shape: {x_adv.shape}")
    print(f"  Output range: [{x_adv.min()}, {x_adv.max()}]")
    print(f"  Max perturbation: {np.abs(x_adv - img_array).max()}")
except Exception as e:
    print(f"✗ Attack failed: {e}")
    import traceback
    traceback.print_exc()
