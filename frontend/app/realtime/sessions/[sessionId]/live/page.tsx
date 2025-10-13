'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function LiveSessionPage({ params }: { params: { sessionId: string } }) {
  const [isConnected, setIsConnected] = useState(false);
  const [currentFrame, setCurrentFrame] = useState<any>(null);
  const [stats, setStats] = useState({
    frameCount: 0,
    totalDetections: 0,
    fps: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<any>(null);

  // Load session info first
  useEffect(() => {
    async function loadSession() {
      try {
        const sessionData = await apiClient.getRealtimeSession(params.sessionId);
        setSession(sessionData);
      } catch (err: any) {
        setError(`Failed to load session: ${err.message}`);
      }
    }
    loadSession();
  }, [params.sessionId]);

  useEffect(() => {
    if (!session?.model_version_id) {
      return; // Wait for session to load
    }

    // Use SSE (Server-Sent Events) instead of WebSocket
    const eventSource = new EventSource(
      `http://localhost:8000/api/v1/realtime/webcam/stream/${params.sessionId}?model_version_id=${session.model_version_id}&conf_threshold=0.25&iou_threshold=0.45`
    );

    eventSource.onopen = () => {
      console.log('SSE connected');
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Check for error
        if (data.error) {
          setError(data.error);
          setIsConnected(false);
          return;
        }

        setCurrentFrame(data);

        setStats(prev => ({
          frameCount: data.frame_number || prev.frameCount,
          totalDetections: prev.totalDetections + (data.detections?.length || 0),
          fps: data.current_fps || prev.fps,
        }));
      } catch (err) {
        console.error('Failed to parse SSE data:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
      setError('Stream connection error');
      setIsConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [params.sessionId, session]);

  async function handleStop() {
    try {
      await apiClient.stopRealtimeSession(params.sessionId);
      alert('Session stopped successfully!');
      window.location.href = `/realtime/sessions/${params.sessionId}/results`;
    } catch (err: any) {
      alert(`Failed to stop session: ${err.message}`);
    }
  }

  return (
    <div>
      <h2>LIVE: Real-time Detection</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <section>
        <h3>Live Video Feed</h3>
        <div style={{
          border: '2px solid black',
          width: '640px',
          height: '480px',
          backgroundColor: '#000',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white'
        }}>
          {session?.model_version_id ? (
            <img
              src={`http://localhost:8000/api/v1/realtime/webcam/stream-mjpeg/${params.sessionId}?model_version_id=${session.model_version_id}&conf_threshold=0.25&draw_boxes=true`}
              alt="Live feed with detections"
              style={{ maxWidth: '100%', maxHeight: '100%' }}
              onError={() => setError('Failed to load video stream')}
            />
          ) : (
            'Loading...'
          )}
        </div>
      </section>

      <section>
        <h3>Session Status</h3>
        <p>Status: {isConnected ? '🔴 LIVE' : '⚫ Disconnected'}</p>
      </section>

      <section>
        <h3>Real-time Metrics</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>FPS:</strong></td>
              <td>{stats.fps.toFixed(1)}</td>
            </tr>
            <tr>
              <td><strong>Frames Processed:</strong></td>
              <td>{stats.frameCount}</td>
            </tr>
            <tr>
              <td><strong>Total Detections:</strong></td>
              <td>{stats.totalDetections}</td>
            </tr>
            <tr>
              <td><strong>Avg Det/Frame:</strong></td>
              <td>{stats.frameCount > 0 ? (stats.totalDetections / stats.frameCount).toFixed(2) : '0.00'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h3>Current Frame Detections</h3>
        {currentFrame?.detections && currentFrame.detections.length > 0 ? (
          <ul>
            {currentFrame.detections.map((det: any, idx: number) => (
              <li key={idx}>
                {det.class_name} ({(det.confidence * 100).toFixed(1)}%) -
                [{det.bbox.x1}, {det.bbox.y1}, {det.bbox.x2}, {det.bbox.y2}]
              </li>
            ))}
          </ul>
        ) : (
          <p>No detections in current frame</p>
        )}
      </section>

      <div>
        <button onClick={handleStop}>Stop Session</button>
      </div>
    </div>
  );
}
