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

export interface JobStartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  progress: number;
  current_step?: string;
  result?: any;
  error?: string;
  warnings?: string[];
}

export interface ProgressUpdate {
  job_id: string;
  progress: number;
  current_step: string;
  message: string;
  status: string;
  result?: any;
  error?: string;
  warnings?: string[];
}

export const apiClient = {
  // 获取所有配置
  getConfigs: () => api.get<string[]>('/configs'),

  // 获取特定配置
  getConfig: (name: string) => api.get<any>(`/configs/${name}`),

  // 启动单点测量
  startSinglePoint: (data: {
    config_name: string;
    mode: 'dry_run' | 'simulated' | 'real';
    overrides?: WorkflowConfig;
  }) => api.post<JobStartResponse>('/workflow/single-point', data),

  // 获取任务状态
  getJobStatus: (jobId: string) => api.get<JobStatus>(`/workflow/jobs/${jobId}`),

  // 停止任务
  stopJob: (jobId: string) => api.post<{ message: string }>(`/workflow/jobs/${jobId}/stop`),

  // 获取所有任务
  getJobs: () => api.get<JobStatus[]>('/workflow/jobs'),
};

export default apiClient;
