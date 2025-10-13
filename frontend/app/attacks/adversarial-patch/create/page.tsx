'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function CreatePatchPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [topClasses, setTopClasses] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const [formData, setFormData] = useState({
    patchName: '',
    datasetId: '',
    modelVersionId: '',
    targetClass: '',
    description: '',
  });

  useEffect(() => {
    loadInitialData();
  }, []);

  async function loadInitialData() {
    try {
      const [datasetsData, modelsData] = await Promise.all([
        apiClient.getDatasets(),
        apiClient.getModels(),
      ]);
      setDatasets(datasetsData);
      setModels(modelsData);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleDatasetChange(datasetId: string) {
    setFormData({ ...formData, datasetId });

    if (datasetId) {
      try {
        const data = await apiClient.getDatasetTopClasses(datasetId);
        if (data.source === 'metadata') {
          setTopClasses(data.top_classes || []);
        } else {
          setTopClasses([]);
        }
      } catch (err) {
        console.error('Failed to load top classes:', err);
        setTopClasses([]);
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setLogs([]);

    // Generate unique session ID
    const sessionId = `patch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    try {
      // Connect to SSE (Server-Sent Events)
      const sseUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/adversarial-patch/patches/${sessionId}/events`;
      const eventSource = new EventSource(sseUrl);

      setLogs(prev => [...prev, '🔌 Connecting to server...']);

      eventSource.onopen = () => {
        setLogs(prev => [...prev, '✅ Connected to server']);
      };

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const timestamp = new Date(data.timestamp).toLocaleTimeString();
        const emoji = data.type === 'success' ? '✅' : data.type === 'status' ? '⚙️' : data.type === 'progress' ? '📊' : 'ℹ️';
        setLogs(prev => [...prev, `${emoji} [${timestamp}] ${data.message}`]);
      };

      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
      };

      // Start patch generation
      setLogs(prev => [...prev, '🚀 Starting patch generation...']);
      const result = await apiClient.generatePatch({
        patch_name: formData.patchName,
        model_version_id: formData.modelVersionId,
        dataset_id: formData.datasetId,
        target_class: formData.targetClass,
        description: formData.description,
        session_id: sessionId,
      });

      // Keep SSE open for a moment to receive final messages
      await new Promise(resolve => setTimeout(resolve, 1000));
      eventSource.close();

      alert('Patch generated successfully!');
      window.location.href = `/attacks/adversarial-patch/result/${result.patch.id}`;
    } catch (err: any) {
      setError(err.message);
      setLogs(prev => [...prev, `❌ Error: ${err.message}`]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h2>Create Adversarial Patch</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div>
          <h3>Basic Configuration</h3>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Patch Name *
              <br />
              <input
                type="text"
                value={formData.patchName}
                onChange={(e) => setFormData({ ...formData, patchName: e.target.value })}
                required
                style={{ width: '100%', padding: '5px' }}
              />
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Source Dataset *
              <br />
              <select
                value={formData.datasetId}
                onChange={(e) => handleDatasetChange(e.target.value)}
                required
                style={{ width: '100%', padding: '5px' }}
              >
                <option value="">Select Dataset</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name} ({dataset.image_count || 0} images)
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Target Model *
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
            <label>
              Target Class *
              <br />
              {topClasses.length > 0 ? (
                <div>
                  <p>Top classes in selected dataset:</p>
                  <select
                    value={formData.targetClass}
                    onChange={(e) => setFormData({ ...formData, targetClass: e.target.value })}
                    required
                    style={{ width: '100%', padding: '5px' }}
                  >
                    <option value="">Select Class</option>
                    {topClasses.map((cls) => (
                      <option key={cls.class_name} value={cls.class_name}>
                        {cls.class_name} ({cls.count} detections, {cls.percentage?.toFixed(2)}%)
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <input
                  type="text"
                  value={formData.targetClass}
                  onChange={(e) => setFormData({ ...formData, targetClass: e.target.value })}
                  placeholder="Enter target class (e.g., person)"
                  required
                  style={{ width: '100%', padding: '5px' }}
                />
              )}
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Description (Optional)
              <br />
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                style={{ width: '100%', padding: '5px' }}
              />
            </label>
          </div>

          <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f0f0f0' }}>
            <p>
              <strong>Note:</strong> Training parameters are managed by the system.
              <br />
              Default: patch_size=100px, epsilon=0.6, iterations=100
            </p>
          </div>

          {logs.length > 0 && (
            <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f9f9f9', border: '1px solid #ddd', maxHeight: '300px', overflowY: 'auto' }}>
              <h4>Generation Logs:</h4>
              <div style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                {logs.map((log, index) => (
                  <div key={index} style={{ marginBottom: '4px' }}>
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <button type="button" onClick={() => window.history.back()} disabled={isLoading}>
              Cancel
            </button>
            {' '}
            <button type="submit" disabled={isLoading}>
              {isLoading ? 'Generating...' : 'Generate Patch'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
