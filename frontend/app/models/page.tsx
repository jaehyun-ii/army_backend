'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';

export default function ModelsPage() {
  const [models, setModels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInferenceModal, setShowInferenceModal] = useState(false);
  const [selectedModel, setSelectedModel] = useState<any>(null);
  const [inferenceImage, setInferenceImage] = useState<File | null>(null);
  const [inferenceResult, setInferenceResult] = useState<any>(null);
  const [isInferencing, setIsInferencing] = useState(false);

  useEffect(() => {
    loadModels();
  }, []);

  async function loadModels() {
    try {
      // Load all uploaded models (both loaded and unloaded)
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/custom-models/`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setModels(data);
      } else {
        setModels([]);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  const handleLoadModel = async (modelId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/custom-models/${modelId}/load`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to load model');
      }

      alert('Model loaded successfully!');
      loadModels(); // Refresh list
    } catch (err: any) {
      console.error('Load error:', err);
      alert(`Failed to load model: ${err.message}`);
    }
  };

  const handleUnloadModel = async (modelId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/custom-models/${modelId}/unload`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to unload model');
      }

      alert('Model unloaded successfully!');
      loadModels(); // Refresh list
    } catch (err: any) {
      console.error('Unload error:', err);
      alert(`Failed to unload model: ${err.message}`);
    }
  };

  const handleTestInference = (model: any) => {
    setSelectedModel(model);
    setInferenceImage(null);
    setInferenceResult(null);
    setShowInferenceModal(true);
  };

  const handleRunInference = async () => {
    if (!inferenceImage || !selectedModel) return;

    setIsInferencing(true);
    setInferenceResult(null);

    try {
      const token = localStorage.getItem('access_token');

      // Convert image to base64
      const reader = new FileReader();
      reader.onloadend = async () => {
        try {
          const base64 = (reader.result as string).split(',')[1];

          const response = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/custom-models/${selectedModel.model_id}/test-inference`,
            {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                image_base64: base64,
                conf_threshold: 0.25,
                iou_threshold: 0.45,
              }),
            }
          );

          if (!response.ok) {
            let errorMessage = 'Inference failed';
            try {
              const errorData = await response.json();
              console.error('API Error:', errorData);

              if (typeof errorData.detail === 'string') {
                errorMessage = errorData.detail;
              } else if (errorData.detail && typeof errorData.detail === 'object') {
                errorMessage = JSON.stringify(errorData.detail);
              } else if (errorData.message) {
                errorMessage = errorData.message;
              }
            } catch (e) {
              errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }

            throw new Error(errorMessage);
          }

          const result = await response.json();
          setInferenceResult(result);

          // Refresh model list to update load status
          loadModels();
        } catch (err: any) {
          console.error('Inference error:', err);
          alert(`Inference failed: ${err.message || err}`);
          throw err;
        } finally {
          setIsInferencing(false);
        }
      };

      reader.readAsDataURL(inferenceImage);
    } catch (err: any) {
      console.error('Inference error:', err);
      setIsInferencing(false);
    }
  };

  if (isLoading) {
    return <div>Loading models...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h2>Models</h2>

      <div style={{ marginBottom: '20px' }}>
        <button onClick={() => window.location.href = '/models/upload'}>
          Upload New Model
        </button>
      </div>

      {models.length === 0 ? (
        <p>No models uploaded yet. Upload a model to get started.</p>
      ) : (
        <table border={1} cellPadding={5} style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Version</th>
              <th>Framework</th>
              <th>Classes</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.model_id}>
                <td>{model.model_name}</td>
                <td>{model.version}</td>
                <td>{model.framework || 'N/A'}</td>
                <td>{model.num_classes || 'N/A'}</td>
                <td>
                  <span style={{ color: model.is_loaded ? 'green' : 'gray', fontWeight: 'bold' }}>
                    {model.is_loaded ? '● Loaded' : '○ Not Loaded'}
                  </span>
                </td>
                <td>{model.created_at ? new Date(model.created_at).toLocaleDateString() : 'N/A'}</td>
                <td>
                  {!model.is_loaded ? (
                    <button onClick={() => handleLoadModel(model.model_id)} style={{ marginRight: '5px' }}>
                      Load
                    </button>
                  ) : (
                    <button onClick={() => handleUnloadModel(model.model_id)} style={{ marginRight: '5px' }}>
                      Unload
                    </button>
                  )}
                  <button
                    onClick={() => handleTestInference(model)}
                    style={{ marginRight: '5px' }}
                  >
                    Test Inference
                  </button>
                  <a href={`/models/${model.model_id}`}>View</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Inference Test Modal */}
      {showInferenceModal && selectedModel && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowInferenceModal(false)}
        >
          <div
            style={{
              backgroundColor: 'white',
              padding: '20px',
              maxWidth: '800px',
              maxHeight: '90%',
              overflow: 'auto',
              minWidth: '500px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Test Inference: {selectedModel.model_name}</h3>

            <div style={{ marginBottom: '15px' }}>
              <label>
                <strong>Select Image:</strong>
                <br />
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setInferenceImage(e.target.files?.[0] || null)}
                />
              </label>
            </div>

            {inferenceImage && (
              <div style={{ marginBottom: '15px' }}>
                <img
                  src={URL.createObjectURL(inferenceImage)}
                  alt="Test"
                  style={{ maxWidth: '100%', maxHeight: '300px' }}
                />
              </div>
            )}

            <div style={{ marginBottom: '15px' }}>
              <button
                onClick={handleRunInference}
                disabled={!inferenceImage || isInferencing}
                style={{ padding: '10px 20px', marginRight: '10px' }}
              >
                {isInferencing ? 'Running...' : 'Run Inference'}
              </button>
              <button onClick={() => setShowInferenceModal(false)} style={{ padding: '10px 20px' }}>
                Close
              </button>
            </div>

            {/* Inference Results */}
            {inferenceResult && (
              <div style={{ marginTop: '20px', borderTop: '2px solid #ccc', paddingTop: '10px' }}>
                <h4>Results ({inferenceResult.detections?.length || 0} detections)</h4>
                <p><strong>Inference Time:</strong> {inferenceResult.inference_time_ms?.toFixed(2)} ms</p>

                {inferenceResult.detections && inferenceResult.detections.length > 0 ? (
                  <table border={1} cellPadding={5} style={{ width: '100%', fontSize: '12px' }}>
                    <thead>
                      <tr>
                        <th>Class</th>
                        <th>Confidence</th>
                        <th>BBox</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inferenceResult.detections.map((det: any, idx: number) => (
                        <tr key={idx}>
                          <td><strong>{det.class_name}</strong></td>
                          <td>{(det.confidence * 100).toFixed(1)}%</td>
                          <td style={{ fontSize: '10px' }}>
                            ({det.bbox.x1.toFixed(0)}, {det.bbox.y1.toFixed(0)}) -
                            ({det.bbox.x2.toFixed(0)}, {det.bbox.y2.toFixed(0)})
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p style={{ color: '#666' }}>No detections found</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
