'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function CompareEvaluationPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<any>(null);

  const [formData, setFormData] = useState({
    preAttackRunId: '',
    postAttackRunId: '',
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
    }
  }

  async function handleCompare(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const result = await apiClient.compareEvaluationRuns({
        pre_attack_run_id: formData.preAttackRunId,
        post_attack_run_id: formData.postAttackRunId,
      });
      setComparison(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  const preAttackRuns = runs.filter(r => r.phase === 'pre_attack');
  const postAttackRuns = runs.filter(r => r.phase === 'post_attack');

  return (
    <div>
      <h2>Compare Evaluation Results</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleCompare}>
        <div style={{ marginBottom: '15px' }}>
          <label>
            Pre-Attack Run
            <br />
            <select
              value={formData.preAttackRunId}
              onChange={(e) => setFormData({ ...formData, preAttackRunId: e.target.value })}
              required
              style={{ width: '100%', padding: '5px' }}
            >
              <option value="">Select Pre-Attack Run</option>
              {preAttackRuns.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.name || run.id} - {new Date(run.created_at).toLocaleDateString()}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Post-Attack Run
            <br />
            <select
              value={formData.postAttackRunId}
              onChange={(e) => setFormData({ ...formData, postAttackRunId: e.target.value })}
              required
              style={{ width: '100%', padding: '5px' }}
            >
              <option value="">Select Post-Attack Run</option>
              {postAttackRuns.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.name || run.id} - {new Date(run.created_at).toLocaleDateString()}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Comparing...' : 'Compare'}
        </button>
      </form>

      {comparison && (
        <section style={{ marginTop: '30px' }}>
          <h3>Comparison Results</h3>

          <table border={1} cellPadding={5}>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Pre-Attack</th>
                <th>Post-Attack</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {comparison.metrics && Object.entries(comparison.metrics).map(([metric, values]: [string, any]) => (
                <tr key={metric}>
                  <td>{metric}</td>
                  <td>{values.pre?.toFixed(3) || 'N/A'}</td>
                  <td>{values.post?.toFixed(3) || 'N/A'}</td>
                  <td>
                    {values.delta !== undefined ? (
                      <span style={{ color: values.delta < 0 ? 'red' : 'green' }}>
                        {values.delta > 0 ? '+' : ''}{(values.delta * 100).toFixed(1)}%
                      </span>
                    ) : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {comparison.attack_success_rate !== undefined && (
            <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#f0f0f0' }}>
              <strong>Attack Success Rate:</strong> {(comparison.attack_success_rate * 100).toFixed(1)}%
            </div>
          )}
        </section>
      )}
    </div>
  );
}
