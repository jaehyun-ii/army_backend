'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function EvaluationRunPage({ params }: { params: { runId: string } }) {
  const [run, setRun] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRunDetails();
    const interval = setInterval(loadRunDetails, 2000);
    return () => clearInterval(interval);
  }, []);

  async function loadRunDetails() {
    try {
      const data = await apiClient.getEvaluationRun(params.runId);
      setRun(data);

      if (data.status === 'completed' || data.status === 'failed') {
        setIsLoading(false);
      }
    } catch (err: any) {
      setError(err.message);
      setIsLoading(false);
    }
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!run) {
    return <div>Loading evaluation run...</div>;
  }

  const isRunning = run.status === 'running' || run.status === 'queued';

  return (
    <div>
      <h2>{isRunning ? 'Evaluation in Progress' : 'Evaluation Results'}</h2>

      <section>
        <h3>Run Information</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>Name:</strong></td>
              <td>{run.name || 'Unnamed Evaluation'}</td>
            </tr>
            <tr>
              <td><strong>Status:</strong></td>
              <td>{run.status}</td>
            </tr>
            <tr>
              <td><strong>Phase:</strong></td>
              <td>{run.phase}</td>
            </tr>
            <tr>
              <td><strong>Created:</strong></td>
              <td>{new Date(run.created_at).toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {run.metrics && (
        <section>
          <h3>Metrics</h3>
          <table border={1} cellPadding={5}>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {run.metrics.mAP !== undefined && (
                <tr>
                  <td>mAP</td>
                  <td>{run.metrics.mAP.toFixed(3)}</td>
                </tr>
              )}
              {run.metrics.precision !== undefined && (
                <tr>
                  <td>Precision</td>
                  <td>{run.metrics.precision.toFixed(3)}</td>
                </tr>
              )}
              {run.metrics.recall !== undefined && (
                <tr>
                  <td>Recall</td>
                  <td>{run.metrics.recall.toFixed(3)}</td>
                </tr>
              )}
              {run.metrics.f1_score !== undefined && (
                <tr>
                  <td>F1 Score</td>
                  <td>{run.metrics.f1_score.toFixed(3)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      )}

      {isRunning && (
        <section>
          <p>Evaluation is still running. This page will update automatically.</p>
        </section>
      )}

      {run.status === 'completed' && (
        <section>
          <h3>Next Actions</h3>
          <div>
            <button onClick={() => window.location.href = '/evaluation/create'}>
              Run New Evaluation
            </button>
            {' '}
            <button onClick={() => window.location.href = '/evaluation/compare'}>
              Compare Results
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
