'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function CamerasPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCameras();
  }, []);

  async function loadCameras() {
    try {
      const data = await apiClient.getCameras();
      setCameras(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading cameras...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Cameras</h2>

      {cameras.length === 0 ? (
        <p>No cameras available</p>
      ) : (
        <table border={1} cellPadding={5} style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Stream URI</th>
              <th>Resolution</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {cameras.map((camera) => (
              <tr key={camera.id}>
                <td>{camera.name}</td>
                <td>{camera.stream_uri || camera.device_id || 'N/A'}</td>
                <td>
                  {camera.resolution
                    ? `${camera.resolution.width}x${camera.resolution.height}`
                    : 'N/A'}
                </td>
                <td>{camera.is_active ? 'Active' : 'Inactive'}</td>
                <td>
                  <a href={`/realtime/sessions/create?camera=${camera.id}`}>Start Session</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: '20px' }}>
        <button onClick={() => window.location.href = '/realtime/sessions/create'}>
          Create New Session
        </button>
      </div>
    </div>
  );
}
