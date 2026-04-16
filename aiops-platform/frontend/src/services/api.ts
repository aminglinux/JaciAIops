import axios from 'axios';
import { message } from 'antd';
import type {
  Log,
  LogStats,
  LogSourceConfig,
  LogSourceConfigPayload,
  AgentTask,
  DiagnoseRequest,
  DiagnoseResponse,
  AlertAnalyzeRequest,
  AlertAnalysisResult,
  AlertEventSummary,
  AlertEventDetail,
  AlertWebhookSecurityConfig,
  AlertWebhookSecurityConfigPayload,
  ApiResponse,
  LoginParams,
  LoginResult,
  UserInfo,
  RegisterParams,
  LLMProvider,
  LLMModel,
  LLMBinding,
  BindingFormValues,
  ModelFormValues,
  ProviderFormValues,
  DiscoveredModel,
  LLMRuntimeConfig,
  RuntimeAnomalyResponse,
  RuntimeDependencyResponse,
  RuntimeGraphConfig,
  RuntimeGraphConfigPayload,
  RuntimeTopologySnapshot,
  ManualGraphEntryPayload,
  ChatSessionSummary,
  ChatHistoryMessage,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    } else if (error.response?.status === 403) {
      message.error('无权限访问');
    } else if (error.response?.data?.message) {
      message.error(error.response.data.message);
    }
    return Promise.reject(error);
  }
);

export const userApi = {
  login: async (data: LoginParams): Promise<LoginResult> => {
    const formData = new FormData();
    formData.append('username', data.username);
    formData.append('password', data.password);
    const response = await api.post<ApiResponse<LoginResult>>('/auth/login', formData);
    return response.data.data;
  },

  register: async (data: RegisterParams): Promise<UserInfo> => {
    const response = await api.post<ApiResponse<UserInfo>>('/auth/register', data);
    return response.data.data;
  },

  getUserInfo: async (): Promise<UserInfo> => {
    const response = await api.get<ApiResponse<UserInfo>>('/auth/me');
    return response.data.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  getUsers: async (): Promise<UserInfo[]> => {
    const response = await api.get<ApiResponse<UserInfo[]>>('/auth/users');
    return response.data.data;
  },
};

export const logsApi = {
  getLogs: async (params?: { level?: string; is_anomaly?: boolean; limit?: number; offset?: number }): Promise<Log[]> => {
    const response = await api.get('/logs', { params });
    return response.data;
  },

  queryLogs: async (params?: {
    source_type?: string;
    keyword?: string;
    level?: string;
    levels?: string;
    service?: string;
    start_time?: string;
    end_time?: string;
    incident_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<Log[]> => {
    const response = await api.get('/logs/query', { params });
    return response.data;
  },

  uploadFile: async (file: File): Promise<{ message: string; filename: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/logs/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  submitFeedback: async (logId: number, feedbackType: boolean): Promise<{ message: string; log_id: number }> => {
    const response = await api.post(`/logs/${logId}/feedback`, { feedback_type: feedbackType });
    return response.data;
  },

  getStats: async (): Promise<LogStats> => {
    const response = await api.get('/logs/stats');
    return response.data;
  },

  getConfig: async (): Promise<LogSourceConfig> => {
    const response = await api.get<ApiResponse<LogSourceConfig>>('/logs/config');
    return response.data.data;
  },

  updateConfig: async (payload: LogSourceConfigPayload): Promise<LogSourceConfig> => {
    const response = await api.put<ApiResponse<LogSourceConfig>>('/logs/config', payload);
    return response.data.data;
  },

  ingestLog: async (log: { level: string; content: string; source?: string }): Promise<Log> => {
    const response = await api.post('/logs/ingest', log);
    return response.data;
  },
};

export const agentApi = {
  diagnose: async (request: DiagnoseRequest): Promise<DiagnoseResponse> => {
    const response = await api.post('/agent/diagnose', request);
    return response.data;
  },

  getTaskStatus: async (taskId: string): Promise<AgentTask> => {
    const response = await api.get(`/agent/status/${taskId}`);
    return response.data;
  },

  getHistory: async (limit: number = 10): Promise<{ tasks: Array<{ task_id: string; user_input: string; status: string; created_at: string }> }> => {
    const response = await api.get('/agent/history', { params: { limit } });
    return response.data;
  },
};

export const alertsApi = {
  analyze: async (request: AlertAnalyzeRequest): Promise<AlertAnalysisResult> => {
    const response = await api.post<AlertAnalysisResult>('/alerts/analyze', request);
    return response.data;
  },

  listEvents: async (params?: { limit?: number; source?: string; status?: string }): Promise<{ events: AlertEventSummary[] }> => {
    const response = await api.get<{ events: AlertEventSummary[] }>('/alerts/events', { params });
    return response.data;
  },

  getEvent: async (eventId: number): Promise<AlertEventDetail> => {
    const response = await api.get<AlertEventDetail>(`/alerts/events/${eventId}`);
    return response.data;
  },

  getSecurityConfig: async (): Promise<AlertWebhookSecurityConfig> => {
    const response = await api.get<ApiResponse<AlertWebhookSecurityConfig>>('/alerts/security-config');
    return response.data.data;
  },

  updateSecurityConfig: async (payload: AlertWebhookSecurityConfigPayload): Promise<AlertWebhookSecurityConfig> => {
    const response = await api.put<ApiResponse<AlertWebhookSecurityConfig>>('/alerts/security-config', payload);
    return response.data.data;
  },
};

export const knowledgeApi = {
  queryKG: async (service?: string, query?: string): Promise<unknown> => {
    const response = await api.get('/knowledge/query', { params: { service, query } });
    return response.data;
  },

  queryRAG: async (query: string, topK: number = 5): Promise<unknown> => {
    const response = await api.post('/knowledge/rag/query', { query, top_k: topK });
    return response.data;
  },

  chat: async (question: string, analyzeProblem: boolean = false, sessionId?: string): Promise<unknown> => {
    const response = await api.post('/knowledge/qa/chat', {
      question,
      analyze_problem: analyzeProblem,
      session_id: sessionId,
    });
    return response.data;
  },

  listChatSessions: async (): Promise<{ sessions: ChatSessionSummary[] }> => {
    const response = await api.get('/knowledge/qa/sessions');
    return response.data;
  },

  getChatSession: async (sessionId: string): Promise<{ session: ChatSessionSummary; messages: ChatHistoryMessage[] }> => {
    const response = await api.get(`/knowledge/qa/sessions/${sessionId}`);
    return response.data;
  },

  getTopology: async (service?: string, depth: number = 2): Promise<unknown> => {
    const response = await api.get('/knowledge/topology', { params: { service, depth } });
    return response.data;
  },

  getRuntimeGraphConfig: async (): Promise<RuntimeGraphConfig> => {
    const response = await api.get<ApiResponse<RuntimeGraphConfig>>('/knowledge/runtime-config');
    return response.data.data;
  },

  updateRuntimeGraphConfig: async (payload: RuntimeGraphConfigPayload): Promise<RuntimeGraphConfig> => {
    const response = await api.put<ApiResponse<RuntimeGraphConfig>>('/knowledge/runtime-config', payload);
    return response.data.data;
  },

  createManualEntry: async (payload: ManualGraphEntryPayload): Promise<{ source: string; sourceType: string; relationCreated: boolean }> => {
    const response = await api.post<ApiResponse<{ source: string; sourceType: string; relationCreated: boolean }>>('/knowledge/manual-entry', payload);
    return response.data.data;
  },

  updateGraphNode: async (nodeId: string, payload: { name: string; properties: Record<string, unknown> }): Promise<unknown> => {
    const response = await api.put(`/knowledge/nodes/${nodeId}`, payload);
    return response.data;
  },

  deleteGraphNode: async (nodeId: string): Promise<unknown> => {
    const response = await api.delete(`/knowledge/nodes/${nodeId}`);
    return response.data;
  },

  updateGraphRelation: async (relationId: string, payload: { relation_type: string; properties: Record<string, unknown> }): Promise<unknown> => {
    const response = await api.put(`/knowledge/relations/${relationId}`, payload);
    return response.data;
  },

  deleteGraphRelation: async (relationId: string): Promise<unknown> => {
    const response = await api.delete(`/knowledge/relations/${relationId}`);
    return response.data;
  },

  importGraphData: async (file: File): Promise<{ fileName: string; records: number; nodes: number; relations: number; failed?: number; errors?: Array<{ index: number; error: string }> }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<ApiResponse<{ fileName: string; records: number; nodes: number; relations: number; failed?: number; errors?: Array<{ index: number; error: string }> }>>(
      '/knowledge/import-data',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data.data;
  },
};

export const llmApi = {
  getProviders: async (): Promise<LLMProvider[]> => {
    const response = await api.get<ApiResponse<LLMProvider[]>>('/llm/providers');
    return response.data.data;
  },

  createProvider: async (data: ProviderFormValues): Promise<LLMProvider> => {
    const response = await api.post<ApiResponse<LLMProvider>>('/llm/providers', data);
    return response.data.data;
  },

  updateProvider: async (id: number, data: Partial<ProviderFormValues>): Promise<LLMProvider> => {
    const response = await api.put<ApiResponse<LLMProvider>>(`/llm/providers/${id}`, data);
    return response.data.data;
  },

  deleteProvider: async (id: number): Promise<void> => {
    await api.delete(`/llm/providers/${id}`);
  },

  validateProvider: async (id: number): Promise<{ success: boolean; message: string; detectedCapabilities: Record<string, unknown> }> => {
    const response = await api.post<ApiResponse<{ success: boolean; message: string; detectedCapabilities: Record<string, unknown> }>>(`/llm/providers/${id}/validate`);
    return response.data.data;
  },

  discoverModels: async (id: number): Promise<{ providerId: number; providerName: string; models: DiscoveredModel[] }> => {
    const response = await api.post<ApiResponse<{ providerId: number; providerName: string; models: DiscoveredModel[] }>>(`/llm/providers/${id}/discover-models`);
    return response.data.data;
  },

  syncModels: async (id: number, data: { model_ids?: string[]; overwrite_existing?: boolean }): Promise<{ providerId: number; providerName: string; created: number; updated: number; skipped: number; totalSelected: number }> => {
    const response = await api.post<ApiResponse<{ providerId: number; providerName: string; created: number; updated: number; skipped: number; totalSelected: number }>>(`/llm/providers/${id}/sync-models`, data);
    return response.data.data;
  },

  getModels: async (): Promise<LLMModel[]> => {
    const response = await api.get<ApiResponse<LLMModel[]>>('/llm/models');
    return response.data.data;
  },

  createModel: async (data: ModelFormValues): Promise<LLMModel> => {
    const response = await api.post<ApiResponse<LLMModel>>('/llm/models', data);
    return response.data.data;
  },

  updateModel: async (id: number, data: Partial<ModelFormValues>): Promise<LLMModel> => {
    const response = await api.put<ApiResponse<LLMModel>>(`/llm/models/${id}`, data);
    return response.data.data;
  },

  deleteModel: async (id: number): Promise<void> => {
    await api.delete(`/llm/models/${id}`);
  },

  getBindings: async (): Promise<{ scenes: unknown[]; bindings: LLMBinding[] }> => {
    const response = await api.get<ApiResponse<{ scenes: unknown[]; bindings: LLMBinding[] }>>('/llm/bindings');
    return response.data.data;
  },

  getRuntimeConfig: async (): Promise<LLMRuntimeConfig> => {
    const response = await api.get<ApiResponse<LLMRuntimeConfig>>('/llm/runtime-config');
    return response.data.data;
  },

  updateBinding: async (sceneKey: string, data: BindingFormValues): Promise<LLMBinding> => {
    const response = await api.put<ApiResponse<LLMBinding>>(`/llm/bindings/${sceneKey}`, data);
    return response.data.data;
  },

};

export const observabilityRuntimeApi = {
  getDependencies: async (service: string, minutes: number = 15): Promise<RuntimeDependencyResponse> => {
    const response = await api.get<RuntimeDependencyResponse>('/observability-runtime/dependencies', {
      params: { service, minutes },
    });
    return response.data;
  },

  getAnomalies: async (service: string, minutes: number = 15): Promise<RuntimeAnomalyResponse> => {
    const response = await api.get<RuntimeAnomalyResponse>('/observability-runtime/anomalies', {
      params: { service, minutes },
    });
    return response.data;
  },

  getTopology: async (service: string, minutes: number = 15): Promise<RuntimeTopologySnapshot> => {
    const response = await api.get<RuntimeTopologySnapshot>('/observability-runtime/topology', {
      params: { service, minutes },
    });
    return response.data;
  },
};

export const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/logs/ws/simulate`;
