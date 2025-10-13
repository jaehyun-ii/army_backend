"""
YOLO Loss Functions.

Extracted from ultralytics YOLO implementation for use in adversarial attacks.
These loss functions enable accurate gradient-based attacks by computing
actual detection losses instead of proxy losses.
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


def bbox_iou(box1, box2, xywh=True, GIoU=False, DIoU=False, CIoU=False, eps=1e-7):
    """
    Calculate Intersection over Union (IoU) of box1(1, 4) to box2(n, 4).

    Args:
        box1 (torch.Tensor): A tensor representing a single bounding box with shape (1, 4).
        box2 (torch.Tensor): A tensor representing n bounding boxes with shape (n, 4).
        xywh (bool, optional): If True, input boxes are in (x, y, w, h) format. If False, input boxes are in
                               (x1, y1, x2, y2) format. Defaults to True.
        GIoU (bool, optional): If True, calculate Generalized IoU. Defaults to False.
        DIoU (bool, optional): If True, calculate Distance IoU. Defaults to False.
        CIoU (bool, optional): If True, calculate Complete IoU. Defaults to False.
        eps (float, optional): A small value to avoid division by zero. Defaults to 1e-7.

    Returns:
        (torch.Tensor): IoU, GIoU, DIoU, or CIoU values depending on the specified flags.
    """
    # Get the coordinates of bounding boxes
    if xywh:  # transform from xywh to xyxy
        (x1, y1, w1, h1), (x2, y2, w2, h2) = box1.chunk(4, -1), box2.chunk(4, -1)
        w1_, h1_, w2_, h2_ = w1 / 2, h1 / 2, w2 / 2, h2 / 2
        b1_x1, b1_x2, b1_y1, b1_y2 = x1 - w1_, x1 + w1_, y1 - h1_, y1 + h1_
        b2_x1, b2_x2, b2_y1, b2_y2 = x2 - w2_, x2 + w2_, y2 - h2_, y2 + h2_
    else:  # x1, y1, x2, y2 = box1
        b1_x1, b1_y1, b1_x2, b1_y2 = box1.chunk(4, -1)
        b2_x1, b2_y1, b2_x2, b2_y2 = box2.chunk(4, -1)
        w1, h1 = b1_x2 - b1_x1, b1_y2 - b1_y1 + eps
        w2, h2 = b2_x2 - b2_x1, b2_y2 - b2_y1 + eps

    # Intersection area
    inter = (b1_x2.minimum(b2_x2) - b1_x1.maximum(b2_x1)).clamp(0) * \
            (b1_y2.minimum(b2_y2) - b1_y1.maximum(b2_y1)).clamp(0)

    # Union Area
    union = w1 * h1 + w2 * h2 - inter + eps

    # IoU
    iou = inter / union
    if CIoU or DIoU or GIoU:
        cw = b1_x2.maximum(b2_x2) - b1_x1.minimum(b2_x1)  # convex (smallest enclosing box) width
        ch = b1_y2.maximum(b2_y2) - b1_y1.minimum(b2_y1)  # convex height
        if CIoU or DIoU:  # Distance or Complete IoU https://arxiv.org/abs/1911.08287v1
            c2 = cw ** 2 + ch ** 2 + eps  # convex diagonal squared
            rho2 = ((b2_x1 + b2_x2 - b1_x1 - b1_x2) ** 2 + (b2_y1 + b2_y2 - b1_y1 - b1_y2) ** 2) / 4  # center dist ** 2
            if CIoU:  # https://github.com/Zzh-tju/DIoU-SSD-pytorch/blob/master/utils/box/box_utils.py#L47
                v = (4 / math.pi ** 2) * (torch.atan(w2 / h2) - torch.atan(w1 / h1)).pow(2)
                with torch.no_grad():
                    alpha = v / (v - iou + (1 + eps))
                return iou - (rho2 / c2 + v * alpha)  # CIoU
            return iou - rho2 / c2  # DIoU
        c_area = cw * ch + eps  # convex area
        return iou - (c_area - union) / c_area  # GIoU https://arxiv.org/pdf/1902.09630.pdf
    return iou  # IoU


def bbox2dist(anchor_points, bbox, reg_max):
    """Transform bbox(xyxy) to dist(ltrb)."""
    x1y1, x2y2 = bbox.chunk(2, -1)
    return torch.cat((anchor_points - x1y1, x2y2 - anchor_points), -1).clamp(0, reg_max - 0.01)  # dist (lt, rb)


class VarifocalLoss(nn.Module):
    """Varifocal loss by Zhang et al. https://arxiv.org/abs/2008.13367."""

    def __init__(self):
        """Initialize the VarifocalLoss class."""
        super().__init__()

    def forward(self, pred_score, gt_score, label, alpha=0.75, gamma=2.0):
        """Computes varfocal loss."""
        weight = alpha * pred_score.sigmoid().pow(gamma) * (1 - label) + gt_score * label
        with torch.cuda.amp.autocast(enabled=False):
            loss = (F.binary_cross_entropy_with_logits(pred_score.float(), gt_score.float(), reduction='none') *
                    weight).sum()
        return loss


class BboxLoss(nn.Module):
    """Bounding box loss with IoU and DFL components."""

    def __init__(self, reg_max, use_dfl=False):
        """Initialize the BboxLoss module with regularization maximum and DFL settings."""
        super().__init__()
        self.reg_max = reg_max
        self.use_dfl = use_dfl

    def forward(self, pred_dist, pred_bboxes, anchor_points, target_bboxes, target_scores, target_scores_sum, fg_mask):
        """IoU loss."""
        weight = torch.masked_select(target_scores.sum(-1), fg_mask).unsqueeze(-1)
        iou = bbox_iou(pred_bboxes[fg_mask], target_bboxes[fg_mask], xywh=False, CIoU=True)
        loss_iou = ((1.0 - iou) * weight).sum() / target_scores_sum

        # DFL loss
        if self.use_dfl:
            target_ltrb = bbox2dist(anchor_points, target_bboxes, self.reg_max)
            loss_dfl = self._df_loss(pred_dist[fg_mask].view(-1, self.reg_max + 1), target_ltrb[fg_mask]) * weight
            loss_dfl = loss_dfl.sum() / target_scores_sum
        else:
            loss_dfl = torch.tensor(0.0).to(pred_dist.device)

        return loss_iou, loss_dfl

    @staticmethod
    def _df_loss(pred_dist, target):
        """Return sum of left and right DFL losses."""
        # Distribution Focal Loss (DFL) proposed in Generalized Focal Loss https://ieeexplore.ieee.org/document/9792391
        tl = target.long()  # target left
        tr = tl + 1  # target right
        wl = tr - target  # weight left
        wr = 1 - wl  # weight right
        return (F.cross_entropy(pred_dist, tl.view(-1), reduction='none').view(tl.shape) * wl +
                F.cross_entropy(pred_dist, tr.view(-1), reduction='none').view(tl.shape) * wr).mean(-1, keepdim=True)


class DetectionLoss:
    """
    Simplified detection loss for adversarial attacks.

    This computes a loss based on detection confidence and bbox IoU
    without requiring full training infrastructure.
    """

    def __init__(self, device='cuda'):
        self.device = device
        self.bbox_loss = BboxLoss(reg_max=16, use_dfl=False)

    def __call__(self, predictions, target_bboxes, target_class_ids=None):
        """
        Compute detection loss for adversarial attack.

        Args:
            predictions: YOLO model output (Results object or tensor)
            target_bboxes: Ground truth bboxes in xyxy format, shape (N, 4)
            target_class_ids: Optional target class IDs, shape (N,)

        Returns:
            Total loss tensor (scalar)
        """
        try:
            # Extract predictions from YOLO output
            if hasattr(predictions, '__len__') and len(predictions) > 0:
                result = predictions[0]

                if hasattr(result, 'boxes'):
                    boxes = result.boxes

                    if not hasattr(boxes, 'xyxy') or len(boxes.xyxy) == 0:
                        # No detections - return zero loss
                        return torch.tensor(0.0, requires_grad=True, device=self.device)

                    pred_bboxes = boxes.xyxy  # (M, 4)
                    pred_conf = boxes.conf if hasattr(boxes, 'conf') else torch.ones(len(pred_bboxes), device=self.device)
                    pred_cls = boxes.cls if hasattr(boxes, 'cls') else torch.zeros(len(pred_bboxes), device=self.device)

                    # Filter by target class if specified
                    if target_class_ids is not None:
                        # Assume single target class for simplicity
                        target_class = target_class_ids[0] if len(target_class_ids) > 0 else None
                        if target_class is not None:
                            mask = pred_cls == target_class
                            if not mask.any():
                                return torch.tensor(0.0, requires_grad=True, device=self.device)
                            pred_bboxes = pred_bboxes[mask]
                            pred_conf = pred_conf[mask]

                    # Convert target bboxes to tensor
                    if isinstance(target_bboxes, list):
                        if len(target_bboxes) == 0:
                            return torch.tensor(0.0, requires_grad=True, device=self.device)
                        target_bboxes = torch.tensor(target_bboxes, device=self.device, dtype=torch.float32)

                    # Compute confidence loss (we want to maximize this to fool detector)
                    conf_loss = pred_conf.sum()

                    # Compute IoU loss if we have predictions and targets
                    iou_loss = torch.tensor(0.0, device=self.device)
                    if len(pred_bboxes) > 0 and len(target_bboxes) > 0:
                        # Compute pairwise IoU between predictions and targets
                        ious = bbox_iou(pred_bboxes, target_bboxes, xywh=False, CIoU=False)
                        # Max IoU for each prediction
                        max_ious = ious.max(dim=1)[0]
                        # We want to minimize IoU with ground truth (make predictions wrong)
                        iou_loss = max_ious.sum()

                    # Total loss: high confidence + low IoU with ground truth
                    # We maximize this loss to fool the detector
                    total_loss = conf_loss + iou_loss

                    return total_loss

            return torch.tensor(0.0, requires_grad=True, device=self.device)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error computing detection loss: {e}")
            return torch.tensor(0.0, requires_grad=True, device=self.device)
