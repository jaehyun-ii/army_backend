'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function NoiseAttackResultsPage() {
  const [attackDatasets, setAttackDatasets] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAttackDatasets();
  }, []);

  async function loadAttackDatasets() {
    try {
      const data = await apiClient.getAttackDatasets();
      // Filter to only show noise attacks
      const noiseAttacks = data.filter((attack: any) => attack.attack_type === 'NOISE');
      setAttackDatasets(noiseAttacks);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading attack datasets...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  const methodMap: Record<string, string> = {
    'fgsm_2d': 'FGSM',
    'pgd_2d': 'PGD',
    'gaussian_2d': 'Gaussian',
    'uniform_2d': 'Uniform',
    'iterative_gradient_2d': 'Iterative Gradient',
  };

  return (
    <div>
      <h2>Noise Attack Datasets</h2>

      <div style={{ marginBottom: '20px' }}>
        <button onClick={() => window.location.href = '/attacks/noise-attack/create'}>
          Create New Noise Attack
        </button>
      </div>

      {attackDatasets.length === 0 ? (
        <div style={{ padding: '20px', backgroundColor: '#f0f0f0', border: '1px solid #ccc' }}>
          No noise attack datasets found. Create one to get started.
        </div>
      ) : (
        <table border={1} cellPadding={10} style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f0f0f0' }}>
              <th>Name</th>
              <th>Target Class</th>
              <th>Method</th>
              <th>Images</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {attackDatasets.map((attack) => (
              <tr key={attack.id}>
                <td>{attack.name}</td>
                <td>{attack.target_class || 'N/A'}</td>
                <td>
                  {methodMap[attack.parameters?.plugin_name] || attack.parameters?.plugin_name?.replace('_2d', '').toUpperCase() || 'NOISE'}
                </td>
                <td>{attack.parameters?.processed_images || 0}</td>
                <td>{new Date(attack.created_at).toLocaleString()}</td>
                <td>
                  <button
                    onClick={() => window.location.href = `/attacks/noise-attack/results/${attack.id}`}
                    style={{ marginRight: '5px' }}
                  >
                    View Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
