const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiClient {
  private baseUrl: string;
  private token: string | null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.token = null;
  }

  setToken(token: string) {
    this.token = token;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    // localStorage에서 토큰을 가져옴 (브라우저 환경에서만)
    const token = this.token || (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null);

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  async post<T>(path: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'API request failed');
    }

    return response.json();
  }

  async put<T>(path: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  async delete(path: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
  }

  // Auth
  async register(data: {
    email: string;
    password: string;
    display_name?: string;
  }) {
    return this.post<any>('/api/v1/auth/register', data);
  }

  async login(data: {
    email: string;
    password: string;
  }) {
    return this.post<{ access_token: string; token_type: string }>('/api/v1/auth/login-json', data);
  }

  // Datasets
  async getDatasets() {
    return this.get<any[]>('/api/v1/datasets-2d?skip=0&limit=100');
  }

  async getDatasetTopClasses(datasetId: string, limit: number = 5) {
    return this.get<any>(`/api/v1/datasets-2d/${datasetId}/top-classes?limit=${limit}`);
  }

  // Models
  async getModels() {
    return this.get<any[]>('/api/v1/models/versions?skip=0&limit=100');
  }

  // Adversarial Patch
  async generatePatch(data: {
    patch_name: string;
    model_version_id: string;
    dataset_id: string;
    target_class: string;
    description?: string;
    session_id?: string;
  }) {
    // Include default values for optional parameters
    const requestData: any = {
      patch_name: data.patch_name,
      model_version_id: data.model_version_id,
      dataset_id: data.dataset_id,
      target_class: data.target_class,
      plugin_name: "global_pgd_2d",
      patch_size: 100,
      area_ratio: 0.3,
      epsilon: 0.6,
      alpha: 0.03,
      iterations: 100,
      batch_size: 8
    };

    // Only include description and session_id if provided
    if (data.description) {
      requestData.description = data.description;
    }
    if (data.session_id) {
      requestData.session_id = data.session_id;
    }

    return this.post<any>('/api/v1/adversarial-patch/patches/generate', requestData);
  }

  async getPatches() {
    return this.get<any[]>('/api/v1/adversarial-patch/patches?skip=0&limit=100');
  }

  async getPatch(patchId: string) {
    return this.get<any>(`/api/v1/adversarial-patch/patches/${patchId}`);
  }

  async downloadPatch(patchId: string) {
    const response = await fetch(`${this.baseUrl}/api/v1/adversarial-patch/patches/${patchId}/download`, {
      method: 'GET',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new Error('Download failed');
    }

    return response.blob();
  }

  // Noise Attacks
  async generateFGSM(data: {
    attack_dataset_name: string;
    model_version_id: string;
    base_dataset_id: string;
    epsilon: number;
    targeted?: boolean;
    target_class?: string;
    session_id?: string;
  }) {
    return this.post<any>('/api/v1/noise-attack/fgsm/generate', data);
  }

  async generatePGD(data: {
    attack_dataset_name: string;
    model_version_id: string;
    base_dataset_id: string;
    epsilon: number;
    alpha: number;
    iterations: number;
    targeted?: boolean;
    target_class?: string;
    session_id?: string;
  }) {
    return this.post<any>('/api/v1/noise-attack/pgd/generate', data);
  }

  async generateGaussian(data: {
    attack_dataset_name: string;
    base_dataset_id: string;
    mean: number;
    std: number;
    target_class: string;
    session_id?: string;
  }) {
    return this.post<any>('/api/v1/noise-attack/gaussian/generate', data);
  }

  async generateIterativeGradient(data: {
    attack_dataset_name: string;
    model_version_id: string;
    base_dataset_id: string;
    max_iterations: number;
    step_size: number;
    epsilon: number;  // Max perturbation (L-infinity constraint)
    ncc_threshold: number;  // NCC similarity threshold
    stop_threshold: number;
    target_class: string;
    session_id?: string;
  }) {
    return this.post<any>('/api/v1/noise-attack/iterative-gradient/generate', data);
  }

  async getAttackDatasets() {
    return this.get<any[]>('/api/v1/adversarial-patch/attack-datasets?skip=0&limit=100');
  }

  async getAttackDataset(attackId: string) {
    return this.get<any>(`/api/v1/adversarial-patch/attack-datasets/${attackId}`);
  }

  // Evaluation
  async createEvaluationRun(data: {
    name: string;
    phase: 'pre_attack' | 'post_attack';
    model_version_id: string;
    base_dataset_id?: string;
    attack_dataset_id?: string;
    config?: any;
  }) {
    return this.post<any>('/api/v1/evaluation/runs', data);
  }

  async getEvaluationRun(runId: string) {
    return this.get<any>(`/api/v1/evaluation/runs/${runId}`);
  }

  async listEvaluationRuns() {
    return this.get<any>('/api/v1/evaluation/runs');
  }

  async compareEvaluationRuns(data: {
    pre_attack_run_id: string;
    post_attack_run_id: string;
  }) {
    return this.post<any>('/api/v1/evaluation/runs/compare', data);
  }

  // Realtime
  async getCameras() {
    return this.get<any[]>('/api/v1/realtime/cameras?skip=0&limit=100');
  }

  async getWebcams() {
    const response = await this.get<{ cameras: any[], count: number }>('/api/v1/realtime/webcam/list');
    return response.cameras;
  }

  async startWebcamSession(data: {
    run_name: string;
    device: string;
    model_version_id: string;
    fps_target?: number;
    window_seconds?: number;
    conf_threshold?: number;
    iou_threshold?: number;
  }) {
    const params = new URLSearchParams({
      run_name: data.run_name,
      device: data.device,
      model_version_id: data.model_version_id,
      fps_target: (data.fps_target || 30).toString(),
      window_seconds: (data.window_seconds || 300).toString(),
      conf_threshold: (data.conf_threshold || 0.25).toString(),
      iou_threshold: (data.iou_threshold || 0.45).toString(),
    });

    return this.post<any>(`/api/v1/realtime/webcam/sessions/start?${params.toString()}`, {});
  }

  async createRealtimeSession(data: {
    camera_id: string;
    model_version_id: string;
    run_name: string;
    capture_duration_seconds?: number | null;
    frame_sample_rate?: number;
    save_frames?: boolean;
    config?: any;
  }) {
    return this.post<any>('/api/v1/realtime/runs', data);
  }

  async getRealtimeSession(sessionId: string) {
    return this.get<any>(`/api/v1/realtime/runs/${sessionId}`);
  }

  async stopRealtimeSession(sessionId: string) {
    return this.post<any>(`/api/v1/realtime/webcam/stop/${sessionId}`, {});
  }

  // Experiments
  async createExperiment(data: {
    name: string;
    description?: string;
    hypothesis?: string;
    parameters?: any;
    tags?: string[];
  }) {
    return this.post<any>('/api/v1/experiments', data);
  }

  async getExperiment(experimentId: string) {
    return this.get<any>(`/api/v1/experiments/${experimentId}`);
  }

  async addExperimentRun(experimentId: string, data: {
    run_name: string;
    parameters?: any;
    metrics?: any;
    artifacts?: any;
  }) {
    return this.post<any>(`/api/v1/experiments/${experimentId}/results`, data);
  }
}

export const apiClient = new ApiClient();
