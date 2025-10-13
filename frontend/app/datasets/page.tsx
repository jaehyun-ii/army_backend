'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDatasets();
  }, []);

  async function loadDatasets() {
    try {
      const data = await apiClient.getDatasets();
      setDatasets(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading datasets...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>2D Datasets</h2>

      {datasets.length === 0 ? (
        <p>No datasets available</p>
      ) : (
        <table border={1} cellPadding={5} style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Images</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((dataset) => (
              <tr key={dataset.id}>
                <td>{dataset.name}</td>
                <td>{dataset.description || 'N/A'}</td>
                <td>{dataset.image_count || 0}</td>
                <td>{new Date(dataset.created_at).toLocaleDateString()}</td>
                <td>
                  <button onClick={() => window.location.href = `/datasets/${dataset.id}`}>
                    View
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
