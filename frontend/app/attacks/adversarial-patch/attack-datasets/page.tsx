'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function PatchAttackDatasetsPage() {
  const [attackDatasets, setAttackDatasets] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAttackDatasets();
  }, []);

  async function loadAttackDatasets() {
    try {
      const data = await apiClient.getAttackDatasets();
      // Filter to only show patch attacks
      const patchAttacks = data.filter((attack: any) => attack.attack_type === 'PATCH');
      setAttackDatasets(patchAttacks);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading patch attack datasets...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Patch Attack Datasets</h2>

      <p style={{ marginBottom: '20px', color: '#666' }}>
        Datasets created by applying adversarial patches to images
      </p>

      {attackDatasets.length === 0 ? (
        <div style={{ padding: '20px', backgroundColor: '#f0f0f0', border: '1px solid #ccc' }}>
          No patch attack datasets found. Generate a patch and apply it to a dataset to get started.
        </div>
      ) : (
        <table border={1} cellPadding={10} style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f0f0f0' }}>
              <th>Name</th>
              <th>Target Class</th>
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
                <td>{attack.parameters?.processed_images || 0}</td>
                <td>{new Date(attack.created_at).toLocaleString()}</td>
                <td>
                  <button
                    onClick={() => window.location.href = `/attacks/adversarial-patch/attack-datasets/${attack.id}`}
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
