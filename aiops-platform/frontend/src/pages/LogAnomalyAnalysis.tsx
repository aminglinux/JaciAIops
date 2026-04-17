import { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Typography, Button, Alert, Space, message, Statistic, Row, Col, List, Tag, Modal, InputNumber, Collapse, Timeline } from 'antd';
import { ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { alertsApi, logsApi } from '../services/api';
import type {
  AlertFinalDecision,
  AnalysisWarning,
  LogAnomalyAnalyzeResult,
  LogStats,
  LogAnalyzeTaskStatus,
  LogAnalyzeProcessEvent,
  LogAnalyzeHistoryItem,
} from '../types';

const { Text } = Typography;

const toRecord = (value: unknown): Record<string, unknown> => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
};

const LogAnomalyAnalysis = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [analyzingAnomaly, setAnalyzingAnomaly] = useState(false);
  const [paramsModalOpen, setParamsModalOpen] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<LogAnomalyAnalyzeResult | null>(null);
  const [processModalOpen, setProcessModalOpen] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [currentTaskStatus, setCurrentTaskStatus] = useState<LogAnalyzeTaskStatus | null>(null);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [analysisHistory, setAnalysisHistory] = useState<LogAnalyzeHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyReplayEvents, setHistoryReplayEvents] = useState<LogAnalyzeProcessEvent[]>([]);
  const [historyReplayTitle, setHistoryReplayTitle] = useState<string>('');
  const [analyzeParams, setAnalyzeParams] = useState({
    lookbackMinutes: 60,
    maxLogs: 300,
  });
  const streamAbortRef = useRef<AbortController | null>(null);
  const activeStreamTaskIdRef = useRef<string | null>(null);
  const processModalBodyRef = useRef<HTMLDivElement | null>(null);
  const historyModalBodyRef = useRef<HTMLDivElement | null>(null);

  const processEvents = useMemo(
    () => (Array.isArray(currentTaskStatus?.events) ? currentTaskStatus?.events : []),
    [currentTaskStatus?.events]
  );

  const fetchData = async () => {
    setLoadingStats(true);
    try {
      const statsData = await logsApi.getStats({ uploaded_only: true });
      setStats(statsData);
      message.success('日志统计已刷新');
    } catch {
      message.error('刷新数据失败');
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, []);

  const startTaskStream = async (taskId: string) => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = new AbortController();
    activeStreamTaskIdRef.current = taskId;
    setCurrentTaskStatus({
      task_id: taskId,
      status: 'queued',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      params: {
        lookback_minutes: analyzeParams.lookbackMinutes,
        max_logs: analyzeParams.maxLogs,
      },
      events: [],
      result: null,
      error: null,
      event_id: null,
    });
    try {
      await alertsApi.streamAnalyzeFromLogsTask(taskId, {
        onMeta: (payload) => {
          if (activeStreamTaskIdRef.current !== taskId) return;
          setCurrentTaskStatus((prev) => ({
            task_id: taskId,
            status: String(payload.status || prev?.status || 'running'),
            created_at: String(payload.created_at || prev?.created_at || ''),
            updated_at: new Date().toISOString(),
            params: prev?.params,
            events: prev?.events || [],
            result: prev?.result || null,
            error: prev?.error || null,
            event_id: prev?.event_id || null,
          }));
        },
        onEvent: (payload) => {
          if (activeStreamTaskIdRef.current !== taskId) return;
          const event = toRecord(payload.event);
          const mappedEvent: LogAnalyzeProcessEvent = {
            timestamp: String(event.timestamp || new Date().toISOString()),
            node: String(event.node || 'unknown'),
            status: String(event.status || 'info'),
            description: String(event.description || ''),
            detail: toRecord(event.detail),
          };
          setCurrentTaskStatus((prev) => ({
            task_id: taskId,
            status: String(payload.status || prev?.status || 'running'),
            created_at: prev?.created_at || '',
            updated_at: new Date().toISOString(),
            params: prev?.params,
            events: [...(prev?.events || []), mappedEvent],
            result: prev?.result || null,
            error: prev?.error || null,
            event_id: prev?.event_id || null,
          }));
        },
        onDone: (payload) => {
          if (activeStreamTaskIdRef.current !== taskId) return;
          const status = String(payload.status || 'completed');
          const result = payload.result ? (payload.result as LogAnomalyAnalyzeResult) : null;
          setCurrentTaskStatus((prev) => ({
            task_id: taskId,
            status,
            created_at: prev?.created_at || '',
            updated_at: new Date().toISOString(),
            params: prev?.params,
            events: prev?.events || [],
            result,
            error: payload.error ? String(payload.error) : null,
            event_id: typeof payload.event_id === 'number' ? payload.event_id : null,
          }));
          if (status === 'completed' && result) {
            setAnalyzeResult(result);
            message.success('异常日志分析完成');
          } else if (status === 'failed') {
            message.error(payload.error ? String(payload.error) : '异常日志分析失败');
          }
          setAnalyzingAnomaly(false);
          activeStreamTaskIdRef.current = null;
        },
        onError: (payload) => {
          if (activeStreamTaskIdRef.current !== taskId) return;
          message.error(payload.message ? String(payload.message) : '分析流连接失败');
          setAnalyzingAnomaly(false);
          activeStreamTaskIdRef.current = null;
        },
      }, streamAbortRef.current.signal);
    } catch {
      if (!streamAbortRef.current?.signal.aborted) {
        message.error('实时分析流中断');
      }
      setAnalyzingAnomaly(false);
      if (activeStreamTaskIdRef.current === taskId) {
        activeStreamTaskIdRef.current = null;
      }
    }
  };

  useEffect(() => () => {
    streamAbortRef.current?.abort();
    activeStreamTaskIdRef.current = null;
  }, []);

  const fetchAnalyzeHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await alertsApi.getAnalyzeFromLogsHistory(30);
      setAnalysisHistory(response.history || []);
    } catch {
      message.error('读取分析历史失败');
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleAnalyzeAnomalyLogs = async () => {
    if ((stats?.total_logs || 0) <= 0) {
      message.info('请先上传日志');
      return;
    }
    if ((stats?.anomaly_count || 0) <= 0) {
      message.info('当前没有异常日志，无需触发 RCA');
      return;
    }
    streamAbortRef.current?.abort();
    activeStreamTaskIdRef.current = null;
    setCurrentTaskId(null);
    setCurrentTaskStatus({
      task_id: '',
      status: 'queued',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      params: {
        lookback_minutes: analyzeParams.lookbackMinutes,
        max_logs: analyzeParams.maxLogs,
      },
      events: [],
      result: null,
      error: null,
      event_id: null,
    });
    setProcessModalOpen(true);
    setAnalyzingAnomaly(true);
    try {
      const start = await alertsApi.startAnalyzeFromLogs({
        lookback_minutes: analyzeParams.lookbackMinutes,
        max_logs: analyzeParams.maxLogs,
      });
      setAnalyzeResult(null);
      setCurrentTaskId(start.task_id);
      message.success(start.message || '已触发异常日志 RCA 工作流');
      void startTaskStream(start.task_id);
    } catch (error) {
      const detail = typeof error === 'object' && error !== null
        ? ((error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
        : '';
      if (detail) {
        message.info(detail);
      } else {
        message.error('触发异常日志分析失败');
      }
      setAnalyzingAnomaly(false);
    }
  };

  const decision = (analyzeResult?.final_decision || null) as AlertFinalDecision | null;
  const analyzeWarnings = (analyzeResult?.warnings || []) as AnalysisWarning[];
  const analyzeWarningText = analyzeWarnings
    .map((item) => (item.impact ? `${item.message}（${item.impact}）` : item.message))
    .filter(Boolean)
    .join('；');
  const rcaPayload = toRecord(analyzeResult?.rca);
  const rcaStages = toRecord(rcaPayload.stages);
  const skillMatchingStage = toRecord(rcaStages.skill_matching);
  const dynamicExecutionStage = toRecord(rcaStages.dynamic_execution);
  const alertPrefetchStage = toRecord(rcaStages.alert_prefetch);
  const metricsEvidence = toRecord(alertPrefetchStage.metrics_evidence);
  const logsEvidence = toRecord(alertPrefetchStage.log_evidence_prefetch);
  const traceEvidence = toRecord(alertPrefetchStage.trace_evidence);
  const durationSeconds = typeof rcaPayload.duration_seconds === 'number' ? rcaPayload.duration_seconds : null;
  const matchedSkills = Array.isArray(skillMatchingStage.matched_skills)
    ? skillMatchingStage.matched_skills.filter((item): item is string => typeof item === 'string')
    : [];
  const executionHistory = Array.isArray(dynamicExecutionStage.execution_history)
    ? dynamicExecutionStage.execution_history.map((item) => toRecord(item))
    : [];
  const recentTools = executionHistory
    .map((item) => item.tool)
    .filter((item): item is string => typeof item === 'string')
    .slice(0, 8);

  const handleOpenHistoryModal = async () => {
    setHistoryModalOpen(true);
    setHistoryReplayEvents([]);
    setHistoryReplayTitle('');
    await fetchAnalyzeHistory();
  };

  const handleReplayHistory = async (item: LogAnalyzeHistoryItem) => {
    try {
      const detail = await alertsApi.getEvent(item.event_id);
      const rca = toRecord(detail.rca);
      const processEventsRaw = Array.isArray(rca.process_events) ? rca.process_events : [];
      const processEventsMapped = processEventsRaw.map((evt) => toRecord(evt)).map((evt) => ({
        timestamp: String(evt.timestamp || ''),
        node: String(evt.node || 'unknown'),
        status: String(evt.status || 'info'),
        description: String(evt.description || ''),
        detail: toRecord(evt.detail),
      }));
      setHistoryReplayEvents(processEventsMapped);
      setHistoryReplayTitle(`会话 #${item.event_id} - ${item.alert_name}`);
    } catch {
      message.error('读取历史会话详情失败');
    }
  };

  const scrollProcessModalToTop = () => {
    processModalBodyRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollHistoryModalToTop = () => {
    historyModalBodyRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="异常日志分析"
        description="本页面用于触发异常日志 RCA、配置参数并回看分析历史。"
      />

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="上传日志总数" value={stats?.total_logs || 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="异常数量" value={stats?.anomaly_count || 0} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="异常率" value={stats ? (stats.anomaly_rate * 100).toFixed(2) : 0} suffix="%" />
          </Card>
        </Col>
      </Row>

      <Card>
        <Space direction="vertical" size={12}>
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchData()} loading={loadingStats}>
              刷新数据
            </Button>
            <Button type="primary" onClick={() => void handleAnalyzeAnomalyLogs()} loading={analyzingAnomaly}>
              分析异常日志（RCA）
            </Button>
            <Button onClick={() => setParamsModalOpen(true)}>参数配置</Button>
            <Button icon={<HistoryOutlined />} onClick={() => void handleOpenHistoryModal()}>分析历史</Button>
          </Space>
          <Text type="secondary">
            参数将用于本次分析任务；分析过程与结果会记录到历史会话中。
          </Text>
        </Space>
      </Card>

      {analyzeResult && (
        <Card
          title="异常日志 RCA 结果"
          extra={(
            <Button size="small" type="link" onClick={() => navigate('/alerts')}>
              前往告警中心
            </Button>
          )}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Text type="secondary">
              本次分析异常日志：{analyzeResult.anomaly_logs} 条，回看窗口：{analyzeResult.lookback_minutes} 分钟
            </Text>
            <Text>分析任务模式：{analyzeResult.mode}</Text>
            <Text>事件 ID：{analyzeResult.event_id ?? '-'}</Text>
            {decision?.root_cause_summary ? (
              <Alert type="info" showIcon message="初步根因" description={decision.root_cause_summary} />
            ) : (
              <Alert type="warning" showIcon message="分析已完成，未返回根因摘要" />
            )}
            {decision?.recommendation && (
              <Alert type="success" showIcon message="建议动作" description={decision.recommendation} />
            )}
            {analyzeWarnings.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message="分析已降级（部分依赖不可用）"
                description={analyzeWarningText}
              />
            )}
            <Collapse
              size="small"
              items={[
                {
                  key: 'rca-process',
                  label: '查看分析过程明细',
                  children: (
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <Text>总耗时：{durationSeconds !== null ? `${durationSeconds.toFixed(2)} 秒` : '-'}</Text>
                      <Text>动态执行状态：{String(dynamicExecutionStage.status || '-')}</Text>
                      <Text>执行迭代次数：{executionHistory.length}</Text>
                      <Text>预采集状态：metrics={String(metricsEvidence.status || '-')} / logs={String(logsEvidence.status || '-')} / trace={String(traceEvidence.status || '-')}</Text>
                      <Text>命中技能：</Text>
                      {matchedSkills.length > 0 ? (
                        <Space size={[4, 6]} wrap>
                          {matchedSkills.map((skill) => (
                            <Tag key={skill} color="blue">{skill}</Tag>
                          ))}
                        </Space>
                      ) : (
                        <Text type="secondary">无</Text>
                      )}
                      <Text>执行过的工具：</Text>
                      {recentTools.length > 0 ? (
                        <Space size={[4, 6]} wrap>
                          {recentTools.map((tool, index) => (
                            <Tag key={`${tool}-${index}`}>{tool}</Tag>
                          ))}
                        </Space>
                      ) : (
                        <Text type="secondary">无</Text>
                      )}
                    </Space>
                  ),
                },
              ]}
            />
          </Space>
        </Card>
      )}

      <Modal
        title="异常日志分析过程"
        open={processModalOpen}
        onCancel={() => setProcessModalOpen(false)}
        footer={[
          <Button key="top" onClick={scrollProcessModalToTop}>
            回到顶部
          </Button>,
          <Button key="close" onClick={() => setProcessModalOpen(false)}>
            关闭
          </Button>,
        ]}
        width={980}
      >
        <div ref={processModalBodyRef} style={{ maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Alert
              type={currentTaskStatus?.status === 'failed' ? 'error' : currentTaskStatus?.status === 'completed' ? 'success' : 'info'}
              showIcon
              message={`任务状态：${currentTaskStatus?.status || 'queued'}`}
              description={currentTaskStatus?.error || `任务ID：${currentTaskId || '-'}`}
            />
            <Timeline
              items={processEvents.map((event, index) => ({
                color: event.status === 'failed' ? 'red' : event.status === 'completed' ? 'green' : event.status === 'warning' ? 'orange' : 'blue',
                children: (
                  <Space direction="vertical" size={2}>
                    <Text strong>{event.description || event.node}</Text>
                    <Text type="secondary">
                      {event.timestamp ? new Date(event.timestamp).toLocaleString() : '-'} | 节点: {event.node} | 状态: {event.status}
                    </Text>
                    {event.detail && Object.keys(event.detail).length > 0 && (
                      <pre style={{ margin: 0, background: '#fafafa', padding: 8, borderRadius: 6, maxHeight: 180, overflow: 'auto', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word', maxWidth: '100%' }}>
                        {JSON.stringify(event.detail, null, 2)}
                      </pre>
                    )}
                  </Space>
                ),
                key: `${event.timestamp}-${event.node}-${index}`,
              }))}
            />
            {processEvents.length === 0 && (
              <Text type="secondary">任务已创建，等待进度事件...</Text>
            )}
          </Space>
        </div>
      </Modal>

      <Modal
        title="异常日志分析历史会话"
        open={historyModalOpen}
        onCancel={() => setHistoryModalOpen(false)}
        footer={[
          <Button key="top" onClick={scrollHistoryModalToTop}>
            回到顶部
          </Button>,
          <Button key="close" onClick={() => setHistoryModalOpen(false)}>
            关闭
          </Button>,
        ]}
        width={1080}
      >
        <div ref={historyModalBodyRef} style={{ maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}>
          <Row gutter={16}>
            <Col span={10}>
              <List
                loading={loadingHistory}
                size="small"
                bordered
                dataSource={analysisHistory}
                locale={{ emptyText: '暂无历史分析会话' }}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button key={`replay-${item.event_id}`} size="small" type="link" onClick={() => void handleReplayHistory(item)}>
                        回看过程
                      </Button>,
                    ]}
                  >
                    <Space direction="vertical" size={0} style={{ width: '100%' }}>
                      <Text strong>{item.alert_name}</Text>
                      <Text type="secondary">会话ID: {item.event_id} | {item.created_at ? new Date(item.created_at).toLocaleString() : '-'}</Text>
                      <Space size={[4, 4]} wrap>
                        <Tag>{item.severity}</Tag>
                        <Tag color="blue">{item.status}</Tag>
                        <Tag color="purple">过程事件 {item.process_events_count}</Tag>
                      </Space>
                    </Space>
                  </List.Item>
                )}
              />
            </Col>
            <Col span={14}>
              <Card
                size="small"
                title={historyReplayTitle || '请选择左侧会话进行回看'}
                extra={(
                  <Button size="small" icon={<ReloadOutlined />} onClick={() => void fetchAnalyzeHistory()}>
                    刷新
                  </Button>
                )}
              >
                {historyReplayEvents.length > 0 ? (
                  <Timeline
                    items={historyReplayEvents.map((event, index) => ({
                      color: event.status === 'failed' ? 'red' : event.status === 'completed' ? 'green' : event.status === 'warning' ? 'orange' : 'blue',
                      children: (
                        <Space direction="vertical" size={2}>
                          <Text strong>{event.description || event.node}</Text>
                          <Text type="secondary">
                            {event.timestamp ? new Date(event.timestamp).toLocaleString() : '-'} | {event.node}
                          </Text>
                          {event.detail && Object.keys(event.detail).length > 0 && (
                            <pre style={{ margin: 0, background: '#fafafa', padding: 8, borderRadius: 6, maxHeight: 160, overflow: 'auto', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word', maxWidth: '100%' }}>
                              {JSON.stringify(event.detail, null, 2)}
                            </pre>
                          )}
                        </Space>
                      ),
                      key: `${event.timestamp}-${event.node}-${index}`,
                    }))}
                  />
                ) : (
                  <Text type="secondary">暂无过程明细</Text>
                )}
              </Card>
            </Col>
          </Row>
        </div>
      </Modal>

      <Modal
        title="参数配置"
        open={paramsModalOpen}
        onCancel={() => setParamsModalOpen(false)}
        onOk={() => {
          setAnalyzeParams((prev) => ({
            lookbackMinutes: Math.min(1440, Math.max(1, prev.lookbackMinutes)),
            maxLogs: Math.min(500, Math.max(20, prev.maxLogs)),
          }));
          setParamsModalOpen(false);
          message.success('分析参数已更新');
        }}
        okText="保存参数"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <Text strong>回看分钟</Text>
            <br />
            <InputNumber
              min={1}
              max={1440}
              style={{ width: '100%', marginTop: 8 }}
              value={analyzeParams.lookbackMinutes}
              onChange={(value) => {
                if (typeof value === 'number') {
                  setAnalyzeParams((prev) => ({ ...prev, lookbackMinutes: value }));
                }
              }}
            />
            <div style={{ marginTop: 4 }}>
              <Text type="secondary">范围 1~1440 分钟，默认 60 分钟</Text>
            </div>
          </div>
          <div>
            <Text strong>最大日志数</Text>
            <br />
            <InputNumber
              min={20}
              max={500}
              style={{ width: '100%', marginTop: 8 }}
              value={analyzeParams.maxLogs}
              onChange={(value) => {
                if (typeof value === 'number') {
                  setAnalyzeParams((prev) => ({ ...prev, maxLogs: value }));
                }
              }}
            />
            <div style={{ marginTop: 4 }}>
              <Text type="secondary">范围 20~500 条，默认 300 条</Text>
            </div>
          </div>
          <Alert
            type="info"
            showIcon
            message={`当前参数：回看 ${analyzeParams.lookbackMinutes} 分钟，最多 ${analyzeParams.maxLogs} 条日志`}
          />
        </Space>
      </Modal>
    </Space>
  );
};

export default LogAnomalyAnalysis;
