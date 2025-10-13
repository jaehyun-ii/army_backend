'use client';

import { useState } from 'react';
import { apiClient } from '@/lib/api';

export default function CreateExperimentPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    hypothesis: '',
    parametersJson: '{}',
    tags: '',
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      let parameters;
      try {
        parameters = JSON.parse(formData.parametersJson);
      } catch {
        throw new Error('Invalid JSON in parameters field');
      }

      const result = await apiClient.createExperiment({
        name: formData.name,
        description: formData.description || undefined,
        hypothesis: formData.hypothesis || undefined,
        parameters,
        tags: formData.tags ? formData.tags.split(',').map(t => t.trim()) : undefined,
      });

      alert('Experiment created successfully!');
      window.location.href = `/experiments/${result.id}`;
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h2>Create New Experiment</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '15px' }}>
          <label>
            Experiment Name *
            <br />
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              style={{ width: '100%', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Description
            <br />
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
              style={{ width: '100%', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Hypothesis
            <br />
            <textarea
              value={formData.hypothesis}
              onChange={(e) => setFormData({ ...formData, hypothesis: e.target.value })}
              rows={3}
              style={{ width: '100%', padding: '5px' }}
              placeholder="e.g., Larger patches achieve better attack success but are more noticeable."
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Parameters (JSON)
            <br />
            <textarea
              value={formData.parametersJson}
              onChange={(e) => setFormData({ ...formData, parametersJson: e.target.value })}
              rows={6}
              style={{ width: '100%', padding: '5px', fontFamily: 'monospace' }}
              placeholder={`{
  "patch_sizes": [50, 100, 150, 200],
  "target_class": "person",
  "epsilon": 0.6,
  "iterations": 100
}`}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Tags (comma-separated)
            <br />
            <input
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              style={{ width: '100%', padding: '5px' }}
              placeholder="e.g., patch-optimization, person-detection, evasion"
            />
          </label>
        </div>

        <div>
          <button type="button" onClick={() => window.history.back()}>
            Cancel
          </button>
          {' '}
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Creating...' : 'Create Experiment'}
          </button>
        </div>
      </form>
    </div>
  );
}
