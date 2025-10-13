"""
Real-time performance measurement API endpoints (cleaned version).
Removed unused endpoints: WebSocket, stats, camera CRUD operations, webcam/info, webcam/start.
"""
from typing import List, Optional
from uuid import UUID
import logging
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.database import get_db
from app.services.realtime_service import realtime_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== Camera Endpoints (Read Only) ==========

@router.get("/cameras", response_model=List[schemas.CameraResponse])
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.CameraResponse]:
    """List all cameras (read only - cameras are auto-created by webcam sessions)."""
    cameras = await crud.camera.get_multi(db, skip=skip, limit=limit)
    return cameras


# ========== RT Capture Run Endpoints ==========

@router.post("/runs", response_model=schemas.RTCaptureRunResponse, status_code=status.HTTP_201_CREATED)
async def create_capture_run(
    *,
    db: AsyncSession = Depends(get_db),
    run_in: schemas.RTCaptureRunCreate,
) -> schemas.RTCaptureRunResponse:
    """Create a new RT capture run."""
    run = await crud.rt_capture_run.create(db, obj_in=run_in)
    return run


@router.get("/runs/{run_id}", response_model=schemas.RTCaptureRunResponse)
async def get_capture_run(
    *,
    db: AsyncSession = Depends(get_db),
    run_id: UUID,
) -> schemas.RTCaptureRunResponse:
    """Get an RT capture run by ID."""
    run = await crud.rt_capture_run.get(db, id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Capture run not found")
    return run


@router.get("/runs", response_model=List[schemas.RTCaptureRunResponse])
async def list_capture_runs(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.RTCaptureRunResponse]:
    """List all RT capture runs."""
    runs = await crud.rt_capture_run.get_multi(db, skip=skip, limit=limit)
    return runs


@router.put("/runs/{run_id}", response_model=schemas.RTCaptureRunResponse)
async def update_capture_run(
    *,
    db: AsyncSession = Depends(get_db),
    run_id: UUID,
    run_in: schemas.RTCaptureRunUpdate,
) -> schemas.RTCaptureRunResponse:
    """Update an RT capture run."""
    run = await crud.rt_capture_run.get(db, id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Capture run not found")
    run = await crud.rt_capture_run.update(db, db_obj=run, obj_in=run_in)
    return run


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capture_run(
    *,
    db: AsyncSession = Depends(get_db),
    run_id: UUID,
):
    """Soft delete an RT capture run."""
    success = await crud.rt_capture_run.soft_delete(db, id=run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Capture run not found")


# ========== RT Frame Endpoints ==========

@router.post("/frames", response_model=schemas.RTFrameResponse, status_code=status.HTTP_201_CREATED)
async def create_frame(
    *,
    db: AsyncSession = Depends(get_db),
    frame_in: schemas.RTFrameCreate,
) -> schemas.RTFrameResponse:
    """Create a new RT frame."""
    frame = await crud.rt_frame.create(db, obj_in=frame_in)
    return frame


@router.get("/frames/{frame_id}", response_model=schemas.RTFrameResponse)
async def get_frame(
    *,
    db: AsyncSession = Depends(get_db),
    frame_id: UUID,
) -> schemas.RTFrameResponse:
    """Get an RT frame by ID."""
    frame = await crud.rt_frame.get(db, id=frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    return frame


@router.get("/frames", response_model=List[schemas.RTFrameResponse])
async def list_frames(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.RTFrameResponse]:
    """List all RT frames."""
    frames = await crud.rt_frame.get_multi(db, skip=skip, limit=limit)
    return frames


@router.put("/frames/{frame_id}", response_model=schemas.RTFrameResponse)
async def update_frame(
    *,
    db: AsyncSession = Depends(get_db),
    frame_id: UUID,
    frame_in: schemas.RTFrameUpdate,
) -> schemas.RTFrameResponse:
    """Update an RT frame."""
    frame = await crud.rt_frame.get(db, id=frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    frame = await crud.rt_frame.update(db, db_obj=frame, obj_in=frame_in)
    return frame


@router.delete("/frames/{frame_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_frame(
    *,
    db: AsyncSession = Depends(get_db),
    frame_id: UUID,
):
    """Soft delete an RT frame."""
    success = await crud.rt_frame.soft_delete(db, id=frame_id)
    if not success:
        raise HTTPException(status_code=404, detail="Frame not found")


# ========== RT Inference Endpoints ==========

@router.post("/inferences", response_model=schemas.RTInferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_inference(
    *,
    db: AsyncSession = Depends(get_db),
    inference_in: schemas.RTInferenceCreate,
) -> schemas.RTInferenceResponse:
    """Create a new RT inference."""
    inference = await crud.rt_inference.create(db, obj_in=inference_in)
    return inference


@router.get("/inferences/{inference_id}", response_model=schemas.RTInferenceResponse)
async def get_inference(
    *,
    db: AsyncSession = Depends(get_db),
    inference_id: UUID,
) -> schemas.RTInferenceResponse:
    """Get an RT inference by ID."""
    inference = await crud.rt_inference.get(db, id=inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Inference not found")
    return inference


@router.get("/inferences", response_model=List[schemas.RTInferenceResponse])
async def list_inferences(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.RTInferenceResponse]:
    """List all RT inferences."""
    inferences = await crud.rt_inference.get_multi(db, skip=skip, limit=limit)
    return inferences


@router.put("/inferences/{inference_id}", response_model=schemas.RTInferenceResponse)
async def update_inference(
    *,
    db: AsyncSession = Depends(get_db),
    inference_id: UUID,
    inference_in: schemas.RTInferenceUpdate,
) -> schemas.RTInferenceResponse:
    """Update an RT inference."""
    inference = await crud.rt_inference.get(db, id=inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Inference not found")
    inference = await crud.rt_inference.update(db, db_obj=inference, obj_in=inference_in)
    return inference


@router.delete("/inferences/{inference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inference(
    *,
    db: AsyncSession = Depends(get_db),
    inference_id: UUID,
):
    """Soft delete an RT inference."""
    success = await crud.rt_inference.soft_delete(db, id=inference_id)
    if not success:
        raise HTTPException(status_code=404, detail="Inference not found")


# ========== Real-time Webcam Capture Endpoints ==========

@router.get("/webcam/list")
async def list_webcams():
    """
    List available webcam devices.

    Returns:
        List of available cameras with device paths
    """
    try:
        cameras = await realtime_service.list_available_cameras()
        return {
            "cameras": cameras,
            "count": len(cameras)
        }
    except Exception as e:
        logger.error(f"Error listing webcams: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list webcam devices"
        )


@router.post("/webcam/sessions/start")
async def create_and_start_webcam_session(
    *,
    db: AsyncSession = Depends(get_db),
    run_name: str = Query(..., description="Session name"),
    device: str = Query("0", description="Camera device index"),
    model_version_id: UUID = Query(..., description="Model version ID for inference"),
    fps_target: float = Query(30.0, description="Target FPS"),
    window_seconds: int = Query(300, description="Capture duration in seconds"),
    conf_threshold: float = Query(0.25, description="Confidence threshold"),
    iou_threshold: float = Query(0.45, description="IOU threshold")
):
    """
    Create a new webcam session and start capture (all-in-one endpoint).

    This endpoint:
    1. Creates or gets a Camera record for the device
    2. Creates an RTCaptureRun
    3. Starts the webcam capture

    Args:
        run_name: Name for the capture session
        device: Camera device index (0, 1, 2, ...)
        model_version_id: Model version to use for inference
        fps_target: Target frames per second
        window_seconds: Duration in seconds
        conf_threshold: Confidence threshold for detections
        iou_threshold: IOU threshold for NMS

    Returns:
        Session information with run_id
    """
    # 1. Get or create camera record for this device
    camera_name = f"Webcam {device}"
    cameras = await crud.camera.get_multi(db, skip=0, limit=100)
    camera = next((c for c in cameras if c.name == camera_name), None)

    if not camera:
        # Create new camera record with proper resolution format
        camera_data = schemas.CameraCreate(
            name=camera_name,
            description=f"Webcam device {device}",
            stream_uri=device,
            resolution={"width": 1920, "height": 1080},  # Default resolution
            is_active=True
        )
        camera = await crud.camera.create(db, obj_in=camera_data)
        logger.info(f"Created camera record for device {device}: {camera.id}")

    # 2. Create RT capture run
    run_data = schemas.RTCaptureRunCreate(
        camera_id=camera.id,
        model_version_id=model_version_id,
        window_seconds=window_seconds,
        fps_target=fps_target,
        frames_expected=int(window_seconds * fps_target),
        notes=run_name
    )
    run = await crud.rt_capture_run.create(db, obj_in=run_data)
    logger.info(f"Created capture run: {run.id}")

    # 3. Start capture
    try:
        result = await realtime_service.start_capture(
            db=db,
            camera_device=device,
            model_version_id=model_version_id,
            run_id=run.id,
            fps_target=fps_target,
            window_seconds=window_seconds
        )

        return {
            "run_id": str(run.id),
            "camera_id": str(camera.id),
            "model_version_id": str(model_version_id),
            "device": device,
            "status": "started",
            "message": f"Webcam session '{run_name}' started successfully",
            "stream_url": f"/api/v1/realtime/webcam/stream/{run.id}",
            "mjpeg_url": f"/api/v1/realtime/webcam/stream-mjpeg/{run.id}"
        }

    except Exception as e:
        logger.error(f"Error starting webcam session: {e}", exc_info=True)
        # Clean up the run record
        await crud.rt_capture_run.soft_delete(db, id=run.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start webcam session: {str(e)}"
        )


@router.get("/webcam/stream/{run_id}")
async def stream_webcam_inference(
    run_id: UUID,
    model_version_id: UUID = Query(..., description="Model version ID"),
    max_frames: Optional[int] = Query(None, description="Maximum frames to capture"),
    conf_threshold: float = Query(0.25, description="Confidence threshold"),
    iou_threshold: float = Query(0.45, description="IOU threshold")
):
    """
    Stream real-time inference results from webcam (SSE format).

    This endpoint returns Server-Sent Events (SSE) stream with inference results.

    Args:
        run_id: Capture run ID
        model_version_id: Model version ID
        max_frames: Maximum number of frames (None = unlimited)
        conf_threshold: Confidence threshold for detections
        iou_threshold: IOU threshold for NMS

    Returns:
        SSE stream of inference results
    """
    async def generate():
        try:
            async for result in realtime_service.capture_and_infer(
                run_id=run_id,
                model_version_id=model_version_id,
                max_frames=max_frames,
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold
            ):
                # Send as Server-Sent Event
                yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            error_data = {
                "error": str(e),
                "run_id": str(run_id),
                "status": "error"
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/webcam/stream-mjpeg/{run_id}")
async def stream_webcam_mjpeg(
    run_id: UUID,
    model_version_id: UUID = Query(..., description="Model version ID"),
    conf_threshold: float = Query(0.25, description="Confidence threshold"),
    draw_boxes: bool = Query(True, description="Draw bounding boxes on frames")
):
    """
    Stream real-time video with detection overlay (MJPEG format).

    This endpoint returns Motion JPEG stream for displaying in <img> tag.

    Args:
        run_id: Capture run ID
        model_version_id: Model version ID
        conf_threshold: Confidence threshold for detections
        draw_boxes: Whether to draw bounding boxes

    Returns:
        MJPEG stream (multipart/x-mixed-replace)
    """
    import cv2
    import asyncio

    def generate_frames():
        """Generate MJPEG frames with detection overlay."""
        run_id_str = str(run_id)
        cap = realtime_service.active_captures.get(run_id_str)

        if not cap:
            logger.error(f"No active capture for run {run_id}")
            return

        frame_count = 0

        while True:
            try:
                # Read frame
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Failed to read frame {frame_count}")
                    break

                frame_count += 1

                # Run inference if detection enabled
                if draw_boxes:
                    try:
                        # Import here to avoid circular dependency
                        from app.services.custom_model_service import custom_model_service

                        # Run inference
                        result = asyncio.run(custom_model_service.run_inference(
                            version_id=str(model_version_id),
                            image=frame,
                            conf_threshold=conf_threshold,
                            iou_threshold=0.45
                        ))

                        # Draw bounding boxes
                        for det in result.detections:
                            x1, y1 = int(det.bbox.x1), int(det.bbox.y1)
                            x2, y2 = int(det.bbox.x2), int(det.bbox.y2)

                            # Draw rectangle
                            color = (0, 255, 0)  # Green
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                            # Draw label
                            label = f'{det.class_name} {det.confidence:.2f}'
                            label_size, _ = cv2.getTextSize(
                                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
                            )

                            # Background for label
                            cv2.rectangle(
                                frame,
                                (x1, y1 - label_size[1] - 10),
                                (x1 + label_size[0], y1),
                                color,
                                -1
                            )

                            # Label text
                            cv2.putText(
                                frame,
                                label,
                                (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (0, 0, 0),
                                2
                            )

                    except Exception as e:
                        logger.error(f"Detection error on frame {frame_count}: {e}")

                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue

                frame_bytes = buffer.tobytes()

                # Yield as MJPEG frame
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                # Control frame rate (~30 FPS)
                import time
                time.sleep(0.033)

            except Exception as e:
                logger.error(f"Error generating frame: {e}")
                break

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.post("/webcam/stop/{run_id}")
async def stop_webcam_capture(run_id: UUID):
    """
    Stop an active webcam capture.

    Args:
        run_id: Capture run ID

    Returns:
        Stop confirmation
    """
    try:
        result = await realtime_service.stop_capture(run_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error stopping webcam capture: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop webcam capture"
        )


# Note: The following endpoints were removed as they are not used by the frontend:
# - Camera POST, PUT, DELETE (cameras are auto-created by webcam sessions)
# - GET /webcam/info (device info not needed by frontend)
# - POST /webcam/start/{run_id} (replaced by sessions/start)
# - GET /stats/current, GET /stats/stream (system metrics not used)
# - WebSocket /ws/frames, /ws/detections (frontend uses SSE instead)
