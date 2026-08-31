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
    const detail = error.response?.data?.detail;
    return typeof detail === 'string' ? detail : JSON.stringify(detail) ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '未知错误';
};

export type RunMode = 'dry_run' | 'simulated' | 'real';
export type JobState = 'pending' | 'running' | 'stopping' | 'completed' | 'failed' | 'stopped';
export type ConfigType = 'single_point' | 'tray';

export interface SpectrumResult {
  output_directory: string;
  mode: RunMode;
  x: number[];
  x_axis_type: 'pixel_index' | 'wavelength_nm';
  wavelengths: number[] | null;
  spectrum: {
    raw: number[];
    corrected: number[] | null;
  };
  metadata: {
    sample_id?: string;
    operator?: string;
    timestamp?: string;
    camera?: { exposure_ms?: number };
  };
  warnings: string[];
}

export interface SinglePointOverrides {
  sample_id?: string;
  operator?: string;
  subtract_background?: boolean;
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
  status: JobState;
  progress: JobProgress;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  result?: SpectrumResult | null;
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
  result?: SpectrumResult | null;
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
  result?: SpectrumResult | null;
  error?: string;
}

export interface TrayWafer {
  index: number;
  row: number;
  col: number;
  x_um: number;
  y_um: number;
}

export interface TrayPreview {
  config_path: string;
  sample_id: string;
  operator: string;
  layout: {
    rows: number;
    cols: number;
    pitch_x_um: number;
    pitch_y_um: number;
    order: 'row_major' | 'serpentine';
  };
  pattern: {
    repeats_per_point: number;
    surrounding_count: number;
    surrounding_distance_um: number;
    burn_threshold: number;
  };
  wafers: TrayWafer[];
  actions: string[];
  summary: {
    wafer_count: number;
    sample_centers: number;
    measurement_points: number;
    acquisitions: number;
    burn_checks: number;
    action_count: number;
  };
  real_available: boolean;
  real_unavailable_reason: string;
}

export interface DeviceScan {
  runtime_mode: string;
  serial_ports: string[];
  configured_stage_port: string;
  waynelabs: {
    configured_port: string;
    device: unknown;
    error?: string;
  };
  zolix_devices: string[];
  dfield_available: boolean;
  [key: string]: unknown;
}

export interface DeviceStatus {
  runtime_mode: string;
  scan: DeviceScan;
  doctor: Record<string, unknown>;
}

export interface LightStatus {
  type: string;
  manual_control: boolean;
  available: boolean;
  hardware_state: {
    voltage_register?: number;
    channel_states?: Record<string, number>;
    laser_state?: string;
    led_state?: string;
    [key: string]: unknown;
  } | null;
}

export interface HistoryRecord {
  id: string;
  source: 'measurement';
  type: 'single_point';
  status: 'completed';
  created_at: string;
  completed_at: string;
  sample_id: string | null;
  operator: string | null;
  mode: string;
  warnings_count: number;
  files: string[];
}

export interface HistoryDetail {
  record: HistoryRecord;
  result: SpectrumResult;
}

export interface EmergencyStopResponse {
  jobs_cancelled: string[];
  laser_off: string;
  message?: string;
}

export const apiClient = {
  getHealth: () => api.get<{ status: string; timestamp: string }>('/health'),

  // 获取所有配置
  getConfigs: (configType: ConfigType = 'single_point') =>
    api.get<ConfigListResponse>('/configs', { params: { config_type: configType } }),

  // 获取特定配置
  getConfig: (name: string) => api.get<{ name: string; content: string }>(`/configs/${name}`),

  // 启动单点测量
  startSinglePoint: (data: {
    config_path: string;
    devices_path?: string;
    mode: RunMode;
    confirm_real?: boolean;
  } & SinglePointOverrides) => api.post<ApiJobStatus>('/workflow/single-point', data),

  // 获取任务状态
  getJobStatus: (jobId: string) => api.get<ApiJobStatus>(`/workflow/jobs/${jobId}`),

  // 停止任务
  stopJob: (jobId: string) => api.post<{ status: JobState; job_id: string }>(`/workflow/jobs/${jobId}/stop`),

  // 获取所有任务
  getJobs: () => api.get<ApiJobStatus[]>('/workflow/jobs'),

  previewTray: (configPath: string) =>
    api.post<TrayPreview>('/workflow/tray/preview', { config_path: configPath }),

  getDeviceStatus: () => api.get<DeviceStatus>('/devices/status'),
  scanDevices: () => api.post<DeviceScan>('/devices/scan'),
  getLightStatus: () => api.get<LightStatus>('/devices/light/status'),
  turnLightOff: () => api.post<{ status: string; message: string; cancelled_jobs?: string[] }>('/devices/light/off'),
  emergencyStop: () => api.post<EmergencyStopResponse>('/emergency-stop'),

  getHistory: () => api.get<HistoryRecord[]>('/history'),
  getHistoryDetail: (recordId: string) => api.get<HistoryDetail>(`/history/${encodeURIComponent(recordId)}`),
  historyFileUrl: (recordId: string, filename: string) =>
    `/api/history/${encodeURIComponent(recordId)}/files/${encodeURIComponent(filename)}`,
};

export default apiClient;
