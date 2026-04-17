import { useEffect, useState } from 'react';
import { Card, Typography, Upload, Button, Alert, Space, message, Statistic, Row, Col, Progress, List, Tag, Modal, InputNumber, Popconfirm, Collapse } from 'antd';
import { InboxOutlined, UploadOutlined, FileTextOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useNavigate } from 'react-router-dom';

import { alertsApi, logsApi } from '../services/api';
import type { AlertFinalDecision, AnalysisWarning, LogAnomalyAnalyzeResult, LogStats, LogUploadResult, UploadBatchSummary } from '../types';

const { Title, Paragraph, Text } = Typography;
const HISTORY_STORAGE_KEY = 'log_upload_history_v1';
const MAX_HISTORY_COUNT = 12;

type UploadHistoryRecord = LogUploadResult & {
  id: string;
};

const toRecord = (value: unknown): Record<string, unknown> => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
};

const LogUpload = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [analyzingAnomaly, setAnalyzingAnomaly] = useState(false);
  const [paramsModalOpen, setParamsModalOpen] = useState(false);
  const [lastUpload, setLastUpload] = useState<UploadHistoryRecord | null>(null);
  const [uploadHistory, setUploadHistory] = useState<UploadHistoryRecord[]>([]);
  const [analyzeResult, setAnalyzeResult] = useState<LogAnomalyAnalyzeResult | null>(null);
  const [analyzeParams, setAnalyzeParams] = useState({
    lookbackMinutes: 60,
    maxLogs: 300,
  });
  const [uploadBatches, setUploadBatches] = useState<UploadBatchSummary[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [deletingBatchId, setDeletingBatchId] = useState<string | null>(null);
  const [clearingUploadedLogs, setClearingUploadedLogs] = useState(false);

  const persistUploadHistory = (records: UploadHistoryRecord[]) => {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(records));
  };

  const fetchData = async () => {
    setLoadingStats(true);
    try {
      const statsData = await logsApi.getStats({ uploaded_only: true });
      setStats(statsData);
      message.success('日志统计已刷新');
    } catch (error) {
      message.error('刷新数据失败');
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchUploadBatches = async () => {
    setLoadingBatches(true);
    try {
      const response = await logsApi.listUploadBatches(30);
      setUploadBatches(response.batches || []);
    } catch {
      message.error('读取上传批次失败');
    } finally {
      setLoadingBatches(false);
    }
  };

  useEffect(() => {
    void fetchData();
    void fetchUploadBatches();
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as UploadHistoryRecord[];
        setUploadHistory(parsed);
        setLastUpload(parsed[0] || null);
      } catch {
        localStorage.removeItem(HISTORY_STORAGE_KEY);
      }
    }
  }, []);

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.log,.txt',
    showUploadList: false,
    multiple: false,
    beforeUpload: async (file) => {
      setUploading(true);
      try {
        const result = await logsApi.uploadFile(file);
        const record: UploadHistoryRecord = {
          ...result,
          id: `${result.filename}-${result.upload_time}-${Date.now()}`,
        };
        const nextHistory = [record, ...uploadHistory].slice(0, MAX_HISTORY_COUNT);
        setLastUpload(record);
        setUploadHistory(nextHistory);
        persistUploadHistory(nextHistory);
        message.success(result.message || `上传成功: ${result.filename}`);
        await fetchData();
        await fetchUploadBatches();
      } catch (error) {
        message.error('上传失败，请稍后重试');
      } finally {
        setUploading(false);
      }
      return false;
    },
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
    setAnalyzingAnomaly(true);
    try {
      const result = await alertsApi.analyzeFromLogs({
        lookback_minutes: analyzeParams.lookbackMinutes,
        max_logs: analyzeParams.maxLogs,
      });
      setAnalyzeResult(result);
      message.success('已触发异常日志 RCA 工作流');
    } catch (error) {
      message.error('触发异常日志分析失败');
    } finally {
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

  const handleDeleteBatch = async (batchId: string) => {
    setDeletingBatchId(batchId);
    try {
      const result = await logsApi.deleteUploadBatch(batchId);
      message.success(result.message);
      await fetchData();
      await fetchUploadBatches();
    } catch {
      message.error('删除上传批次失败');
    } finally {
      setDeletingBatchId(null);
    }
  };

  const handleClearUploadedLogs = async () => {
    setClearingUploadedLogs(true);
    try {
      const result = await logsApi.clearUploadedLogs();
      message.success(result.message);
      await fetchData();
      await fetchUploadBatches();
    } catch {
      message.error('清空上传日志失败');
    } finally {
      setClearingUploadedLogs(false);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="日志上传"
        description="支持上传 `.log` 或 `.txt` 文件；上传完成后可直接触发“异常日志 RCA 工作流”，并在告警中心查看分析结果。"
      />

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="今日日志总数" value={stats?.total_logs || 0} />
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
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div>
            <Title level={4} style={{ marginBottom: 8 }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              上传日志文件
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              建议上传单个服务或单次故障期间采集的日志，便于后续检索和诊断。
            </Paragraph>
          </div>

          <Upload.Dragger {...uploadProps} disabled={uploading}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽日志文件到这里上传</p>
            <p className="ant-upload-hint">
              仅支持 `.log`、`.txt`，一次上传一个文件
            </p>
          </Upload.Dragger>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <Text type="secondary">上传后系统会自动入库，随后可在“日志查询”页面进行检索。</Text>
            <Upload {...uploadProps} disabled={uploading}>
              <Button icon={<UploadOutlined />} loading={uploading} type="primary">
              选择文件上传
              </Button>
            </Upload>
          </div>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchData()} loading={loadingStats}>
              刷新数据
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchUploadBatches()} loading={loadingBatches}>
              刷新批次
            </Button>
            <Button
              type="primary"
              onClick={() => void handleAnalyzeAnomalyLogs()}
              loading={analyzingAnomaly}
            >
              分析异常日志（RCA）
            </Button>
            <Button onClick={() => setParamsModalOpen(true)}>
              分析参数
            </Button>
          </div>
        </Space>
      </Card>

      <Card
        title={(
          <Space>
            <HistoryOutlined />
            <span>上传记录</span>
          </Space>
        )}
        extra={(
          <Space>
            <Button
              size="small"
              onClick={() => {
                setUploadHistory([]);
                setLastUpload(null);
                localStorage.removeItem(HISTORY_STORAGE_KEY);
                message.success('已清空本地展示记录');
              }}
              disabled={uploadHistory.length === 0}
            >
              清空展示记录
            </Button>
            <Popconfirm
              title="确认清空所有已上传日志？"
              description="该操作会删除数据库中所有上传批次对应的日志，无法恢复。"
              okText="确认清空"
              cancelText="取消"
              okButtonProps={{ danger: true, loading: clearingUploadedLogs }}
              onConfirm={() => void handleClearUploadedLogs()}
            >
              <Button size="small" danger loading={clearingUploadedLogs}>
                清空已上传日志
              </Button>
            </Popconfirm>
          </Space>
        )}
      >
        {!lastUpload ? (
          <Alert type="info" showIcon message="暂无上传记录" description="上传文件后，这里会展示本次上传结果和历史记录。" />
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              <Col span={8}>
                <Card size="small">
                  <Statistic title="最近上传日志条数" value={lastUpload.logs_created} />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <Statistic title="最近异常条数" value={lastUpload.anomaly_count} valueStyle={{ color: '#cf1322' }} />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <Statistic
                    title="最近异常占比"
                    value={lastUpload.logs_created > 0 ? ((lastUpload.anomaly_count / lastUpload.logs_created) * 100).toFixed(2) : 0}
                    suffix="%"
                  />
                </Card>
              </Col>
            </Row>

            <Card size="small" title={`最新文件：${lastUpload.filename}`}>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Text type="secondary">上传时间：{new Date(lastUpload.upload_time).toLocaleString()}</Text>
                <Progress
                  percent={lastUpload.logs_created > 0 ? Number(((lastUpload.anomaly_count / lastUpload.logs_created) * 100).toFixed(2)) : 0}
                  strokeColor="#cf1322"
                  success={{ percent: lastUpload.logs_created > 0 ? Number((100 - (lastUpload.anomaly_count / lastUpload.logs_created) * 100).toFixed(2)) : 100 }}
                  format={(percent) => `异常占比 ${percent}%`}
                />
                <Text>{lastUpload.message}</Text>
              </Space>
            </Card>

            {analyzeResult && (
              <Card
                size="small"
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

            <List
              size="small"
              header={<Text strong>最近上传历史（最多 {MAX_HISTORY_COUNT} 条）</Text>}
              bordered
              dataSource={uploadHistory}
              renderItem={(item) => (
                <List.Item>
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', gap: 12, flexWrap: 'wrap' }}>
                    <Space>
                      <Text strong>{item.filename}</Text>
                      <Tag color="blue">{item.logs_created} 条</Tag>
                      <Tag color={item.anomaly_count > 0 ? 'red' : 'green'}>
                        异常 {item.anomaly_count}
                      </Tag>
                    </Space>
                    <Text type="secondary">{new Date(item.upload_time).toLocaleString()}</Text>
                  </div>
                </List.Item>
              )}
            />

            <List
              size="small"
              header={<Text strong>已上传日志批次（可按批次删除）</Text>}
              bordered
              loading={loadingBatches}
              dataSource={uploadBatches}
              locale={{ emptyText: '暂无可管理的上传批次' }}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Popconfirm
                      key={`del-${item.batch_id}`}
                      title="确认删除该批次日志？"
                      description={`将删除批次 ${item.batch_id} 的所有日志`}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true, loading: deletingBatchId === item.batch_id }}
                      onConfirm={() => void handleDeleteBatch(item.batch_id)}
                    >
                      <Button size="small" danger loading={deletingBatchId === item.batch_id}>
                        删除批次
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', gap: 12, flexWrap: 'wrap' }}>
                    <Space wrap>
                      <Text strong>{item.filename || 'unknown.log'}</Text>
                      <Tag color="purple">{item.batch_id}</Tag>
                      <Tag color="blue">{item.logs_created} 条</Tag>
                      <Tag color={item.anomaly_count > 0 ? 'red' : 'green'}>异常 {item.anomaly_count}</Tag>
                    </Space>
                    <Text type="secondary">
                      {item.last_log_time ? new Date(item.last_log_time).toLocaleString() : '-'}
                    </Text>
                  </div>
                </List.Item>
              )}
            />
          </Space>
        )}
      </Card>

      <Modal
        title="分析参数"
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

export default LogUpload;
