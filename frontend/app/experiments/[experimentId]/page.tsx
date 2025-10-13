'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function ExperimentPage({ params }: { params: { experimentId: string } }) {
  const [experiment, setExperiment] = useState<any>(null);
  const [showAddRun, setShowAddRun] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [runFormData, setRunFormData] = useState({
    runName: '',
    parametersJson: '{}',
    metricsJson: '{}',
    artifactsJson: '{}',
  });

  useEffect(() => {
    loadExperiment();
  }, []);

  async function loadExperiment() {
    try {
      const data = await apiClient.getExperiment(params.experimentId);
      setExperiment(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAddRun(e: React.FormEvent) {
    e.preventDefault();

    try {
      const parameters = JSON.parse(runFormData.parametersJson);
      const metrics = JSON.parse(runFormData.metricsJson);
      const artifacts = JSON.parse(runFormData.artifactsJson);

      await apiClient.addExperimentRun(params.experimentId, {
        run_name: runFormData.runName,
        parameters,
        metrics,
        artifacts,
      });

      alert('Run added successfully!');
      setShowAddRun(false);
      loadExperiment();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  }

  if (isLoading) {
    return <div>Loading experiment...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Experiment: {experiment?.name}</h2>

      <section>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>Status:</strong></td>
              <td>{experiment?.status || 'active'}</td>
            </tr>
            <tr>
              <td><strong>Created:</strong></td>
              <td>{new Date(experiment?.created_at).toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {experiment?.description && (
        <section>
          <h3>Description</h3>
          <p>{experiment.description}</p>
        </section>
      )}

      {experiment?.hypothesis && (
        <section>
          <h3>Hypothesis</h3>
          <p>{experiment.hypothesis}</p>
        </section>
      )}

      {experiment?.parameters && (
        <section>
          <h3>Parameters</h3>
          <pre style={{ backgroundColor: '#f0f0f0', padding: '10px' }}>
            {JSON.stringify(experiment.parameters, null, 2)}
          </pre>
        </section>
      )}

      <section>
        <h3>Runs</h3>
        {experiment?.runs && experiment.runs.length > 0 ? (
          <table border={1} cellPadding={5} style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Run Name</th>
                <th>Parameters</th>
                <th>Metrics</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {experiment.runs.map((run: any) => (
                <tr key={run.id}>
                  <td>{run.run_name}</td>
                  <td>
                    <pre style={{ margin: 0 }}>{JSON.stringify(run.parameters, null, 2)}</pre>
                  </td>
                  <td>
                    <pre style={{ margin: 0 }}>{JSON.stringify(run.metrics, null, 2)}</pre>
                  </td>
                  <td>{new Date(run.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No runs yet</p>
        )}
      </section>

      <section>
        <button onClick={() => setShowAddRun(!showAddRun)}>
          {showAddRun ? 'Cancel' : 'Add New Run'}
        </button>
      </section>

      {showAddRun && (
        <section style={{ border: '1px solid black', padding: '20px', marginTop: '20px' }}>
          <h3>Add Experiment Run</h3>
          <form onSubmit={handleAddRun}>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Run Name *
                <br />
                <input
                  type="text"
                  value={runFormData.runName}
                  onChange={(e) => setRunFormData({ ...runFormData, runName: e.target.value })}
                  required
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Parameters (JSON)
                <br />
                <textarea
                  value={runFormData.parametersJson}
                  onChange={(e) => setRunFormData({ ...runFormData, parametersJson: e.target.value })}
                  rows={4}
                  style={{ width: '100%', padding: '5px', fontFamily: 'monospace' }}
                  placeholder='{"patch_size": 150}'
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Metrics (JSON)
                <br />
                <textarea
                  value={runFormData.metricsJson}
                  onChange={(e) => setRunFormData({ ...runFormData, metricsJson: e.target.value })}
                  rows={4}
                  style={{ width: '100%', padding: '5px', fontFamily: 'monospace' }}
                  placeholder='{"attack_success_rate": 0.82, "detection_drop": 0.73}'
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Artifacts (JSON)
                <br />
                <textarea
                  value={runFormData.artifactsJson}
                  onChange={(e) => setRunFormData({ ...runFormData, artifactsJson: e.target.value })}
                  rows={3}
                  style={{ width: '100%', padding: '5px', fontFamily: 'monospace' }}
                  placeholder='{"patch_id": "abc123", "evaluation_run_id": "def456"}'
                />
              </label>
            </div>

            <div>
              <button type="button" onClick={() => setShowAddRun(false)}>
                Cancel
              </button>
              {' '}
              <button type="submit">Add Run</button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}
