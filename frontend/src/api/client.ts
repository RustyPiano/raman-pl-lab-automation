import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Extract error message from unknown error type
 * Handles axios errors, Error instances, and unknown types safely
 */
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '未知错误';
};

export interface WorkflowConfig {
  sample_id?: string;
  operator?: string;
  laser_power?: number;
  integration_time?: number;
  accumulations?: number;
  subtract_background?: boolean;
  [key: string]: any;
}

export interface ConfigListResponse {
  configs: string[];
}

export interface JobProgress {
  current_step: string | null;
  total_steps: number | null;
  completed_steps: number;
  message: string | null;
  percentage: number | null;
}

export interface ApiJobStatus {
  id: string;
  type: string;
  status: 'pending' | 'running' | 'stopping' | 'completed' | 'failed' | 'stopped';
  progress: JobProgress;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  result?: any;
}

export interface JobStatus {
  id: string;
  type: string;
  status: ApiJobStatus['status'];
  progress: number;
  current_step?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  result?: any;
}

export interface ProgressUpdate {
  type: 'status' | 'progress' | 'error' | 'pong';
  status?: ApiJobStatus['status'];
  progress?: JobProgress;
  step?: string;
  completed?: number;
  total?: number;
  message?: string;
  percentage?: number | null;
  result?: any;
  error?: string;
}

export const apiClient = {
  // 获取所有配置
  getConfigs: () => api.get<ConfigListResponse>('/configs'),

  // 获取特定配置
  getConfig: (name: string) => api.get<any>(`/configs/${name}`),

  // 启动单点测量
  startSinglePoint: (data: {
    config_path: string;
    devices_path?: string;
    mode: 'dry_run' | 'simulated' | 'real';
    confirm_real?: boolean;
  }) => api.post<ApiJobStatus>('/workflow/single-point', data),

  // 获取任务状态
  getJobStatus: (jobId: string) => api.get<ApiJobStatus>(`/workflow/jobs/${jobId}`),

  // 停止任务
  stopJob: (jobId: string) => api.post<{ status: string; job_id: string }>(`/workflow/jobs/${jobId}/stop`),

  // 获取所有任务
  getJobs: () => api.get<ApiJobStatus[]>('/workflow/jobs'),
};

export default apiClient;
