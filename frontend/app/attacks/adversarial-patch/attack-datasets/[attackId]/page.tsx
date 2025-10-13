'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function PatchAttackDatasetDetailPage({ params }: { params: { attackId: string } }) {
  const [attack, setAttack] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAttackDetails();
  }, []);

  async function loadAttackDetails() {
    try {
      const data = await apiClient.getAttackDataset(params.attackId);
      setAttack(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading attack dataset details...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Patch Attack Dataset: {attack?.name}</h2>

      <section style={{ marginBottom: '30px' }}>
        <h3>Basic Information</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>ID:</strong></td>
              <td>{attack?.id}</td>
            </tr>
            <tr>
              <td><strong>Name:</strong></td>
              <td>{attack?.name}</td>
            </tr>
            <tr>
              <td><strong>Attack Type:</strong></td>
              <td>{attack?.attack_type}</td>
            </tr>
            <tr>
              <td><strong>Target Class:</strong></td>
              <td>{attack?.target_class || 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Description:</strong></td>
              <td>{attack?.description || 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Created:</strong></td>
              <td>{new Date(attack?.created_at).toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section style={{ marginBottom: '30px' }}>
        <h3>Statistics</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>Processed Images:</strong></td>
              <td>{attack?.parameters?.processed_images || 0}</td>
            </tr>
            <tr>
              <td><strong>Patch Scale:</strong></td>
              <td>{attack?.parameters?.patch_scale || 'N/A'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section style={{ marginBottom: '30px' }}>
        <h3>Referenced Resources</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>Base Dataset ID:</strong></td>
              <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{attack?.base_dataset_id || 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Target Model Version ID:</strong></td>
              <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{attack?.target_model_version_id || 'N/A'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section style={{ marginBottom: '30px' }}>
        <h3>Storage</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>Storage Path:</strong></td>
              <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                {attack?.parameters?.storage_path || 'N/A'}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h3>Actions</h3>
        <div>
          <button onClick={() => window.location.href = '/attacks/adversarial-patch/attack-datasets'}>
            Back to List
          </button>
          {' '}
          <button onClick={() => window.location.href = '/evaluation/create'}>
            Run Evaluation
          </button>
        </div>
      </section>
    </div>
  );
}
