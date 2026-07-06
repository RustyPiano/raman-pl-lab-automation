import { create } from 'zustand';
import apiClient, { getErrorMessage } from '@/api/client';
import type { ApiJobStatus, JobStatus, ProgressUpdate } from '@/api/client';

/**
 * Construct WebSocket URL with environment variable support
 * Handles both development and production environments
 */
const getWebSocketUrl = (jobId: string): string => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = import.meta.env.VITE_WS_HOST || window.location.host;
  return `${wsProtocol}//${wsHost}/api/workflow/ws/jobs/${jobId}`;
};

const toJobStatus = (job: ApiJobStatus): JobStatus => ({
  ...job,
  progress: job.progress.percentage ?? 0,
  current_step: job.progress.current_step,
});

interface WorkflowState {
  currentJob: JobStatus | null;
  jobs: JobStatus[];
  wsConnection: WebSocket | null;
  logs: string[];

  // Actions
  startSinglePoint: (
    configPath: string,
    mode: 'dry_run' | 'simulated' | 'real',
    confirmReal?: boolean
  ) => Promise<string>;
  connectWebSocket: (jobId: string) => void;
  disconnectWebSocket: () => void;
  updateProgress: (update: ProgressUpdate) => void;
  stopJob: (jobId: string) => Promise<void>;
  fetchJobs: () => Promise<void>;
  addLog: (message: string) => void;
  clearLogs: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  currentJob: null,
  jobs: [],
  wsConnection: null,
  logs: [],

  startSinglePoint: async (configPath, mode, confirmReal = false) => {
    try {
      const response = await apiClient.startSinglePoint({
        config_path: configPath,
        mode,
        confirm_real: confirmReal,
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
      wsConnection.close();
    }

    const wsUrl = getWebSocketUrl(jobId);

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      get().addLog('🔗 Connected to job stream');
    };

    ws.onmessage = (event) => {
      try {
        const update: ProgressUpdate = JSON.parse(event.data);
        get().updateProgress(update);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      get().addLog('❌ Connection error');
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed', event.code, event.reason);

      if (event.code !== 1000 && event.code !== 1001) {
        // Abnormal closure, attempt reconnect after 3 seconds
        get().addLog('⚠️ Connection lost, reconnecting...');
        setTimeout(() => {
          const currentJob = get().currentJob;
          if (currentJob && (currentJob.status === 'running' || currentJob.status === 'stopping' || currentJob.status === 'pending')) {
            get().connectWebSocket(jobId);
          }
        }, 3000);
      } else {
        get().addLog('🔌 Disconnected');
      }

      set({ wsConnection: null });
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

  updateProgress: (update: ProgressUpdate) => {
    if (update.type === 'pong') return;

    set((state) => ({
      currentJob: state.currentJob ? {
        ...state.currentJob,
        status: update.type === 'error' ? 'failed' : update.status ?? state.currentJob.status,
        progress: update.type === 'progress'
          ? update.percentage ?? state.currentJob.progress
          : update.progress?.percentage ?? state.currentJob.progress,
        current_step: update.type === 'progress'
          ? update.step ?? state.currentJob.current_step
          : update.progress?.current_step ?? state.currentJob.current_step,
        result: update.result ?? state.currentJob.result,
        error: update.error ?? state.currentJob.error,
      } : null,
    }));

    // Add log message
    const status = update.type === 'error' ? 'failed' : update.status;
    const emoji = status === 'completed' ? '✅' :
                  status === 'failed' ? '❌' :
                  status === 'running' || update.type === 'progress' ? '▶️' : '⏸️';
    const message = update.message ?? update.error ?? update.step ?? status;
    if (message) get().addLog(`${emoji} ${message}`);

    // Disconnect WebSocket if job is finished
    if (status === 'completed' || status === 'failed' || status === 'stopped') {
      setTimeout(() => {
        get().disconnectWebSocket();
      }, 1000);
    }
  },

  stopJob: async (jobId: string) => {
    try {
      await apiClient.stopJob(jobId);
      get().addLog('⏹️ 停止请求已发送，等待硬件安全收尾（激光关闭确认后才会真正停止）…');

      // Honest semantics: mark as "stopping" and keep the WebSocket open so the
      // backend's real terminal status (stopped/completed/failed) reaches the UI.
      set((state) => ({
        currentJob: state.currentJob ? {
          ...state.currentJob,
          status: 'stopping',
        } : null,
      }));
    } catch (error) {
      const message = getErrorMessage(error);
      throw new Error(message);
    }
  },

  fetchJobs: async () => {
    try {
      const response = await apiClient.getJobs();
      set({ jobs: response.data.map(toJobStatus) });
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
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
