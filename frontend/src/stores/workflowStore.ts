import { create } from 'zustand';
import apiClient, { getErrorMessage } from '@/api/client';
import type { JobStatus, ProgressUpdate, WorkflowConfig } from '@/api/client';

/**
 * Construct WebSocket URL with environment variable support
 * Handles both development and production environments
 */
const getWebSocketUrl = (jobId: string): string => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = import.meta.env.VITE_WS_HOST || window.location.host;
  return `${wsProtocol}//${wsHost}/ws/jobs/${jobId}`;
};

interface WorkflowState {
  currentJob: JobStatus | null;
  jobs: JobStatus[];
  wsConnection: WebSocket | null;
  logs: string[];

  // Actions
  startSinglePoint: (
    configName: string,
    mode: 'dry_run' | 'simulated' | 'real',
    overrides?: WorkflowConfig
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

  startSinglePoint: async (configName, mode, overrides) => {
    try {
      const response = await apiClient.startSinglePoint({
        config_name: configName,
        mode,
        overrides,
      });

      const jobId = response.data.job_id;

      // Fetch initial job status
      const statusResponse = await apiClient.getJobStatus(jobId);
      set({ currentJob: statusResponse.data });

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
          if (currentJob && currentJob.status === 'running') {
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
    set((state) => ({
      currentJob: state.currentJob ? {
        ...state.currentJob,
        progress: update.progress,
        current_step: update.current_step,
        status: update.status as any,
        result: update.result || state.currentJob.result,
        error: update.error,
        warnings: update.warnings,
      } : null,
    }));

    // Add log message
    const emoji = update.status === 'completed' ? '✅' :
                  update.status === 'failed' ? '❌' :
                  update.status === 'running' ? '▶️' : '⏸️';
    get().addLog(`${emoji} ${update.message}`);

    // Disconnect WebSocket if job is finished
    if (update.status === 'completed' || update.status === 'failed' || update.status === 'stopped') {
      setTimeout(() => {
        get().disconnectWebSocket();
      }, 1000);
    }
  },

  stopJob: async (jobId: string) => {
    try {
      await apiClient.stopJob(jobId);
      get().addLog('⏹️ Stop requested');

      // Update local state
      set((state) => ({
        currentJob: state.currentJob ? {
          ...state.currentJob,
          status: 'stopped',
        } : null,
      }));

      // Disconnect WebSocket
      get().disconnectWebSocket();
    } catch (error) {
      const message = getErrorMessage(error);
      throw new Error(message);
    }
  },

  fetchJobs: async () => {
    try {
      const response = await apiClient.getJobs();
      set({ jobs: response.data });
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
