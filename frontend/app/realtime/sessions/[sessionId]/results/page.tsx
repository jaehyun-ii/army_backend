'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function SessionResultsPage({ params }: { params: { sessionId: string } }) {
  const [session, setSession] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSessionResults();
  }, []);

  async function loadSessionResults() {
    try {
      const data = await apiClient.getRealtimeSession(params.sessionId);
      setSession(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading session results...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Session Results: {session?.run_name || 'Unnamed Session'}</h2>

      <section>
        <h3>Session Summary</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>Started:</strong></td>
              <td>{new Date(session?.started_at || session?.created_at).toLocaleString()}</td>
            </tr>
            <tr>
              <td><strong>Ended:</strong></td>
              <td>{session?.ended_at ? new Date(session.ended_at).toLocaleString() : 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Duration:</strong></td>
              <td>{session?.duration ? `${session.duration}s` : 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Status:</strong></td>
              <td>{session?.status || 'completed'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {session?.statistics && (
        <section>
          <h3>Performance Statistics</h3>
          <table border={1} cellPadding={5}>
            <tbody>
              <tr>
                <td><strong>Total Frames:</strong></td>
                <td>{session.statistics.total_frames || 0}</td>
              </tr>
              <tr>
                <td><strong>Average FPS:</strong></td>
                <td>{session.statistics.avg_fps?.toFixed(1) || 'N/A'}</td>
              </tr>
              <tr>
                <td><strong>Total Detections:</strong></td>
                <td>{session.statistics.total_detections || 0}</td>
              </tr>
              <tr>
                <td><strong>Avg Det/Frame:</strong></td>
                <td>{session.statistics.avg_det_per_frame?.toFixed(2) || 'N/A'}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {session?.class_stats && (
        <section>
          <h3>Class-wise Statistics</h3>
          <table border={1} cellPadding={5}>
            <thead>
              <tr>
                <th>Class</th>
                <th>Count</th>
                <th>Percentage</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(session.class_stats).map(([className, count]: [string, any]) => (
                <tr key={className}>
                  <td>{className}</td>
                  <td>{count}</td>
                  <td>{((count / session.statistics.total_detections) * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h3>Next Actions</h3>
        <div>
          <button onClick={() => window.location.href = '/realtime/sessions/create'}>
            New Session
          </button>
        </div>
      </section>
    </div>
  );
}
