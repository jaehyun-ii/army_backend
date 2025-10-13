'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function PatchResultPage({ params }: { params: { patchId: string } }) {
  const [patch, setPatch] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPatchDetails();
  }, []);

  async function loadPatchDetails() {
    try {
      const data = await apiClient.getPatch(params.patchId);
      setPatch(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDownload() {
    try {
      const blob = await apiClient.downloadPatch(params.patchId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `adversarial_patch_${params.patchId}.png`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    }
  }

  if (isLoading) {
    return <div>Loading patch details...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Patch Generated Successfully</h2>

      <section>
        <h3>Patch Information</h3>
        <table border={1} cellPadding={5}>
          <tbody>
            <tr>
              <td><strong>ID:</strong></td>
              <td>{patch?.id}</td>
            </tr>
            <tr>
              <td><strong>Name:</strong></td>
              <td>{patch?.name}</td>
            </tr>
            <tr>
              <td><strong>Target Class:</strong></td>
              <td>{patch?.target_class}</td>
            </tr>
            <tr>
              <td><strong>Method:</strong></td>
              <td>{patch?.method}</td>
            </tr>
            <tr>
              <td><strong>Description:</strong></td>
              <td>{patch?.description || 'N/A'}</td>
            </tr>
            <tr>
              <td><strong>Created:</strong></td>
              <td>{new Date(patch?.created_at).toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h3>Patch Preview</h3>
        <img
          src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/adversarial-patch/patches/${params.patchId}/image`}
          alt="Adversarial Patch"
          style={{ maxWidth: '400px', border: '1px solid black' }}
          onError={(e) => {
            e.currentTarget.style.display = 'none';
            e.currentTarget.parentElement!.innerHTML += '<p style="color: red;">Image not available</p>';
          }}
        />
      </section>

      {patch?.patch_metadata && (
        <section>
          <h3>Generation Statistics</h3>
          <table border={1} cellPadding={5}>
            <tbody>
              <tr>
                <td><strong>Best Score:</strong></td>
                <td>{patch.patch_metadata.best_score?.toFixed(4) || 'N/A'}</td>
              </tr>
              <tr>
                <td><strong>Training Samples:</strong></td>
                <td>{patch.patch_metadata.num_training_samples || 'N/A'}</td>
              </tr>
              <tr>
                <td><strong>Target Class ID:</strong></td>
                <td>{patch.patch_metadata.target_class_id ?? 'N/A'}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {patch?.hyperparameters && (
        <section>
          <h3>Hyperparameters</h3>
          <table border={1} cellPadding={5}>
            <tbody>
              <tr>
                <td><strong>Epsilon:</strong></td>
                <td>{patch.hyperparameters.epsilon}</td>
              </tr>
              <tr>
                <td><strong>Alpha:</strong></td>
                <td>{patch.hyperparameters.alpha}</td>
              </tr>
              <tr>
                <td><strong>Iterations:</strong></td>
                <td>{patch.hyperparameters.iterations}</td>
              </tr>
              <tr>
                <td><strong>Batch Size:</strong></td>
                <td>{patch.hyperparameters.batch_size}</td>
              </tr>
              <tr>
                <td><strong>Patch Size:</strong></td>
                <td>{patch.hyperparameters.patch_size}px</td>
              </tr>
              <tr>
                <td><strong>Area Ratio:</strong></td>
                <td>{patch.hyperparameters.area_ratio}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h3>Next Actions</h3>
        <div>
          <button onClick={handleDownload}>Download Patch</button>
          {' '}
          <button onClick={() => window.location.href = '/attacks/adversarial-patch/create'}>
            Create New Patch
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
