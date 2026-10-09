import { create } from 'zustand';
import apiClient, { getErrorMessage } from '@/api/client';
import type {
  ApiJobStatus,
  JobStatus,
  ProgressUpdate,
  RunMode,
  SinglePointOverrides,
} from '@/api/client';

// 开发时由 Vite 代理 WebSocket，生产时与页面同源
const getWebSocketUrl = (jobId: string): string => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${window.location.host}/api/workflow/ws/jobs/${jobId}`;
};

const toJobStatus = (job: ApiJobStatus): JobStatus => ({
  ...job,
  progress: job.progress.percentage ?? 0,
  current_step: job.progress.current_step,
});

const isActive = (job: JobStatus) => ['pending', 'running', 'stopping'].includes(job.status);

interface WorkflowState {
  currentJob: JobStatus | null;
  wsConnection: WebSocket | null;
  logs: string[];

  // Actions
  startSinglePoint: (
    configPath: string,
    mode: RunMode,
    confirmReal?: boolean,
    overrides?: SinglePointOverrides,
  ) => Promise<string>;
  connectWebSocket: (jobId: string) => void;
  disconnectWebSocket: () => void;
  updateProgress: (update: ProgressUpdate, jobId: string) => void;
  stopJob: (jobId: string) => Promise<void>;
  fetchJobs: () => Promise<void>;
  addLog: (message: string) => void;
  clearLogs: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  currentJob: null,
  wsConnection: null,
  logs: [],

  startSinglePoint: async (configPath, mode, confirmReal = false, overrides = {}) => {
    try {
      const response = await apiClient.startSinglePoint({
        config_path: configPath,
        mode,
        confirm_real: confirmReal,
        ...overrides,
      });

      const jobId = response.data.id;
      set({ currentJob: toJobStatus(response.data) });

      // Connect WebSocket
      get().connectWebSocket(jobId);

      return jobId;
    } catch (error) {
      const message = getErrorMessage(error);
      throw new Error(message);
    }
  },

  connectWebSocket: (jobId: string) => {
    const { wsConnection } = get();

    // Close existing connection
    if (wsConnection) {
      wsConnection.close(1000, 'Replaced by a newer job stream');
    }

    const wsUrl = getWebSocketUrl(jobId);

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      if (get().wsConnection !== ws) return;
      get().addLog('已连接任务推送');
    };

    ws.onmessage = (event) => {
      try {
        const update: ProgressUpdate = JSON.parse(event.data);
        get().updateProgress(update, jobId);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      if (get().wsConnection !== ws) return;
      console.error('WebSocket error:', error);
      get().addLog('任务推送连接出错');
    };

    ws.onclose = (event) => {
      if (get().wsConnection !== ws) return;

      set({ wsConnection: null });

      if (event.code !== 1000 && event.code !== 1001) {
        // Abnormal closure, attempt reconnect after 3 seconds
        get().addLog('任务推送中断，3 秒后重连');
        setTimeout(() => {
          const currentJob = get().currentJob;
          if (
            currentJob?.id === jobId &&
            get().wsConnection === null &&
            (currentJob.status === 'running' || currentJob.status === 'stopping' || currentJob.status === 'pending')
          ) {
            get().connectWebSocket(jobId);
          }
        }, 3000);
      }
    };

    set({ wsConnection: ws });
  },

  disconnectWebSocket: () => {
    const { wsConnection } = get();
    if (wsConnection) {
      wsConnection.close(1000, 'User disconnect');
      set({ wsConnection: null });
    }
  },

  updateProgress: (update: ProgressUpdate, jobId: string) => {
    if (get().currentJob?.id !== jobId) return;
    if (!isActive(get().currentJob!) && update.status && ['pending', 'running', 'stopping'].includes(update.status)) return;

    set((state) => ({
      currentJob: state.currentJob ? {
        ...state.currentJob,
        status: update.type === 'error' ? 'failed' : update.status ?? state.currentJob.status,
        progress: update.progress?.percentage ?? state.currentJob.progress,
        current_step: update.progress?.current_step ?? state.currentJob.current_step,
        result: update.result ?? state.currentJob.result,
        error: update.error ?? state.currentJob.error,
      } : null,
    }));

    const status = update.type === 'error' ? 'failed' : update.status;
    const message = update.message ?? update.error;
    if (message) get().addLog(message);

    // Disconnect WebSocket if job is finished
    if (status === 'completed' || status === 'failed' || status === 'stopped') {
      setTimeout(() => {
        if (get().currentJob?.id === jobId) get().disconnectWebSocket();
      }, 1000);
    }
  },

  stopJob: async (jobId: string) => {
    try {
      const response = await apiClient.stopJob(jobId);

      // The backend pushes the stop message; mark as "stopping" and keep the WebSocket open so the
      // backend's real terminal status (stopped/completed/failed) reaches the UI.
      set((state) => ({
        currentJob: state.currentJob?.id === jobId && isActive(state.currentJob) ? {
          ...state.currentJob,
          status: response.data.status,
        } : state.currentJob,
      }));
    } catch (error) {
      const message = getErrorMessage(error);
      throw new Error(message);
    }
  },

  fetchJobs: async () => {
    const previousId = get().currentJob?.id;
    const response = await apiClient.getJobs();
    const jobs = response.data.map(toJobStatus);
    // A response started before a new submission must not replace the new job.
    if (get().currentJob?.id !== previousId) return;
    let currentJob = jobs.find((job) => job.id === previousId)
      ?? jobs.find(isActive)
      ?? jobs.at(-1)
      ?? null;
    const previous = get().currentJob;
    if (previous && !isActive(previous) && currentJob?.id === previous.id && isActive(currentJob)) {
      currentJob = previous;
    }
    set({ currentJob });
    if (currentJob && isActive(currentJob) && (!get().wsConnection || currentJob.id !== previousId)) {
      get().connectWebSocket(currentJob.id);
    } else if (!currentJob || !isActive(currentJob)) {
      get().disconnectWebSocket();
    }
  },

  addLog: (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    set((state) => ({
      logs: [...state.logs.slice(-99), `[${timestamp}] ${message}`],
    }));
  },

  clearLogs: () => {
    set({ logs: [] });
  },
}));
