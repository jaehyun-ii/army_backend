/**
 * API Client for FastAPI Backend
 * 새로운 백엔드 API: /home/jaehyun/army/army_backend/backend
 */

const BACKEND_API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000'
const API_V1 = '/api/v1'

interface APIResponse<T> {
  data?: T
  error?: string
  message?: string
}

class APIClient {
  private baseURL: string

  constructor(baseURL: string = BACKEND_API_URL) {
    this.baseURL = baseURL
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`

    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include',
    }

    try {
      const response = await fetch(url, config)

      // 204 No Content는 빈 응답 반환
      if (response.status === 204) {
        return {} as T
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        // Handle both string and object detail formats
        let errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`

        // If detail is an array (validation errors), format it
        if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((err: any) =>
            `${err.loc?.join('.')} - ${err.msg}`
          ).join(', ')
        } else if (typeof errorData.detail === 'object') {
          errorMessage = JSON.stringify(errorData.detail)
        }

        throw new Error(errorMessage)
      }

      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      }

      return {} as T
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error)
      throw error
    }
  }

  // ============================================
  // Authentication Endpoints
  // ============================================

  async register(data: { email: string; password: string; name?: string }) {
    return this.request(`${API_V1}/auth/register`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async login(data: { email: string; password: string }) {
    return this.request(`${API_V1}/auth/login-json`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ============================================
  // Dataset CRUD Endpoints (datasets-2d)
  // ============================================

  async getDatasets(skip = 0, limit = 100) {
    return this.request(`${API_V1}/datasets-2d?skip=${skip}&limit=${limit}`)
  }

  async getDataset(id: string) {
    return this.request(`${API_V1}/datasets-2d/${id}`)
  }

  async createDataset(data: any) {
    return this.request(`${API_V1}/datasets-2d/`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateDataset(id: string, data: any) {
    return this.request(`${API_V1}/datasets-2d/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteDataset(id: string) {
    return this.request(`${API_V1}/datasets-2d/${id}`, {
      method: 'DELETE',
    })
  }

  async getDatasetImages(datasetId: string, skip = 0, limit = 100) {
    return this.request(`${API_V1}/datasets-2d/${datasetId}/images?skip=${skip}&limit=${limit}`)
  }

  async deleteImage(imageId: string) {
    return this.request(`${API_V1}/datasets-2d/images/${imageId}`, {
      method: 'DELETE',
    })
  }

  // ============================================
  // Dataset Service Endpoints (upload, stats)
  // ============================================

  async uploadDatasetFolder(data: {
    source_folder: string
    dataset_name: string
    description?: string
    owner_id?: string
    inference_metadata_path?: string
  }) {
    return this.request(`${API_V1}/dataset-service/upload-folder`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getDatasetStats(id: string) {
    return this.request(`${API_V1}/dataset-service/${id}/stats`)
  }

  async getDatasetDetectionStats(id: string, data: {
    detection_model_id: string  // Backend expects this field name
    conf_threshold?: number
  }) {
    return this.request(`${API_V1}/dataset-service/${id}/detection-stats`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async deleteDatasetWithFiles(id: string) {
    return this.request(`${API_V1}/dataset-service/${id}`, {
      method: 'DELETE',
    })
  }

  // ============================================
  // Models Endpoints
  // ============================================

  async getModels(skip = 0, limit = 100) {
    return this.request(`${API_V1}/models?skip=${skip}&limit=${limit}`)
  }

  async getModel(id: string) {
    return this.request(`${API_V1}/models/${id}`)
  }

  async createModel(data: any) {
    return this.request(`${API_V1}/models/`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ============================================
  // Adversarial Patch Endpoints
  // ============================================

  async generateAdversarialPatch(data: {
    patch_name: string
    model_id: string
    dataset_id: string
    target_class: string
    plugin_name?: string
    patch_size?: number
    area_ratio?: number
    epsilon?: number
    alpha?: number
    iterations?: number
    batch_size?: number
    description?: string
    created_by?: string
    session_id?: string
  }) {
    return this.request(`${API_V1}/adversarial-patch/patches/generate`, {
      method: 'POST',
      body: JSON.stringify({
        plugin_name: 'global_pgd_2d',
        patch_size: 100,
        area_ratio: 0.3,
        epsilon: 0.6,
        alpha: 0.03,
        iterations: 100,
        batch_size: 8,
        ...data,
      }),
    })
  }

  async getPatch(patchId: string) {
    return this.request(`${API_V1}/adversarial-patch/patches/${patchId}`)
  }

  async getPatchImage(patchId: string) {
    const url = `${this.baseURL}${API_V1}/adversarial-patch/patches/${patchId}/image`
    return url // 이미지 URL 반환
  }

  async downloadPatch(patchId: string): Promise<void> {
    const url = `${this.baseURL}${API_V1}/adversarial-patch/patches/${patchId}/download`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `patch_${patchId}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  }

  async listPatches(skip = 0, limit = 100, targetClass?: string) {
    let endpoint = `${API_V1}/adversarial-patch/patches?skip=${skip}&limit=${limit}`
    if (targetClass) {
      endpoint += `&target_class=${targetClass}`
    }
    return this.request(endpoint)
  }

  async generateAttackDataset(data: {
    attack_dataset_name: string
    model_id: string  // Changed from detection_model_id to match backend
    base_dataset_id: string
    patch_id: string
    target_class: string
    patch_scale?: number
    description?: string
    created_by?: string
  }) {
    return this.request(`${API_V1}/adversarial-patch/attack-datasets/generate`, {
      method: 'POST',
      body: JSON.stringify({
        patch_scale: 0.3,
        ...data,
      }),
    })
  }

  async getAttackDataset(attackId: string) {
    return this.request(`${API_V1}/adversarial-patch/attack-datasets/${attackId}`)
  }

  async downloadAttackDataset(attackId: string): Promise<void> {
    const url = `${this.baseURL}${API_V1}/adversarial-patch/attack-datasets/${attackId}/download`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `attack_dataset_${attackId}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  }

  async listAttackDatasets(skip = 0, limit = 100, targetClass?: string) {
    let endpoint = `${API_V1}/adversarial-patch/attack-datasets?skip=${skip}&limit=${limit}`
    if (targetClass) {
      endpoint += `&target_class=${targetClass}`
    }
    return this.request(endpoint)
  }

  // ============================================
  // Noise Attack Endpoints
  // ============================================

  async generateFGSMAttack(data: {
    attack_dataset_name: string
    detection_model_id: string
    base_dataset_id: string
    epsilon?: number
    targeted?: boolean
    target_class?: string
    description?: string
    created_by?: string
    session_id?: string
  }) {
    return this.request(`${API_V1}/noise-attack/fgsm/generate`, {
      method: 'POST',
      body: JSON.stringify({
        epsilon: 8.0,
        targeted: false,
        ...data,
      }),
    })
  }

  async generatePGDAttack(data: {
    attack_dataset_name: string
    detection_model_id: string
    base_dataset_id: string
    epsilon?: number
    alpha?: number
    iterations?: number
    targeted?: boolean
    target_class?: string
    description?: string
    created_by?: string
    session_id?: string
  }) {
    return this.request(`${API_V1}/noise-attack/pgd/generate`, {
      method: 'POST',
      body: JSON.stringify({
        epsilon: 8.0,
        alpha: 2.0,
        iterations: 10,
        targeted: false,
        ...data,
      }),
    })
  }

  async generateGaussianNoise(data: {
    attack_dataset_name: string
    base_dataset_id: string
    mean?: number
    std?: number
    target_class: string
    description?: string
    created_by?: string
    session_id?: string
  }) {
    return this.request(`${API_V1}/noise-attack/gaussian/generate`, {
      method: 'POST',
      body: JSON.stringify({
        mean: 0.0,
        std: 25.0,
        ...data,
      }),
    })
  }

  async generateUniformNoise(data: {
    attack_dataset_name: string
    base_dataset_id: string
    low?: number
    high?: number
    target_class: string
    description?: string
    created_by?: string
    session_id?: string
  }) {
    return this.request(`${API_V1}/noise-attack/uniform/generate`, {
      method: 'POST',
      body: JSON.stringify({
        low: -25.0,
        high: 25.0,
        ...data,
      }),
    })
  }

  async generateIterativeGradientAttack(data: {
    attack_dataset_name: string
    detection_model_id: string
    base_dataset_id: string
    max_iterations?: number
    step_size?: number
    epsilon?: number
    ncc_threshold?: number
    stop_threshold?: number
    target_class: string
    description?: string
    created_by?: string
    session_id?: string
  }) {
    return this.request(`${API_V1}/noise-attack/iterative-gradient/generate`, {
      method: 'POST',
      body: JSON.stringify({
        max_iterations: 10000,
        step_size: 1.0,
        epsilon: 0.03,
        ncc_threshold: 0.6,
        stop_threshold: 0.1,
        ...data,
      }),
    })
  }

  // ============================================
  // Evaluation Endpoints
  // ============================================

  async createEvaluationRun(data: any) {
    // Remove null/undefined values to avoid database constraint violations
    const cleanData = Object.fromEntries(
      Object.entries(data).filter(([_, v]) => v != null)
    )
    return this.request(`${API_V1}/evaluation/runs`, {
      method: 'POST',
      body: JSON.stringify(cleanData),
    })
  }

  async getEvaluationRun(runId: string) {
    return this.request(`${API_V1}/evaluation/runs/${runId}`)
  }

  async listEvaluationRuns(params: {
    page?: number
    page_size?: number
    phase?: string
    status?: string
    model_id?: string
    base_dataset_id?: string
    attack_dataset_id?: string
  }) {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, String(value))
      }
    })
    return this.request(`${API_V1}/evaluation/runs?${queryParams.toString()}`)
  }

  async updateEvaluationRun(runId: string, data: any) {
    return this.request(`${API_V1}/evaluation/runs/${runId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteEvaluationRun(runId: string) {
    return this.request(`${API_V1}/evaluation/runs/${runId}`, {
      method: 'DELETE',
    })
  }

  async executeEvaluationRun(
    runId: string,
    params: {
      conf_threshold?: number
      iou_threshold?: number
      session_id?: string
    } = {}
  ) {
    const queryParams = new URLSearchParams()
    if (params.conf_threshold !== undefined) {
      queryParams.append('conf_threshold', String(params.conf_threshold))
    }
    if (params.iou_threshold !== undefined) {
      queryParams.append('iou_threshold', String(params.iou_threshold))
    }

    // Build request body - only include session_id if provided
    const body = params.session_id ? { session_id: params.session_id } : {}

    return this.request(`${API_V1}/evaluation/runs/${runId}/execute?${queryParams.toString()}`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async compareRobustness(data: {
    clean_run_id: string
    adv_run_id: string
  }) {
    return this.request(`${API_V1}/evaluation/runs/compare-robustness`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getEvaluationClassMetrics(runId: string) {
    return this.request(`${API_V1}/evaluation/runs/${runId}/class-metrics`)
  }

  async getEvaluationItems(runId: string, page = 1, pageSize = 100) {
    return this.request(`${API_V1}/evaluation/runs/${runId}/items?page=${page}&page_size=${pageSize}`)
  }

  // ============================================
  // Experiments Endpoints
  // ============================================

  async createExperiment(data: any) {
    return this.request(`${API_V1}/experiments/`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getExperiment(id: string) {
    return this.request(`${API_V1}/experiments/${id}`)
  }

  async listExperiments(skip = 0, limit = 100) {
    return this.request(`${API_V1}/experiments?skip=${skip}&limit=${limit}`)
  }

  async updateExperiment(id: string, data: any) {
    return this.request(`${API_V1}/experiments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteExperiment(id: string) {
    return this.request(`${API_V1}/experiments/${id}`, {
      method: 'DELETE',
    })
  }

  // ============================================
  // Annotations Endpoints
  // ============================================

  async getImageAnnotations(
    imageId: string,
    options?: {
      annotation_type?: 'bbox' | 'polygon' | 'keypoint' | 'segmentation'
      min_confidence?: number
    }
  ) {
    let endpoint = `${API_V1}/annotations/image/${imageId}`
    const params = new URLSearchParams()

    if (options?.annotation_type) {
      params.append('annotation_type', options.annotation_type)
    }
    if (options?.min_confidence !== undefined) {
      params.append('min_confidence', options.min_confidence.toString())
    }

    if (params.toString()) {
      endpoint += `?${params.toString()}`
    }

    return this.request(endpoint)
  }

  async getDatasetAnnotationsSummary(
    datasetId: string,
    minConfidence?: number
  ) {
    let endpoint = `${API_V1}/annotations/dataset/${datasetId}`
    if (minConfidence !== undefined) {
      endpoint += `?min_confidence=${minConfidence}`
    }
    return this.request(endpoint)
  }

  async createAnnotationsBulk(
    imageId: string,
    annotations: Array<{
      annotation_type: 'bbox' | 'polygon' | 'keypoint' | 'segmentation'
      class_name: string
      class_index?: number
      bbox_x?: number
      bbox_y?: number
      bbox_width?: number
      bbox_height?: number
      polygon_data?: any[]
      keypoints?: any[]
      confidence?: number
      is_crowd?: boolean
      metadata?: Record<string, any>
    }>
  ) {
    return this.request(`${API_V1}/annotations/bulk?image_id=${imageId}`, {
      method: 'POST',
      body: JSON.stringify(annotations),
    })
  }

  async deleteImageAnnotations(
    imageId: string,
    annotationType?: 'bbox' | 'polygon' | 'keypoint' | 'segmentation'
  ) {
    let endpoint = `${API_V1}/annotations/image/${imageId}`
    if (annotationType) {
      endpoint += `?annotation_type=${annotationType}`
    }
    return this.request(endpoint, {
      method: 'DELETE',
    })
  }

  // ============================================
  // Storage Endpoints
  // ============================================

  async getStorageInfo() {
    return this.request(`${API_V1}/storage/info`)
  }

  async listStorageFiles(path?: string) {
    const endpoint = path
      ? `${API_V1}/storage/list?path=${encodeURIComponent(path)}`
      : `${API_V1}/storage/list`
    return this.request(endpoint)
  }
}

// Export singleton instance
export const apiClient = new APIClient()

// Export class for custom instances
export default APIClient
