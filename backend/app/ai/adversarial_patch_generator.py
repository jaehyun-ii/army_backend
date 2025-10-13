import torch

import cv2

import numpy as np

from pathlib import Path

from ultralytics import YOLO

import json

from datetime import datetime





class GlobalPGDPatchGenerator:

    def __init__(self, model_path='yolo8n.pt', patch_size=100, area_ratio=0.3, epsilon=0.3, alpha=0.01, iterations=100, batch_size=8, input_size=640, log_callback=None):

        torch.manual_seed(123)

        np.random.seed(123)



        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        self.model = YOLO(model_path)

        self.model.model.to(self.device)

        self.model.model.eval()

        for p in self.model.model.parameters():

            p.requires_grad = False

        self.base_patch_size = patch_size

        self.area_ratio = area_ratio

        self.epsilon = epsilon

        self.alpha = alpha

        self.iterations = iterations

        self.batch_size = batch_size

        self.input_size = input_size

        self.log_callback = log_callback

        self.eps = 1e-6

        self.img_cache = {}

        self.topk = 100

        self.initial_alpha = alpha

        self.initial_area_ratio = area_ratio



    def calculate_patch_size_for_bbox(self, bbox):

        x1, y1, x2, y2 = bbox

        bbox_w = x2 - x1

        bbox_h = y2 - y1

        bbox_area = bbox_w * bbox_h



        target_patch_area = bbox_area * self.area_ratio

        patch_size = int(np.sqrt(target_patch_area))



        return max(patch_size, 10)



    def generate_global_patch(self, image_bbox_list, target_class_id):

        patch_size = self.base_patch_size



        self.area_ratio = 0.4

        self.alpha = 0.02

        print(f"\n[WARMUP] Starting with area_ratio={self.area_ratio}, alpha={self.alpha}")

        print(f"Base patch size: {patch_size}x{patch_size}")

        print(f"Patch will be resized to {self.area_ratio*100}% of each bbox area")



        patch = torch.rand(3, patch_size, patch_size, device=self.device, requires_grad=True)

        patch.data = patch.data * 2 - 1



        optimizer = torch.optim.Adam([patch], lr=self.alpha)



        best_patch = patch.clone()

        best_score = float('inf')



        print(f"Generating global patch for {len(image_bbox_list)} target objects...")

        print(f"Using batch size: {self.batch_size}")



        num_batches = (len(image_bbox_list) + self.batch_size - 1) // self.batch_size



        for iteration in range(self.iterations):

            optimizer.zero_grad()



            if iteration == 20:

                self.alpha = self.initial_alpha

                self.area_ratio = self.initial_area_ratio

                for g in optimizer.param_groups:

                    g['lr'] = self.alpha

                print(f"[WARMUP END] Restoring alpha={self.alpha}, area_ratio={self.area_ratio}")



            total_loss_scalar = 0.0

            total_items = 0

            soft_hits_total = 0

            score_sum_total = 0.0

            pred_count_total = 0



            for batch_idx in range(num_batches):

                start_idx = batch_idx * self.batch_size

                end_idx = min(start_idx + self.batch_size, len(image_bbox_list))

                batch = image_bbox_list[start_idx:end_idx]



                batch_adv_imgs = []

                batch_scaled_bboxes = []



                for img_path, bbox in batch:

                    if img_path not in self.img_cache:

                        img = cv2.imread(str(img_path))

                        self.img_cache[img_path] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    img_rgb = self.img_cache[img_path]

                    orig_h, orig_w = img_rgb.shape[:2]



                    x1, y1, x2, y2 = bbox



                    scale = self.input_size / max(orig_w, orig_h)

                    new_w = int(orig_w * scale)

                    new_h = int(orig_h * scale)



                    resized_img = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)



                    padded_img = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)

                    padded_img[:new_h, :new_w] = resized_img



                    scaled_x1 = int(x1 * scale)

                    scaled_y1 = int(y1 * scale)

                    scaled_x2 = int(x2 * scale)

                    scaled_y2 = int(y2 * scale)

                    scaled_bbox = [scaled_x1, scaled_y1, scaled_x2, scaled_y2]



                    original_img = torch.from_numpy(padded_img).permute(2, 0, 1).float().to(self.device) / 255.0



                    patch_clamped = torch.clamp(patch, -self.epsilon, self.epsilon)

                    patch_scaled = (patch_clamped + 1) / 2



                    target_patch_size = self.calculate_patch_size_for_bbox(scaled_bbox)



                    patch_resized = torch.nn.functional.interpolate(

                        patch_scaled.unsqueeze(0),

                        size=(target_patch_size, target_patch_size),

                        mode='bilinear',

                        align_corners=False

                    ).squeeze(0)



                    center_x = (scaled_x1 + scaled_x2) // 2

                    center_y = (scaled_y1 + scaled_y2) // 2



                    patch_x1 = max(0, center_x - target_patch_size // 2)

                    patch_y1 = max(0, center_y - target_patch_size // 2)

                    patch_x2 = min(self.input_size, patch_x1 + target_patch_size)

                    patch_y2 = min(self.input_size, patch_y1 + target_patch_size)



                    actual_patch_w = patch_x2 - patch_x1

                    actual_patch_h = patch_y2 - patch_y1



                    patch_crop = patch_resized[:, :actual_patch_h, :actual_patch_w]



                    pad_left   = patch_x1

                    pad_right  = self.input_size - patch_x2

                    pad_top    = patch_y1

                    pad_bottom = self.input_size - patch_y2



                    patch_padded = torch.nn.functional.pad(patch_crop, (pad_left, pad_right, pad_top, pad_bottom))



                    dtype = original_img.dtype

                    mask_small = torch.ones((1, actual_patch_h, actual_patch_w), device=self.device, dtype=dtype)



                    edge = 3

                    kernel = torch.ones(1, 1, edge, edge, device=self.device) / (edge * edge)

                    soft = torch.nn.functional.conv2d(mask_small.unsqueeze(0), kernel, padding=edge // 2)

                    soft = soft.squeeze(0).clamp(0, 1)



                    mask = torch.nn.functional.pad(soft, (pad_left, pad_right, pad_top, pad_bottom))

                    mask = mask.expand(3, self.input_size, self.input_size)



                    adv_img = original_img * (1 - mask) + patch_padded * mask



                    batch_adv_imgs.append(adv_img)

                    batch_scaled_bboxes.append(scaled_bbox)



                assert any(t.requires_grad for t in batch_adv_imgs), "adv_img must be connected to patch"

                batch_tensor = torch.stack(batch_adv_imgs).to(self.device, dtype=torch.float32)

                print(f"  [DEBUG] Processing batch {batch_idx+1}/{num_batches}, batch_tensor.shape={batch_tensor.shape}, requires_grad={batch_tensor.requires_grad}")



                with torch.set_grad_enabled(True):

                    print(f"  [DEBUG] Running model inference...")
                    with torch.cuda.amp.autocast(enabled=self.device.type == 'cuda'):
                        raw_output = self.model.model(batch_tensor)
                    print(f"  [DEBUG] Model inference complete")



                    if isinstance(raw_output, (list, tuple)):

                        pred = raw_output[0]

                    else:

                        pred = raw_output

                    if isinstance(pred, (list, tuple)):

                        pred = pred[0]



                    if pred.ndim == 4:

                        B, A, _, C = pred.shape

                        pred = pred.view(B, -1, C)

                    elif pred.ndim == 2:

                        pred = pred.unsqueeze(0)

                    elif pred.ndim != 3:

                        raise RuntimeError(f"Unexpected pred shape: {pred.shape}")



                    boxes_xywh = pred[..., :4]

                    obj_logits = pred[..., 4]

                    cls_logits = pred[..., 5:]



                    obj_scores = torch.sigmoid(obj_logits.clamp(-10, 10))

                    class_scores = torch.sigmoid(cls_logits.clamp(-10, 10))



                    scale_hint = boxes_xywh.detach().amax().to('cpu').item()

                    if scale_hint <= 3.0:

                        boxes_xywh = boxes_xywh * float(self.input_size)

                        if (iteration + 1) % 10 == 0:

                            print(f"  [DEBUG] Box coords are normalized (max={scale_hint:.3f}), scaling to pixels")



                    if (iteration + 1) % 10 == 0:

                        print(f"  [DBG] obj_mean={obj_scores.mean().item():.4f}, cls_mean={class_scores.mean().item():.4f}")

                        print(f"  [DBG] logit_obj_mean={obj_logits.mean().item():.3f}, logit_cls_t_mean={cls_logits[..., target_class_id].mean().item():.3f}")

                        print(f"  [DBG] boxes_xywh amax={boxes_xywh.detach().amax().item():.2f}, amin={boxes_xywh.detach().amin().item():.2f}")



                    p_t = class_scores[..., target_class_id]

                    conf_t = (obj_scores * p_t).clamp(0, 1)



                    x, y, w, h = boxes_xywh.unbind(-1)

                    x1 = (x - w / 2).clamp(0, self.input_size)

                    y1 = (y - h / 2).clamp(0, self.input_size)

                    x2 = (x + w / 2).clamp(0, self.input_size)

                    y2 = (y + h / 2).clamp(0, self.input_size)

                    boxes_xyxy = torch.stack([x1, y1, x2, y2], dim=-1)



                    def iou_xyxy_torch(b1, b2):

                        inter_x1 = torch.maximum(b1[:, 0], b2[0])

                        inter_y1 = torch.maximum(b1[:, 1], b2[1])

                        inter_x2 = torch.minimum(b1[:, 2], b2[2])

                        inter_y2 = torch.minimum(b1[:, 3], b2[3])

                        inter_w = (inter_x2 - inter_x1).clamp(min=0)

                        inter_h = (inter_y2 - inter_y1).clamp(min=0)

                        inter = inter_w * inter_h

                        area1 = (b1[:, 2]-b1[:, 0]).clamp(min=0) * (b1[:, 3]-b1[:, 1]).clamp(min=0)

                        area2 = (b2[2]-b2[0]).clamp(min=0) * (b2[3]-b2[1]).clamp(min=0)

                        return inter / (area1 + area2 - inter + self.eps)



                    loss_batch = 0.0



                    for b in range(pred.shape[0]):

                        gt_xyxy = torch.tensor(batch_scaled_bboxes[b], device=pred.device, dtype=torch.float32)

                        conf_b = conf_t[b]

                        boxes_b = boxes_xyxy[b]



                        if conf_b.numel() == 0:

                            continue



                        H = W = float(self.input_size)

                        gt_cx = ((gt_xyxy[0] + gt_xyxy[2]) * 0.5) / W

                        gt_cy = ((gt_xyxy[1] + gt_xyxy[3]) * 0.5) / H

                        pred_cx = ((boxes_b[:, 0] + boxes_b[:, 2]) * 0.5) / W

                        pred_cy = ((boxes_b[:, 1] + boxes_b[:, 3]) * 0.5) / H



                        sigma = 0.30

                        dist2 = (pred_cx - gt_cx)**2 + (pred_cy - gt_cy)**2

                        dist_w = torch.exp(-dist2 / (2 * sigma * sigma))



                        w = dist_w

                        score_b_all = (obj_scores[b] * class_scores[b, :, target_class_id]) * w



                        K = min(self.topk, score_b_all.numel())

                        topk_vals, topk_idx = torch.topk(score_b_all, k=K, dim=0)



                        obj_logits_b = obj_logits[b]

                        cls_logits_b = cls_logits[b, :, target_class_id]



                        obj_logit_topk = obj_logits_b[topk_idx]

                        cls_logit_topk = cls_logits_b[topk_idx]

                        w_topk = w[topk_idx].detach()



                        import torch.nn.functional as F

                        loss_obj = F.binary_cross_entropy_with_logits(

                            obj_logit_topk, torch.zeros_like(obj_logit_topk),

                            weight=w_topk, reduction='sum'

                        )

                        loss_cls = F.binary_cross_entropy_with_logits(

                            cls_logit_topk, torch.zeros_like(cls_logit_topk),

                            weight=w_topk, reduction='sum'

                        )



                        loss_items = loss_obj + loss_cls



                        if (iteration + 1) % 10 == 0 and b == 0:

                            print(f"  [DBG] dist_w_mean={dist_w.mean().item():.4f}, w_mean={w.mean().item():.4f}")

                            print(f"  [DBG] topk_vals: max={topk_vals.max().item():.4f}, min={topk_vals.min().item():.4f}, mean={topk_vals.mean().item():.4f}")

                            print(f"  [DBG] loss_obj={loss_obj.item():.3f}, loss_cls={loss_cls.item():.3f}")



                        soft_hits_total += (score_b_all > 0.05).sum().item()

                        score_sum_total += score_b_all.sum().item()

                        pred_count_total += score_b_all.numel()



                        loss_batch = loss_batch + loss_items



                loss_batch = loss_batch.float()

                loss_batch.backward()



                total_loss_scalar += loss_batch.item()

                total_items += len(batch)



            if total_items > 0:

                avg_loss = total_loss_scalar / max(1, total_items)



                if (iteration + 1) % 10 == 0:

                    print(f"[Iter {iteration+1}] model.training = {self.model.model.training}, avg_loss = {avg_loss:.4f}")



                if avg_loss < best_score:

                    best_score = avg_loss

                    best_patch = patch.clone().detach()



                if (iteration + 1) % 10 == 0:

                    if patch.grad is not None:

                        grad_norm = patch.grad.norm().item()

                        print(f"  [DEBUG] ||patch.grad|| = {grad_norm:.6f}")

                    else:

                        print(f"  [DEBUG] WARNING: patch.grad is None!")



                optimizer.step()



                with torch.no_grad():

                    patch.data = torch.clamp(patch.data, -self.epsilon, self.epsilon)



                if (iteration + 1) % 10 == 0:

                    avg_score = score_sum_total / max(1, pred_count_total)

                    print(f"  Iteration {iteration + 1}/{self.iterations}: Loss={avg_loss:.6f}, "

                          f"SoftHits={soft_hits_total}/{pred_count_total}, "

                          f"avg_score={avg_score:.4f}")

                    if self.log_callback:
                        self.log_callback(iteration + 1, avg_loss, soft_hits_total, len(image_bbox_list))

            else:

                if (iteration + 1) % 10 == 0:

                    print(f"  Iteration {iteration + 1}/{self.iterations}: No detections")

                    if self.log_callback:
                        self.log_callback(iteration + 1, None, 0, len(image_bbox_list))



        patch_final = (torch.clamp(best_patch, -self.epsilon, self.epsilon) + 1) / 2

        patch_np = (patch_final.permute(1, 2, 0).detach().cpu().numpy() * 255).astype(np.uint8)



        return patch_np, best_score



    def compute_iou(self, box1, box2):

        x1_min, y1_min, x1_max, y1_max = box1

        x2_min, y2_min, x2_max, y2_max = box2



        inter_xmin = max(x1_min, x2_min)

        inter_ymin = max(y1_min, y2_min)

        inter_xmax = min(x1_max, x2_max)

        inter_ymax = min(y1_max, y2_max)



        inter_w = max(0, inter_xmax - inter_xmin)

        inter_h = max(0, inter_ymax - inter_ymin)

        inter_area = inter_w * inter_h



        box1_area = (x1_max - x1_min) * (y1_max - y1_min)

        box2_area = (x2_max - x2_min) * (y2_max - y2_min)



        union_area = box1_area + box2_area - inter_area



        if union_area == 0:

            return 0



        iou = inter_area / union_area

        return iou





def apply_patch_to_bbox(image_path, patch, bbox):

    img = cv2.imread(str(image_path))

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)



    x1, y1, x2, y2 = map(int, bbox)

    bbox_h = y2 - y1

    bbox_w = x2 - x1



    patch_resized = cv2.resize(patch, (bbox_w, bbox_h), interpolation=cv2.INTER_LINEAR)



    img_rgb[y1:y2, x1:x2] = patch_resized



    return img_rgb





def run_global_patch_generation(target_class, model_path='yolo11n.pt', json_path='result/yolo_inference_results_20250926_170507.json'):

    output_dir = Path('adversarial_results')

    output_dir.mkdir(exist_ok=True)



    patches_dir = output_dir / 'patches'

    patches_dir.mkdir(exist_ok=True)



    adversarial_dir = output_dir / 'adversarial_images'

    adversarial_dir.mkdir(exist_ok=True)



    generator = GlobalPGDPatchGenerator(

        model_path=model_path,

        patch_size=100,

        area_ratio=0.3,

        epsilon=0.6,

        alpha=0.03,

        iterations=100,

        batch_size=8,

        input_size=640

    )



    with open(json_path, 'r') as f:

        inference_data = json.load(f)



    model = YOLO(model_path)

    class_names = model.names

    target_class_id = None

    for cid, cname in class_names.items():

        if cname == target_class:

            target_class_id = cid

            break



    if target_class_id is None:

        print(f"Error: Target class '{target_class}' not found in model classes")

        return



    print(f"Target class: {target_class} (ID: {target_class_id})")



    dataset_path = Path('dataset')



    image_bbox_list = []



    for img_data in inference_data['images']:

        filename = img_data['filename']

        detections = img_data['detections']



        target_bboxes = [det for det in detections if det['class'] == target_class]



        if not target_bboxes:

            continue



        image_path = dataset_path / filename



        for target_det in target_bboxes:

            bbox = [

                target_det['bbox']['x1'],

                target_det['bbox']['y1'],

                target_det['bbox']['x2'],

                target_det['bbox']['y2']

            ]

            image_bbox_list.append((image_path, bbox))



    if not image_bbox_list:

        print(f"No {target_class} objects found in dataset")

        return



    print(f"Total {target_class} objects found: {len(image_bbox_list)}")



    patch_np, _ = generator.generate_global_patch(image_bbox_list, target_class_id)



    patch_filename = f'global_patch_{target_class}.png'

    patch_path = patches_dir / patch_filename

    cv2.imwrite(str(patch_path), cv2.cvtColor(patch_np, cv2.COLOR_RGB2BGR))

    print(f"\nGlobal patch saved: {patch_path}")



    results_dict = {

        'model': Path(model_path).stem,

        'attack_method': 'Global PGD',

        'target_class': target_class,

        'target_class_id': target_class_id,

        'patch_config': {

            'base_patch_size': generator.base_patch_size,

            'area_ratio': generator.area_ratio,

            'epsilon': generator.epsilon,

            'alpha': generator.alpha,

            'iterations': generator.iterations,

            'batch_size': generator.batch_size

        },

        'timestamp': datetime.now().isoformat(),

        'global_patch_file': patch_filename,

        'images': []

    }



    print(f"\nApplying global patch to all images...")



    for img_data in inference_data['images']:

        filename = img_data['filename']

        detections = img_data['detections']



        target_bboxes = [det for det in detections if det['class'] == target_class]



        if not target_bboxes:

            continue



        print(f"\nProcessing: {filename} ({len(target_bboxes)} {target_class} objects)")



        image_path = dataset_path / filename



        img = cv2.imread(str(image_path))

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)



        for target_det in target_bboxes:

            bbox = [

                target_det['bbox']['x1'],

                target_det['bbox']['y1'],

                target_det['bbox']['x2'],

                target_det['bbox']['y2']

            ]



            x1, y1, x2, y2 = map(int, bbox)



            target_patch_size = generator.calculate_patch_size_for_bbox(bbox)



            patch_resized = cv2.resize(patch_np, (target_patch_size, target_patch_size), interpolation=cv2.INTER_LINEAR)



            center_x = (x1 + x2) // 2

            center_y = (y1 + y2) // 2



            patch_x1 = max(0, center_x - target_patch_size // 2)

            patch_y1 = max(0, center_y - target_patch_size // 2)

            patch_x2 = min(img_rgb.shape[1], patch_x1 + target_patch_size)

            patch_y2 = min(img_rgb.shape[0], patch_y1 + target_patch_size)



            actual_patch_w = patch_x2 - patch_x1

            actual_patch_h = patch_y2 - patch_y1



            img_rgb[patch_y1:patch_y2, patch_x1:patch_x2] = patch_resized[:actual_patch_h, :actual_patch_w]



        adv_filename = f'adversarial_{Path(filename).stem}.jpg'

        adv_path = adversarial_dir / adv_filename

        cv2.imwrite(str(adv_path), cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))



        results_adv = generator.model(img_rgb)



        original_count = len(target_bboxes)

        adversarial_count = 0



        if results_adv[0].boxes is not None:

            for box in results_adv[0].boxes:

                cls_id = int(box.cls)

                if cls_id == target_class_id:

                    for target_det in target_bboxes:

                        bbox = [

                            target_det['bbox']['x1'],

                            target_det['bbox']['y1'],

                            target_det['bbox']['x2'],

                            target_det['bbox']['y2']

                        ]

                        iou = generator.compute_iou(box.xyxy[0].cpu().numpy(), bbox)

                        if iou > 0.3:

                            adversarial_count += 1

                            break



        vis_img = img_rgb.copy()

        for r in results_adv:

            if r.boxes is not None:

                for box in r.boxes:

                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                    conf = float(box.conf)

                    cls_id = int(box.cls)

                    cls_name = generator.model.names[cls_id]



                    color = (0, 0, 255) if cls_id == target_class_id else (0, 255, 0)

                    cv2.rectangle(vis_img, (x1, y1), (x2, y2), color, 2)

                    label = f'{cls_name} {conf:.2f}'

                    cv2.putText(vis_img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)



        vis_filename = f'visualized_{Path(filename).stem}.jpg'

        vis_path = adversarial_dir / vis_filename

        cv2.imwrite(str(vis_path), cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))



        image_result = {

            'filename': filename,

            'original_detections': original_count,

            'adversarial_detections': adversarial_count,

            'reduction': original_count - adversarial_count,

            'adversarial_file': adv_filename

        }



        results_dict['images'].append(image_result)



        print(f"  Original: {original_count}, After attack: {adversarial_count}, Reduction: {original_count - adversarial_count}")



    output_file = output_dir / f'global_pgd_attack_{target_class}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

    with open(output_file, 'w', encoding='utf-8') as f:

        json.dump(results_dict, f, indent=2, ensure_ascii=False)



    print(f"\n{'='*60}")

    print(f"All results saved to: {output_file}")

    print(f"Total images processed: {len(results_dict['images'])}")



    total_original = sum(img['original_detections'] for img in results_dict['images'])

    total_adversarial = sum(img['adversarial_detections'] for img in results_dict['images'])

    total_reduction = total_original - total_adversarial



    print(f"Total original detections: {total_original}")

    print(f"Total adversarial detections: {total_adversarial}")

    print(f"Total reduction: {total_reduction}")



    if total_original > 0:

        success_rate = total_reduction / total_original

        print(f"Attack success rate: {success_rate:.2%}")



    print(f"{'='*60}")





if __name__ == "__main__":

    import sys



    if len(sys.argv) < 2:

        print("Usage: python adversarial_patch_generator.py <target_class> [model_path]")

        print("Example: python adversarial_patch_generator.py person")

        print("Example: python adversarial_patch_generator.py person yolo11n.pt")

        print("Example: python adversarial_patch_generator.py person yolov8n.pt")

        sys.exit(1)



    target_class = sys.argv[1]

    model_path = sys.argv[2] if len(sys.argv) > 2 else 'yolo11n.pt'



    run_global_patch_generation(target_class, model_path)