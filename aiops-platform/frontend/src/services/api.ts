import axios from 'axios';
import { message } from 'antd';
import type {
  Log,
  LogStats,
  AgentTask,
  DiagnoseRequest,
  DiagnoseResponse,
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

export const knowledgeApi = {
  queryKG: async (service?: string, query?: string): Promise<unknown> => {
    const response = await api.get('/knowledge/query', { params: { service, query } });
    return response.data;
  },

  queryRAG: async (query: string, topK: number = 5): Promise<unknown> => {
    const response = await api.post('/knowledge/rag/query', { query, top_k: topK });
    return response.data;
  },

  chat: async (question: string, analyzeProblem: boolean = false): Promise<unknown> => {
    const response = await api.get('/knowledge/qa/chat', { params: { question, analyze_problem: analyzeProblem } });
    return response.data;
  },

  getTopology: async (service?: string, depth: number = 2): Promise<unknown> => {
    const response = await api.get('/knowledge/topology', { params: { service, depth } });
    return response.data;
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

export const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/logs/ws/simulate`;
