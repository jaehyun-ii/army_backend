'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function NoiseAttackDetailPage({ params }: { params: { attackId: string } }) {
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

  const pluginName = attack?.parameters?.plugin_name || 'unknown';
  const methodMap: Record<string, string> = {
    'fgsm_2d': 'FGSM (Fast Gradient Sign Method)',
    'pgd_2d': 'PGD (Projected Gradient Descent)',
    'gaussian_2d': 'Gaussian Noise',
    'uniform_2d': 'Uniform Noise',
    'iterative_gradient_2d': 'Iterative Gradient Attack',
  };
  const method = methodMap[pluginName] || pluginName.replace('_2d', '').toUpperCase();

  return (
    <div>
      <h2>Noise Attack Dataset: {attack?.name}</h2>

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
              <td><strong>Method:</strong></td>
              <td>{method}</td>
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
              <td><strong>Skipped Images:</strong></td>
              <td>{attack?.parameters?.skipped_images || 0} (no target class found)</td>
            </tr>
            <tr>
              <td><strong>Failed Images:</strong></td>
              <td>{attack?.parameters?.failed_images || 0}</td>
            </tr>
            <tr>
              <td><strong>Average Noise Magnitude:</strong></td>
              <td>{attack?.parameters?.avg_noise_magnitude?.toFixed(4) || 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Max Noise Magnitude:</strong></td>
              <td>{attack?.parameters?.max_noise_magnitude?.toFixed(4) || 'N/A'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section style={{ marginBottom: '30px' }}>
        <h3>Attack Parameters</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            {attack?.parameters?.epsilon !== undefined && (
              <tr>
                <td><strong>Epsilon:</strong></td>
                <td>{attack.parameters.epsilon}</td>
              </tr>
            )}
            {attack?.parameters?.alpha !== undefined && (
              <tr>
                <td><strong>Alpha:</strong></td>
                <td>{attack.parameters.alpha}</td>
              </tr>
            )}
            {attack?.parameters?.iterations !== undefined && (
              <tr>
                <td><strong>Iterations:</strong></td>
                <td>{attack.parameters.iterations}</td>
              </tr>
            )}
            {attack?.parameters?.mean !== undefined && (
              <tr>
                <td><strong>Mean:</strong></td>
                <td>{attack.parameters.mean}</td>
              </tr>
            )}
            {attack?.parameters?.std !== undefined && (
              <tr>
                <td><strong>Std:</strong></td>
                <td>{attack.parameters.std}</td>
              </tr>
            )}
            {attack?.parameters?.min_val !== undefined && (
              <tr>
                <td><strong>Min Value:</strong></td>
                <td>{attack.parameters.min_val}</td>
              </tr>
            )}
            {attack?.parameters?.max_val !== undefined && (
              <tr>
                <td><strong>Max Value:</strong></td>
                <td>{attack.parameters.max_val}</td>
              </tr>
            )}
            {attack?.parameters?.max_iterations !== undefined && (
              <tr>
                <td><strong>Max Iterations:</strong></td>
                <td>{attack.parameters.max_iterations}</td>
              </tr>
            )}
            {attack?.parameters?.step_size !== undefined && (
              <tr>
                <td><strong>Step Size:</strong></td>
                <td>{attack.parameters.step_size}</td>
              </tr>
            )}
            {attack?.parameters?.stop_threshold !== undefined && (
              <tr>
                <td><strong>Stop Threshold:</strong></td>
                <td>{attack.parameters.stop_threshold}</td>
              </tr>
            )}
            <tr>
              <td><strong>Targeted:</strong></td>
              <td>{attack?.parameters?.targeted ? 'Yes' : 'No'}</td>
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
          <button onClick={() => window.location.href = '/attacks/noise-attack/results'}>
            Back to List
          </button>
          {' '}
          <button onClick={() => window.location.href = '/attacks/noise-attack/create'}>
            Create New Attack
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
