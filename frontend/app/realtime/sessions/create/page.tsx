'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function CreateRealtimeSessionPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    sessionName: '',
    cameraId: '',
    modelVersionId: '',
    isUnlimited: true,
    duration: 60,
    frameSampleRate: 5,
    saveFrames: true,
    confidenceThreshold: 0.5,
    iouThreshold: 0.45,
  });

  useEffect(() => {
    loadInitialData();
  }, []);

  async function loadInitialData() {
    try {
      const [camerasData, modelsData] = await Promise.all([
        apiClient.getWebcams(), // Use real webcam list instead of DB cameras
        apiClient.getModels(),
      ]);
      setCameras(camerasData);
      setModels(modelsData);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const result = await apiClient.startWebcamSession({
        run_name: formData.sessionName,
        device: formData.cameraId,
        model_version_id: formData.modelVersionId,
        fps_target: 30.0,
        window_seconds: formData.isUnlimited ? 3600 : formData.duration,
        conf_threshold: formData.confidenceThreshold,
        iou_threshold: formData.iouThreshold,
      });

      alert(`Live session started successfully!\n${result.message}`);
      window.location.href = `/realtime/sessions/${result.run_id}/live`;
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h2>Create Live Session</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <section>
          <h3>Step 1: Select Camera</h3>
          <div style={{ marginBottom: '15px' }}>
            <select
              value={formData.cameraId}
              onChange={(e) => setFormData({ ...formData, cameraId: e.target.value })}
              required
              style={{ width: '100%', padding: '5px' }}
            >
              <option value="">Select Camera</option>
              {cameras.map((camera) => (
                <option key={camera.device} value={camera.device}>
                  {camera.name} ({camera.backend})
                  {camera.resolution && ` - ${camera.resolution}`}
                  {camera.fps && ` @ ${camera.fps} FPS`}
                </option>
              ))}
            </select>
          </div>
        </section>

        <section>
          <h3>Step 2: Configure Session</h3>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Session Name *
              <br />
              <input
                type="text"
                value={formData.sessionName}
                onChange={(e) => setFormData({ ...formData, sessionName: e.target.value })}
                required
                style={{ width: '100%', padding: '5px' }}
              />
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Detection Model *
              <br />
              <select
                value={formData.modelVersionId}
                onChange={(e) => setFormData({ ...formData, modelVersionId: e.target.value })}
                required
                style={{ width: '100%', padding: '5px' }}
              >
                <option value="">Select Model</option>
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} v{model.version}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <h4>Session Duration</h4>
            <label>
              <input
                type="radio"
                checked={formData.isUnlimited}
                onChange={() => setFormData({ ...formData, isUnlimited: true })}
              />
              {' '}Unlimited (manual stop)
            </label>
            <br />
            <label>
              <input
                type="radio"
                checked={!formData.isUnlimited}
                onChange={() => setFormData({ ...formData, isUnlimited: false })}
              />
              {' '}Fixed duration: {' '}
              <input
                type="number"
                min="1"
                value={formData.duration}
                onChange={(e) => setFormData({ ...formData, duration: parseInt(e.target.value) })}
                disabled={formData.isUnlimited}
                style={{ padding: '5px' }}
              />
              {' '}seconds
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <h4>Recording Options</h4>
            <label>
              <input
                type="checkbox"
                checked={formData.saveFrames}
                onChange={(e) => setFormData({ ...formData, saveFrames: e.target.checked })}
              />
              {' '}Save frames to disk
            </label>
            {formData.saveFrames && (
              <div style={{ marginTop: '10px', marginLeft: '20px' }}>
                <label>
                  Frame Sample Rate: Every {' '}
                  <input
                    type="number"
                    min="1"
                    value={formData.frameSampleRate}
                    onChange={(e) => setFormData({ ...formData, frameSampleRate: parseInt(e.target.value) })}
                    style={{ padding: '5px', width: '60px' }}
                  />
                  {' '}frames
                </label>
              </div>
            )}
          </div>

          <div style={{ marginBottom: '15px' }}>
            <h4>Detection Parameters</h4>
            <div style={{ marginBottom: '10px' }}>
              <label>
                Confidence Threshold
                <br />
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={formData.confidenceThreshold}
                  onChange={(e) => setFormData({ ...formData, confidenceThreshold: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
            <div>
              <label>
                IOU Threshold
                <br />
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={formData.iouThreshold}
                  onChange={(e) => setFormData({ ...formData, iouThreshold: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
          </div>
        </section>

        <div>
          <button type="button" onClick={() => window.history.back()}>
            Cancel
          </button>
          {' '}
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Starting...' : 'Start Session'}
          </button>
        </div>
      </form>
    </div>
  );
}
