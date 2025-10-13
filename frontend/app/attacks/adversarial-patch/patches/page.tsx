'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function PatchesListPage() {
  const [patches, setPatches] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPatches();
  }, []);

  async function loadPatches() {
    try {
      const data = await apiClient.getPatches();
      setPatches(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading patches...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Generated Adversarial Patches</h2>

      <div style={{ marginBottom: '20px' }}>
        <button onClick={() => window.location.href = '/attacks/adversarial-patch/create'}>
          Create New Patch
        </button>
      </div>

      {patches.length === 0 ? (
        <div style={{ padding: '20px', backgroundColor: '#f0f0f0', border: '1px solid #ccc' }}>
          No patches found. Create one to get started.
        </div>
      ) : (
        <table border={1} cellPadding={10} style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f0f0f0' }}>
              <th>Name</th>
              <th>Target Class</th>
              <th>Method</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {patches.map((patch) => (
              <tr key={patch.id}>
                <td>{patch.name}</td>
                <td>{patch.target_class || 'N/A'}</td>
                <td>{patch.method || 'N/A'}</td>
                <td>{new Date(patch.created_at).toLocaleString()}</td>
                <td>
                  <button
                    onClick={() => window.location.href = `/attacks/adversarial-patch/result/${patch.id}`}
                    style={{ marginRight: '5px' }}
                  >
                    View Details
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        const blob = await apiClient.downloadPatch(patch.id);
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `${patch.name}.png`;
                        a.click();
                        window.URL.revokeObjectURL(url);
                      } catch (err: any) {
                        alert(`Download failed: ${err.message}`);
                      }
                    }}
                  >
                    Download
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
