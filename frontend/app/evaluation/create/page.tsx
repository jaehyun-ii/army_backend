'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function CreateEvaluationPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    evaluationName: '',
    evaluationType: 'pre_attack' as 'pre_attack' | 'post_attack',
    modelVersionId: '',
    datasetId: '',
    confidenceThreshold: 0.25,
    iouThreshold: 0.5,
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const requestBody: any = {
        name: formData.evaluationName,
        phase: formData.evaluationType,
        model_version_id: formData.modelVersionId,
        config: {
          confidence_threshold: formData.confidenceThreshold,
          iou_threshold: formData.iouThreshold,
        },
      };

      if (formData.evaluationType === 'pre_attack') {
        requestBody.base_dataset_id = formData.datasetId;
      } else {
        requestBody.attack_dataset_id = formData.datasetId;
      }

      const result = await apiClient.createEvaluationRun(requestBody);

      alert('Evaluation started successfully!');
      window.location.href = `/evaluation/runs/${result.id}`;
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h2>Create Evaluation Run</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <section>
          <h3>Evaluation Type</h3>
          <div>
            <label>
              <input
                type="radio"
                value="pre_attack"
                checked={formData.evaluationType === 'pre_attack'}
                onChange={(e) => setFormData({ ...formData, evaluationType: e.target.value as any })}
              />
              {' '}Pre-Attack (Baseline)
              <br />
              <small>Evaluate model on clean dataset</small>
            </label>
          </div>
          <div>
            <label>
              <input
                type="radio"
                value="post_attack"
                checked={formData.evaluationType === 'post_attack'}
                onChange={(e) => setFormData({ ...formData, evaluationType: e.target.value as any })}
              />
              {' '}Post-Attack
              <br />
              <small>Evaluate model on adversarial dataset</small>
            </label>
          </div>
        </section>

        <section>
          <h3>Configuration</h3>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Evaluation Name *
              <br />
              <input
                type="text"
                value={formData.evaluationName}
                onChange={(e) => setFormData({ ...formData, evaluationName: e.target.value })}
                required
                style={{ width: '100%', padding: '5px' }}
              />
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
              Dataset *
              <br />
              <select
                value={formData.datasetId}
                onChange={(e) => setFormData({ ...formData, datasetId: e.target.value })}
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
        </section>

        <section>
          <h3>Evaluation Parameters</h3>

          <div style={{ marginBottom: '15px' }}>
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

          <div style={{ marginBottom: '15px' }}>
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
        </section>

        <div>
          <button type="button" onClick={() => window.history.back()}>
            Cancel
          </button>
          {' '}
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Starting...' : 'Run Evaluation'}
          </button>
        </div>
      </form>
    </div>
  );
}
