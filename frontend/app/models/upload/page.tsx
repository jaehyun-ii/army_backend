'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function ModelUploadPage() {
  const router = useRouter();
  const [modelName, setModelName] = useState('');
  const [version, setVersion] = useState('1.0');
  const [framework, setFramework] = useState('pytorch');
  const [description, setDescription] = useState('');
  const [configFile, setConfigFile] = useState<File | null>(null);
  const [adapterFile, setAdapterFile] = useState<File | null>(null);
  const [weightsFile, setWeightsFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!modelName || !configFile || !adapterFile || !weightsFile) {
      setError('Please fill in all required fields and select all required files');
      return;
    }

    setIsUploading(true);

    try {
      const token = localStorage.getItem('access_token');
      const formData = new FormData();

      formData.append('model_name', modelName);
      formData.append('version', version);
      formData.append('framework', framework);
      if (description) {
        formData.append('description', description);
      }
      formData.append('config_file', configFile);
      formData.append('adapter_file', adapterFile);
      formData.append('weights_file', weightsFile);

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/custom-models/upload`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();
      alert(`Model uploaded successfully!\nModel ID: ${result.model_id}\nStatus: ${result.upload_status}`);
      router.push('/models');
    } catch (err: any) {
      console.error('Upload error:', err);
      setError(err.message || 'Failed to upload model');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div>
      <h2>Upload Custom Model</h2>

      {error && (
        <div style={{ padding: '10px', backgroundColor: '#ffdddd', color: '#d00', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '15px' }}>
          <label>
            <strong>Model Name *</strong>
            <br />
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              required
              style={{ width: '400px', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            <strong>Version *</strong>
            <br />
            <input
              type="text"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              required
              style={{ width: '400px', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            <strong>Framework *</strong>
            <br />
            <select
              value={framework}
              onChange={(e) => setFramework(e.target.value)}
              required
              style={{ width: '400px', padding: '5px' }}
            >
              <option value="pytorch">PyTorch</option>
              <option value="tensorflow">TensorFlow</option>
              <option value="onnx">ONNX</option>
              <option value="other">Other</option>
            </select>
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            <strong>Description</strong>
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              style={{ width: '400px', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f0f0f0' }}>
          <h3>Required Files</h3>

          <div style={{ marginBottom: '10px' }}>
            <label>
              <strong>config.yaml *</strong>
              <br />
              <input
                type="file"
                accept=".yaml,.yml"
                onChange={(e) => setConfigFile(e.target.files?.[0] || null)}
                required
              />
              {configFile && <div style={{ fontSize: '12px', color: '#666' }}>Selected: {configFile.name}</div>}
            </label>
          </div>

          <div style={{ marginBottom: '10px' }}>
            <label>
              <strong>adapter.py *</strong>
              <br />
              <input
                type="file"
                accept=".py"
                onChange={(e) => setAdapterFile(e.target.files?.[0] || null)}
                required
              />
              {adapterFile && <div style={{ fontSize: '12px', color: '#666' }}>Selected: {adapterFile.name}</div>}
            </label>
          </div>

          <div style={{ marginBottom: '10px' }}>
            <label>
              <strong>Weights File * (.pt, .pth, .onnx, etc.)</strong>
              <br />
              <input
                type="file"
                onChange={(e) => setWeightsFile(e.target.files?.[0] || null)}
                required
              />
              {weightsFile && <div style={{ fontSize: '12px', color: '#666' }}>Selected: {weightsFile.name}</div>}
            </label>
          </div>
        </div>

        <div style={{ marginTop: '20px' }}>
          <button type="submit" disabled={isUploading} style={{ padding: '10px 20px', marginRight: '10px' }}>
            {isUploading ? 'Uploading...' : 'Upload Model'}
          </button>
          <button type="button" onClick={() => router.back()} style={{ padding: '10px 20px' }}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
