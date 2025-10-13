"""
Real-time video capture and inference service.
"""
import cv2
import numpy as np
import asyncio
import time
from typing import Optional, Dict, Any, AsyncGenerator
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.services.custom_model_service import custom_model_service
from app.crud.model_repo import crud_model_version
from app.models.realtime import RTRunStatus

logger = logging.getLogger(__name__)


class RealtimeService:
    """Service for real-time webcam capture and inference."""

    def __init__(self):
        self.active_captures = {}  # run_id -> VideoCapture mapping

    async def start_capture(
        self,
        db: AsyncSession,
        camera_device: str,
        model_version_id: UUID,
        run_id: UUID,
        fps_target: float = 30.0,
        window_seconds: int = 5,
    ) -> Dict[str, Any]:
        """
        Start real-time video capture from webcam.

        Args:
            db: Database session
            camera_device: Camera device path (e.g., /dev/video0)
            model_version_id: Model version to use for inference
            run_id: Capture run ID
            fps_target: Target frames per second
            window_seconds: Duration in seconds

        Returns:
            Capture statistics
        """
        # Verify model exists
        model_version = await crud_model_version.get_version(db, model_version_id)
        if not model_version:
            raise ValueError(f"Model version {model_version_id} not found")

        # Load model if not already loaded
        try:
            await custom_model_service.load_model(str(model_version_id))
        except Exception as e:
            logger.warning(f"Model not loaded, attempting to load: {e}")
            # Model might already be loaded, continue

        # Open video capture
        try:
            # Convert device to integer if it's a numeric string
            try:
                device_index = int(camera_device)
                cap = cv2.VideoCapture(device_index)
            except ValueError:
                # Not a number, treat as device path (e.g., /dev/video0)
                cap = cv2.VideoCapture(camera_device)

            if not cap.isOpened():
                raise RuntimeError(f"Failed to open camera device: {camera_device}")

            # Set camera properties
            cap.set(cv2.CAP_PROP_FPS, fps_target)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            self.active_captures[str(run_id)] = cap

            logger.info(f"Started capture for run {run_id} on device {camera_device}")

            return {
                "run_id": str(run_id),
                "camera_device": camera_device,
                "model_version_id": str(model_version_id),
                "fps_target": fps_target,
                "window_seconds": window_seconds,
                "status": "started"
            }

        except Exception as e:
            logger.error(f"Error starting capture: {e}")
            raise

    async def capture_and_infer(
        self,
        run_id: UUID,
        model_version_id: UUID,
        max_frames: Optional[int] = None,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Capture frames and run inference in real-time.

        Args:
            run_id: Capture run ID
            model_version_id: Model version ID
            max_frames: Maximum number of frames to capture (None = unlimited)
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS

        Yields:
            Frame results with detections
        """
        run_id_str = str(run_id)
        cap = self.active_captures.get(run_id_str)

        if not cap:
            raise ValueError(f"No active capture for run {run_id}")

        frame_count = 0
        start_time = time.time()

        try:
            while True:
                # Check max frames limit
                if max_frames and frame_count >= max_frames:
                    break

                # Read frame
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Failed to read frame {frame_count}")
                    break

                frame_count += 1
                capture_time = time.time()

                # Run inference
                try:
                    inference_start = time.time()
                    result = await custom_model_service.run_inference(
                        version_id=str(model_version_id),
                        image=frame,
                        conf_threshold=conf_threshold,
                        iou_threshold=iou_threshold
                    )
                    inference_time = (time.time() - inference_start) * 1000

                    # Calculate FPS
                    elapsed = time.time() - start_time
                    current_fps = frame_count / elapsed if elapsed > 0 else 0

                    # Format detections
                    detections = [
                        {
                            "bbox": {
                                "x1": det.bbox.x1,
                                "y1": det.bbox.y1,
                                "x2": det.bbox.x2,
                                "y2": det.bbox.y2
                            },
                            "class_id": det.class_id,
                            "class_name": det.class_name,
                            "confidence": det.confidence
                        }
                        for det in result.detections
                    ]

                    yield {
                        "run_id": run_id_str,
                        "frame_number": frame_count,
                        "timestamp": capture_time,
                        "detections": detections,
                        "num_detections": len(detections),
                        "inference_time_ms": inference_time,
                        "current_fps": round(current_fps, 2),
                        "frame_shape": frame.shape
                    }

                except Exception as e:
                    logger.error(f"Inference error on frame {frame_count}: {e}")
                    yield {
                        "run_id": run_id_str,
                        "frame_number": frame_count,
                        "timestamp": capture_time,
                        "error": str(e),
                        "status": "failed"
                    }

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.001)

        finally:
            total_time = time.time() - start_time
            avg_fps = frame_count / total_time if total_time > 0 else 0

            logger.info(
                f"Capture complete: {frame_count} frames in {total_time:.2f}s "
                f"(avg FPS: {avg_fps:.2f})"
            )

    async def stop_capture(self, run_id: UUID) -> Dict[str, Any]:
        """
        Stop an active capture.

        Args:
            run_id: Capture run ID

        Returns:
            Stop status
        """
        run_id_str = str(run_id)
        cap = self.active_captures.get(run_id_str)

        if not cap:
            raise ValueError(f"No active capture for run {run_id}")

        # Release camera
        cap.release()
        del self.active_captures[run_id_str]

        logger.info(f"Stopped capture for run {run_id}")

        return {
            "run_id": run_id_str,
            "status": "stopped"
        }

    async def get_camera_info(self, camera_device: str) -> Dict[str, Any]:
        """
        Get camera device information.

        Args:
            camera_device: Camera device path (e.g., /dev/video0)

        Returns:
            Camera information
        """
        try:
            cap = cv2.VideoCapture(camera_device)
            if not cap.isOpened():
                raise RuntimeError(f"Failed to open camera device: {camera_device}")

            info = {
                "device": camera_device,
                "backend": cap.getBackendName(),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "fourcc": int(cap.get(cv2.CAP_PROP_FOURCC)),
                "brightness": cap.get(cv2.CAP_PROP_BRIGHTNESS),
                "contrast": cap.get(cv2.CAP_PROP_CONTRAST),
                "saturation": cap.get(cv2.CAP_PROP_SATURATION),
                "is_opened": cap.isOpened()
            }

            cap.release()
            return info

        except Exception as e:
            logger.error(f"Error getting camera info: {e}")
            raise

    async def list_available_cameras(self) -> list:
        """
        List available camera devices (cross-platform).

        Returns:
            List of available camera devices
        """
        available = []

        # Use index-based access (works on Linux, macOS, Windows)
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    # Get camera properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)

                    available.append({
                        "device": str(i),
                        "index": i,
                        "backend": cap.getBackendName(),
                        "name": f"Camera {i}",
                        "resolution": f"{width}x{height}",
                        "fps": fps
                    })
                    cap.release()
            except Exception:
                continue

        return available


# Global service instance
realtime_service = RealtimeService()
