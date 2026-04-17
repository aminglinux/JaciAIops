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
  id: string | number;
  timestamp: string;
  level: string;
  content: string;
  source: string;
  source_type?: string;
  service?: string | null;
  labels?: Record<string, string> | null;
  is_anomaly: boolean;
  anomaly_score: number | null;
  user_feedback: boolean | null;
  raw?: Record<string, unknown> | null;
}

export interface LogStats {
  total_logs: number;
  anomaly_count: number;
  anomaly_rate: number;
  level_distribution: Record<string, number>;
  top_patterns: Array<{ content: string; score: number }>;
}

export interface LogUploadResult {
  message: string;
  filename: string;
  batch_id: string;
  logs_created: number;
  anomaly_count: number;
  upload_time: string;
}

export interface UploadBatchSummary {
  batch_id: string;
  filename: string;
  logs_created: number;
  anomaly_count: number;
  first_log_time?: string | null;
  last_log_time?: string | null;
}

export interface DeleteUploadBatchResult {
  batch_id: string;
  deleted_logs: number;
  message: string;
}

export interface ClearUploadedLogsResult {
  deleted_logs: number;
  deleted_batches: number;
  message: string;
}

export interface LogSourceConfig {
  elasticsearchEnabled: boolean;
  elasticsearchUrl: string;
  elasticsearchIndexPattern: string;
  elasticsearchAuthType: 'none' | 'basic' | 'api_key' | string;
  elasticsearchUsername?: string;
  elasticsearchPasswordMasked?: string;
  elasticsearchApiKeyMasked?: string;
  elasticsearchTlsVerify: boolean;
  lokiEnabled: boolean;
  lokiUrl: string;
  updatedBy?: string | null;
  updatedAt?: string | null;
}

export interface LogSourceConfigPayload {
  elasticsearch_enabled: boolean;
  elasticsearch_url: string;
  elasticsearch_index_pattern: string;
  elasticsearch_auth_type: string;
  elasticsearch_username?: string;
  elasticsearch_password?: string;
  elasticsearch_api_key?: string;
  elasticsearch_tls_verify: boolean;
  loki_enabled: boolean;
  loki_url: string;
}

export interface LogSourceTestResult {
  success: boolean;
  message: string;
  details?: {
    endpoint?: string | null;
    clusterName?: string | null;
    clusterUuid?: string | null;
    version?: string | null;
    tagline?: string | null;
    authenticatedAs?: string | null;
    labelsCount?: number | null;
    status?: string | null;
    sampleLabels?: string | null;
  };
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

export interface AlertAnalyzeRequest {
  alert_name: string;
  severity?: string;
  service?: string;
  instance?: string;
  metric_name?: string;
  metric_value?: number;
  threshold?: number;
  starts_at?: string;
  ends_at?: string;
  description?: string;
  labels?: Record<string, unknown>;
  annotations?: Record<string, unknown>;
  source?: string;
  lookback_minutes?: number;
}

export interface NormalizedAlert {
  alert_name: string;
  severity: string;
  service?: string | null;
  instance?: string | null;
  metric_name?: string | null;
  metric_value?: number | null;
  threshold?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  description: string;
  labels: Record<string, unknown>;
  annotations: Record<string, unknown>;
  source: string;
  lookback_minutes: number;
}

export interface AlertAnalysisResult {
  event_id?: number;
  alert: NormalizedAlert;
  query: string;
  rca: Record<string, unknown>;
  final_decision?: Decision | null;
  warnings?: AnalysisWarning[];
  mode: string;
}

export interface LogAnomalyAnalyzeRequest {
  lookback_minutes?: number;
  max_logs?: number;
  alert_name?: string;
  severity?: string;
  service?: string;
}

export interface LogAnomalyAnalyzeResult extends AlertAnalysisResult {
  anomaly_logs: number;
  lookback_minutes: number;
}

export interface AnalysisWarning {
  code?: string;
  message: string;
  impact?: string;
}

export interface AlertEventSummary {
  id: number;
  source: string;
  alert_name: string;
  severity: string;
  service?: string | null;
  instance?: string | null;
  status: string;
  fingerprint?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
  description: string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertEventDetail extends AlertEventSummary {
  labels: Record<string, unknown>;
  annotations: Record<string, unknown>;
  alert: Record<string, unknown>;
  query: string;
  rca: Record<string, unknown>;
  final_decision?: AlertFinalDecision | null;
}

export interface AlertLogEvidence {
  status?: 'matched' | 'weak_matched' | 'not_found' | string;
  summary?: string;
  top_patterns?: string[];
  sample_logs?: string[];
  suspected_component?: string;
  confidence?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  match_score?: number;
  matched_fields?: string[];
  source_type?: string;
}

export interface AlertFinalDecision {
  is_final?: boolean;
  problem_type?: string;
  root_cause?: string;
  root_cause_summary?: string;
  impact?: string;
  recommendation?: string;
  action_plan?: string;
  risk_level?: string;
  confidence?: string;
  decision?: string;
  reasoning?: string;
  analysis_summary?: string;
  evidence_chain?: string[];
  propagation_path?: string[];
  affected_services?: string[];
  log_evidence?: AlertLogEvidence;
  error?: string;
  [key: string]: unknown;
}

export interface AlertWebhookSecurityConfig {
  ipWhitelist: string[];
  ipWhitelistText: string;
  trustProxyHeaders: boolean;
  updatedBy?: string | null;
  updatedAt?: string | null;
}

export interface AlertWebhookSecurityConfigPayload {
  ip_whitelist: string;
  trust_proxy_headers: boolean;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  analyze_problem: boolean;
  last_message: string;
  created_at?: string;
  updated_at?: string;
}

export interface ChatHistoryMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  mode?: string | null;
  intent?: {
    intent: string;
    entities: Record<string, string>;
    confidence: string;
  } | null;
  knowledge?: {
    knowledge_report?: string;
  } | null;
  runtime_topology?: RuntimeTopologySnapshot | null;
  created_at?: string;
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

export interface RuntimeServiceDependency {
  source_service: string;
  target_service: string;
  dependency_type: string;
  avg_latency_ms: number;
  error_rate: number;
  call_count: number;
  last_seen?: string | null;
  source: string;
  details?: Record<string, unknown>;
}

export interface RuntimeTraceAnomaly {
  service: string;
  trace_id: string;
  span_name: string;
  duration_ms: number;
  suspected_dependency?: string | null;
  anomaly_type: string;
  details?: Record<string, unknown>;
}

export interface RuntimeTopologySnapshot {
  service: string;
  window_minutes: number;
  upstream: RuntimeServiceDependency[];
  downstream: RuntimeServiceDependency[];
  anomalies: RuntimeTraceAnomaly[];
  source: string;
}

export interface RuntimeDependencyResponse {
  service: string;
  minutes: number;
  dependencies: RuntimeServiceDependency[];
}

export interface RuntimeAnomalyResponse {
  service: string;
  minutes: number;
  anomalies: RuntimeTraceAnomaly[];
}

export interface RuntimeGraphConfig {
  traceBackend: string;
  jaegerQueryUrl: string;
  tempoQueryUrl: string;
  traceQueryTimeout: number;
  traceDefaultLookbackMinutes: number;
  runtimeGraphEnabled: boolean;
  serviceList: string[];
  updatedBy?: string | null;
  updatedAt?: string | null;
}

export interface RuntimeGraphConfigPayload {
  trace_backend: string;
  jaeger_query_url: string;
  tempo_query_url: string;
  trace_query_timeout: number;
  trace_default_lookback_minutes: number;
  runtime_graph_enabled: boolean;
  service_list: string[];
}

export interface ManualGraphRelationPayload {
  target_type: string;
  target_name: string;
  relation_type: string;
  target_properties?: Record<string, unknown>;
}

export interface ManualGraphEntryPayload {
  source_type: string;
  source_name: string;
  source_properties?: Record<string, unknown>;
  relation?: ManualGraphRelationPayload | null;
}
