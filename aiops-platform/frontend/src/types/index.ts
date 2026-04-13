export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface UserInfo {
  userId: number;
  username: string;
  email: string;
  avatar?: string;
  roles: string[];
  permissions: string[];
  scope: string[];
  isAdmin: boolean;
}

export interface LoginParams {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user: UserInfo;
}

export interface RegisterParams {
  username: string;
  email: string;
  password: string;
  isAdmin?: boolean;
}

export interface Log {
  id: number;
  timestamp: string;
  level: string;
  content: string;
  source: string;
  is_anomaly: boolean;
  anomaly_score: number | null;
  user_feedback: boolean | null;
}

export interface LogStats {
  total_logs: number;
  anomaly_count: number;
  anomaly_rate: number;
  level_distribution: Record<string, number>;
  top_patterns: Array<{ content: string; score: number }>;
}

export interface AgentTask {
  task_id: string;
  user_input?: string;
  status: string;
  intent_data: IntentData | null;
  analysis_report: AnalysisReport | null;
  knowledge_context: KnowledgeContext | null;
  decision: Decision | null;
  action_result: ActionResult | null;
  created_at: string;
  updated_at: string;
  warning_cleared?: boolean;
  ansible_playbook?: AnsiblePlaybook | null;
  server_status_check?: ServerStatusCheck | null;
  mode?: string;
  iterations?: number;
  diagnosis_plan?: DiagnosisPlan | null;
  execution_outputs?: ExecutionOutput[];
  saved_outputs?: SavedOutput[];
  raw_response?: string;
}

export interface DiagnosisPlan {
  plan_name: string;
  check_type: string;
  commands: string[];
  reasoning: string;
  expected_findings?: string[];
  created_at?: string;
}

export interface ExecutionOutput {
  command: string;
  output: string;
  success: boolean;
  target_host: string;
}

export interface SavedOutput {
  success: boolean;
  target_host: string;
  command?: string;
  saved_to: string;
}

export interface AnsiblePlaybook {
  target_host: string;
  playbook: Record<string, unknown>;
  symptoms: string[];
  metrics: string[];
}

export interface ServerStatusCheck {
  success: boolean;
  warning_cleared: boolean;
  memory_usage?: number;
  cpu_usage?: number;
  disk_usage?: number;
  shm_usage?: number;
  anomalies: string[];
  raw_output?: string;
  error?: string;
}

export interface IntentData {
  intent: string;
  entities: {
    service: string;
    ip: string | null;
    symptom: string;
    time_range: string;
  };
  confidence: string;
  normalized_query: string;
  clarification_needed: boolean;
}

export interface AnalysisReport {
  service: string;
  analysis_report: string;
  metrics_summary: Record<string, string | number>;
  log_patterns: string[];
  trace_anomalies: Array<{ span: string; duration: string; anomaly: string }>;
}

export interface KnowledgeContext {
  service: string;
  symptom: string;
  knowledge_report: string;
  topology_info: Record<string, unknown>;
  similar_incidents: Record<string, unknown>;
  sop_docs: Record<string, unknown>;
}

export interface Decision {
  root_cause_summary?: string;
  decision?: string;
  action_plan?: string;
  target_agent?: string | null;
  risk_level: string;
  reasoning?: string;
  is_final?: boolean;
  problem_type?: string;
  root_cause?: string;
  impact?: string;
  recommendation?: string;
}

export interface ActionResult {
  tool_name: string;
  template_name: string | null;
  parameters: Record<string, unknown>;
  risk_assessment: string;
  requires_approval: boolean;
  execution_note: string;
}

export interface DiagnoseRequest {
  user_input: string;
  session_id?: string;
}

export interface DiagnoseResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface LLMProvider {
  id: number;
  name: string;
  providerCode: string;
  providerType: string;
  baseUrl: string;
  apiKeyMasked: string;
  enabled: boolean;
  isBuiltin: boolean;
  extraConfig?: Record<string, unknown>;
  createdAt?: string;
  updatedAt?: string;
}

export interface LLMModel {
  id: number;
  providerId: number;
  providerName: string;
  modelId: string;
  displayName: string;
  modelType: string;
  supportsFunctionCalling: boolean;
  supportsStreaming: boolean;
  supportsJsonMode: boolean;
  contextWindow?: number | null;
  maxOutputTokens?: number | null;
  enabled: boolean;
  isDefaultCandidate: boolean;
  meta?: Record<string, unknown>;
  createdAt?: string;
  updatedAt?: string;
}

export interface LLMBinding {
  sceneKey: string;
  displayName: string;
  temperature?: number | null;
  maxTokens?: number | null;
  topP?: number | null;
  enabled: boolean;
  modelId?: number | null;
  modelName: string;
  providerId?: number | null;
  providerName: string;
  supportsFunctionCalling: boolean;
  source: string;
}

export interface LLMScene {
  scene_key: string;
  display_name: string;
  temperature: number;
  supports_function_calling: boolean;
}

export interface ProviderFormValues {
  name: string;
  provider_code: string;
  provider_type: string;
  base_url: string;
  api_key?: string;
  enabled: boolean;
}

export interface ModelFormValues {
  provider_id: number;
  model_id: string;
  display_name: string;
  model_type: string;
  supports_function_calling: boolean;
  supports_streaming: boolean;
  supports_json_mode: boolean;
  context_window?: number;
  max_output_tokens?: number;
  enabled: boolean;
  is_default_candidate: boolean;
}

export interface BindingFormValues {
  model_id: number;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  enabled: boolean;
}

export interface DiscoveredModel {
  modelId: string;
  displayName: string;
  alreadyImported: boolean;
  enabled: boolean;
  supportsFunctionCalling: boolean;
  supportsStreaming: boolean;
  supportsJsonMode: boolean;
  modelType: string;
}

export interface LLMRuntimeBinding {
  sceneKey: string;
  displayName: string;
  providerName: string;
  model: string;
  source: string;
  temperature: number;
  supportsFunctionCalling: boolean;
}

export interface LLMRuntimeConfig {
  bindings: LLMRuntimeBinding[];
  fallback: {
    baseUrl: string;
    model: string;
  };
}
