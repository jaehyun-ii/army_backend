'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function EvaluationHistoryPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState({
    phase: 'all',
    status: 'all',
  });

  useEffect(() => {
    loadEvaluationRuns();
  }, []);

  async function loadEvaluationRuns() {
    try {
      const data = await apiClient.listEvaluationRuns();
      setRuns(Array.isArray(data) ? data : data.items || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  const filteredRuns = runs.filter(run => {
    if (filter.phase !== 'all' && run.phase !== filter.phase) return false;
    if (filter.status !== 'all' && run.status !== filter.status) return false;
    return true;
  });

  if (isLoading) {
    return <div>Loading evaluation history...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Evaluation History</h2>

      <section style={{ marginBottom: '20px' }}>
        <h3>Filters</h3>
        <div>
          <label>
            Phase: {' '}
            <select
              value={filter.phase}
              onChange={(e) => setFilter({ ...filter, phase: e.target.value })}
              style={{ padding: '5px' }}
            >
              <option value="all">All</option>
              <option value="pre_attack">Pre-Attack</option>
              <option value="post_attack">Post-Attack</option>
            </select>
          </label>
          {' '}
          <label>
            Status: {' '}
            <select
              value={filter.status}
              onChange={(e) => setFilter({ ...filter, status: e.target.value })}
              style={{ padding: '5px' }}
            >
              <option value="all">All</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="aborted">Aborted</option>
            </select>
          </label>
        </div>
      </section>

      {filteredRuns.length === 0 ? (
        <p>No evaluation runs found</p>
      ) : (
        <table border={1} cellPadding={5} style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Phase</th>
              <th>Status</th>
              <th>Model</th>
              <th>Created</th>
              <th>Metrics</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((run) => (
              <tr key={run.id}>
                <td>{run.name || 'Unnamed'}</td>
                <td>{run.phase}</td>
                <td>{run.status}</td>
                <td>{run.model_version?.name || 'N/A'}</td>
                <td>{new Date(run.created_at).toLocaleString()}</td>
                <td>
                  {run.metrics ? (
                    <small>
                      mAP: {run.metrics.mAP?.toFixed(3) || 'N/A'}
                      <br />
                      F1: {run.metrics.f1_score?.toFixed(3) || 'N/A'}
                    </small>
                  ) : (
                    'N/A'
                  )}
                </td>
                <td>
                  <a href={`/evaluation/runs/${run.id}`}>View</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: '20px' }}>
        <button onClick={() => window.location.href = '/evaluation/create'}>
          New Evaluation
        </button>
        {' '}
        <button onClick={() => window.location.href = '/evaluation/compare'}>
          Compare Results
        </button>
      </div>
    </div>
  );
}
