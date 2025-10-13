'use client';

import { useState, useEffect, useRef } from 'react';
import { apiClient } from '@/lib/api';

type AttackType = 'fgsm' | 'pgd' | 'gaussian' | 'uniform' | 'iterative-gradient';

export default function CreateNoiseAttackPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [topClasses, setTopClasses] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SSE 관련 state
  const [logs, setLogs] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const [attackType, setAttackType] = useState<AttackType>('pgd');
  const [formData, setFormData] = useState({
    attackName: '',
    datasetId: '',
    modelVersionId: '',
    // FGSM & PGD
    epsilon: 8.0,
    targetClass: '',
    // PGD specific
    alpha: 2.0,
    iterations: 10,
    // Gaussian
    mean: 0.0,
    std: 25.0,
    // Iterative Gradient
    maxIterations: 10000,  // Increased from 1000 to 10000 to match attack_detector capabilities
    stepSize: 1.0,  // Changed from 10000.0 to 1.0 for imperceptible noise
    epsilonIter: 0.03,  // Max perturbation (L-infinity constraint)
    nccThreshold: 0.6,  // NCC similarity threshold
    stopThreshold: 0.1,
  });

  useEffect(() => {
    loadInitialData();
  }, []);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  async function loadInitialData() {
    try {
      const [datasetsData, modelsData] = await Promise.all([
        apiClient.getDatasets(),
        apiClient.getModels(),
      ]);
      setDatasets(datasetsData);
      setModels(modelsData);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleDatasetChange(datasetId: string) {
    setFormData({ ...formData, datasetId });

    if (datasetId) {
      try {
        const data = await apiClient.getDatasetTopClasses(datasetId);
        if (data.source === 'metadata') {
          setTopClasses(data.top_classes || []);
        } else {
          setTopClasses([]);
        }
      } catch (err) {
        console.error('Failed to load top classes:', err);
        setTopClasses([]);
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setIsGenerating(true);
    setError(null);
    setLogs([]);
    setShowLogs(true);

    // Generate unique session ID for SSE
    const sessionId = `noise-attack-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    try {
      // Start SSE connection
      const eventSource = new EventSource(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/noise-attack/attacks/${sessionId}/events`
      );

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.message) {
          setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`]);
        }
        if (data.status === 'completed') {
          eventSource.close();
          setIsGenerating(false);
          setTimeout(() => {
            alert('Attack dataset created successfully!');
            window.location.href = '/attacks/noise-attack/results';
          }, 1000);
        }
        if (data.status === 'error') {
          eventSource.close();
          setIsGenerating(false);
          setError(data.message || 'Unknown error occurred');
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE Error:', error);
        eventSource.close();
        setIsGenerating(false);
        // Don't set error here - attack might still be running
      };

      // Start attack generation with session_id
      let result;

      if (attackType === 'fgsm') {
        result = await apiClient.generateFGSM({
          attack_dataset_name: formData.attackName,
          model_version_id: formData.modelVersionId,
          base_dataset_id: formData.datasetId,
          epsilon: formData.epsilon,
          targeted: true,
          target_class: formData.targetClass,
          session_id: sessionId,
        });
      } else if (attackType === 'pgd') {
        result = await apiClient.generatePGD({
          attack_dataset_name: formData.attackName,
          model_version_id: formData.modelVersionId,
          base_dataset_id: formData.datasetId,
          epsilon: formData.epsilon,
          alpha: formData.alpha,
          iterations: formData.iterations,
          targeted: true,
          target_class: formData.targetClass,
          session_id: sessionId,
        });
      } else if (attackType === 'gaussian') {
        result = await apiClient.generateGaussian({
          attack_dataset_name: formData.attackName,
          base_dataset_id: formData.datasetId,
          mean: formData.mean,
          std: formData.std,
          target_class: formData.targetClass,
          session_id: sessionId,
        });
      } else if (attackType === 'iterative-gradient') {
        result = await apiClient.generateIterativeGradient({
          attack_dataset_name: formData.attackName,
          model_version_id: formData.modelVersionId,
          base_dataset_id: formData.datasetId,
          max_iterations: formData.maxIterations,
          step_size: formData.stepSize,
          epsilon: formData.epsilonIter,
          ncc_threshold: formData.nccThreshold,
          stop_threshold: formData.stopThreshold,
          target_class: formData.targetClass,
          session_id: sessionId,
        });
      }

      // API call started successfully
      setLogs((prev) => [...prev, '[INFO] Attack generation started...']);

    } catch (err: any) {
      setError(err.message);
      setIsGenerating(false);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h2>Create Noise Attack Dataset (Targeted)</h2>

      <div style={{ backgroundColor: '#e8f4fd', padding: '15px', marginBottom: '20px', border: '1px solid #0066cc' }}>
        <strong>ℹ️ Note:</strong> All noise attacks are now <strong>targeted attacks</strong>.
        Noise will only be applied inside the bounding boxes of the specified target class.
      </div>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <section>
          <h3>Step 1: Select Attack Type</h3>
          <div>
            <label>
              <input
                type="radio"
                value="fgsm"
                checked={attackType === 'fgsm'}
                onChange={(e) => setAttackType(e.target.value as AttackType)}
              />
              {' '}FGSM (Fast Gradient Sign Method)
              <br />
              <small>Fast one-step attack using gradient sign</small>
            </label>
          </div>
          <div>
            <label>
              <input
                type="radio"
                value="pgd"
                checked={attackType === 'pgd'}
                onChange={(e) => setAttackType(e.target.value as AttackType)}
              />
              {' '}PGD (Projected Gradient Descent)
              <br />
              <small>Iterative attack with multiple steps</small>
            </label>
          </div>
          <div>
            <label>
              <input
                type="radio"
                value="gaussian"
                checked={attackType === 'gaussian'}
                onChange={(e) => setAttackType(e.target.value as AttackType)}
              />
              {' '}Gaussian Noise
              <br />
              <small>Random Gaussian noise injection</small>
            </label>
          </div>
          <div>
            <label>
              <input
                type="radio"
                value="iterative-gradient"
                checked={attackType === 'iterative-gradient'}
                onChange={(e) => setAttackType(e.target.value as AttackType)}
              />
              {' '}Iterative Gradient Attack ⭐
              <br />
              <small>Advanced attack with imperceptible noise using epsilon constraints and NCC similarity (most powerful & subtle)</small>
            </label>
          </div>
        </section>

        <section>
          <h3>Step 2: Configuration</h3>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Attack Name *
              <br />
              <input
                type="text"
                value={formData.attackName}
                onChange={(e) => setFormData({ ...formData, attackName: e.target.value })}
                required
                style={{ width: '100%', padding: '5px' }}
              />
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Source Dataset *
              <br />
              <select
                value={formData.datasetId}
                onChange={(e) => handleDatasetChange(e.target.value)}
                required
                style={{ width: '100%', padding: '5px' }}
              >
                <option value="">Select Dataset</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name} ({dataset.image_count || 0} images)
                  </option>
                ))}
              </select>
            </label>
          </div>

          {(attackType === 'fgsm' || attackType === 'pgd' || attackType === 'iterative-gradient') && (
            <div style={{ marginBottom: '15px' }}>
              <label>
                Target Model *
                <br />
                <select
                  value={formData.modelVersionId}
                  onChange={(e) => setFormData({ ...formData, modelVersionId: e.target.value })}
                  required
                  style={{ width: '100%', padding: '5px' }}
                >
                  <option value="">Select Model</option>
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name} v{model.version}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          <div style={{ marginBottom: '15px' }}>
            <label>
              Target Class * (noise applied inside bboxes)
              <br />
              {topClasses.length > 0 ? (
                <div>
                  <p style={{ fontSize: '12px', color: '#666', marginBottom: '5px' }}>
                    Top classes in selected dataset:
                  </p>
                  <select
                    value={formData.targetClass}
                    onChange={(e) => setFormData({ ...formData, targetClass: e.target.value })}
                    required
                    style={{ width: '100%', padding: '5px' }}
                  >
                    <option value="">Select Class</option>
                    {topClasses.map((cls) => (
                      <option key={cls.class_name} value={cls.class_name}>
                        {cls.class_name} ({cls.count} detections, {cls.percentage?.toFixed(2)}%)
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <input
                  type="text"
                  value={formData.targetClass}
                  onChange={(e) => setFormData({ ...formData, targetClass: e.target.value })}
                  placeholder="Enter target class (e.g., person, car)"
                  required
                  style={{ width: '100%', padding: '5px' }}
                />
              )}
            </label>
          </div>
        </section>

        {attackType === 'pgd' && (
          <section>
            <h3>PGD Parameters</h3>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Epsilon (0-255)
                <br />
                <input
                  type="number"
                  min="0"
                  max="255"
                  step="0.1"
                  value={formData.epsilon}
                  onChange={(e) => setFormData({ ...formData, epsilon: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Alpha (Step Size)
                <br />
                <input
                  type="number"
                  min="0"
                  max="50"
                  step="0.1"
                  value={formData.alpha}
                  onChange={(e) => setFormData({ ...formData, alpha: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Iterations
                <br />
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={formData.iterations}
                  onChange={(e) => setFormData({ ...formData, iterations: parseInt(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
          </section>
        )}

        {attackType === 'fgsm' && (
          <section>
            <h3>FGSM Parameters</h3>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Epsilon (0-255)
                <br />
                <input
                  type="number"
                  min="0"
                  max="255"
                  step="0.1"
                  value={formData.epsilon}
                  onChange={(e) => setFormData({ ...formData, epsilon: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
          </section>
        )}

        {attackType === 'gaussian' && (
          <section>
            <h3>Gaussian Noise Parameters</h3>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Mean
                <br />
                <input
                  type="number"
                  step="0.1"
                  value={formData.mean}
                  onChange={(e) => setFormData({ ...formData, mean: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
            <div style={{ marginBottom: '15px' }}>
              <label>
                Standard Deviation (0-100)
                <br />
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.std}
                  onChange={(e) => setFormData({ ...formData, std: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
          </section>
        )}

        {attackType === 'iterative-gradient' && (
          <section>
            <h3>Iterative Gradient Parameters</h3>
            <div style={{ backgroundColor: '#fff3cd', padding: '10px', marginBottom: '15px', border: '1px solid #ffc107', borderRadius: '4px' }}>
              <strong>⚙️ Advanced Attack:</strong> Creates imperceptible noise using iterative gradient optimization with epsilon constraints and NCC similarity checking.
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Max Iterations (1-100000)
                <br />
                <small>Maximum number of attack iterations to perform</small>
                <br />
                <input
                  type="number"
                  min="1"
                  max="100000"
                  value={formData.maxIterations}
                  onChange={(e) => setFormData({ ...formData, maxIterations: parseInt(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Step Size (0.1-10.0)
                <br />
                <small>Gradient step size in normalized range (default: 1.0, lower = more subtle)</small>
                <br />
                <input
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={formData.stepSize}
                  onChange={(e) => setFormData({ ...formData, stepSize: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Epsilon (0.01-0.3)
                <br />
                <small>Maximum perturbation per pixel (default: 0.03 = 3%, lower = less visible)</small>
                <br />
                <input
                  type="number"
                  min="0.01"
                  max="0.3"
                  step="0.01"
                  value={formData.epsilonIter}
                  onChange={(e) => setFormData({ ...formData, epsilonIter: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                NCC Threshold (0.3-0.95)
                <br />
                <small>Similarity threshold to preserve visual quality (default: 0.6, higher = more similar)</small>
                <br />
                <input
                  type="number"
                  min="0.3"
                  max="0.95"
                  step="0.05"
                  value={formData.nccThreshold}
                  onChange={(e) => setFormData({ ...formData, nccThreshold: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label>
                Stop Threshold (0.0-1.0)
                <br />
                <small>Stop when detections &lt; threshold × initial (default: 0.1)</small>
                <br />
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={formData.stopThreshold}
                  onChange={(e) => setFormData({ ...formData, stopThreshold: parseFloat(e.target.value) })}
                  style={{ width: '100%', padding: '5px' }}
                />
              </label>
            </div>
          </section>
        )}

        <div>
          <button type="button" onClick={() => window.history.back()} disabled={isGenerating}>
            Cancel
          </button>
          {' '}
          <button type="submit" disabled={isLoading || isGenerating}>
            {isGenerating ? 'Generating...' : isLoading ? 'Starting...' : 'Generate Attack Dataset'}
          </button>
        </div>
      </form>

      {/* Real-time Logs */}
      {showLogs && (
        <div style={{ marginTop: '30px', border: '1px solid #ccc', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            backgroundColor: '#333',
            color: 'white',
            padding: '10px',
            fontWeight: 'bold',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>📋 Real-time Generation Logs</span>
            <span style={{ fontSize: '12px', color: '#aaa' }}>
              {isGenerating ? '🔄 Generating...' : '✅ Completed'}
            </span>
          </div>
          <div style={{
            backgroundColor: '#1e1e1e',
            color: '#d4d4d4',
            padding: '15px',
            fontFamily: 'monospace',
            fontSize: '13px',
            maxHeight: '400px',
            overflowY: 'auto'
          }}>
            {logs.length === 0 ? (
              <div style={{ color: '#888' }}>Waiting for logs...</div>
            ) : (
              <>
                {logs.map((log, index) => (
                  <div key={index} style={{ marginBottom: '5px' }}>
                    {log}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
