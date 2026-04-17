import { useEffect, useState } from 'react';
import { Card, Typography, Upload, Button, Alert, Space, message, Statistic, Row, Col, Progress, List, Tag } from 'antd';
import { InboxOutlined, UploadOutlined, FileTextOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useNavigate } from 'react-router-dom';

import { alertsApi, logsApi } from '../services/api';
import type { AlertFinalDecision, LogAnomalyAnalyzeResult, LogStats, LogUploadResult } from '../types';

const { Title, Paragraph, Text } = Typography;
const HISTORY_STORAGE_KEY = 'log_upload_history_v1';
const MAX_HISTORY_COUNT = 12;

type UploadHistoryRecord = LogUploadResult & {
  id: string;
};

const LogUpload = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [analyzingAnomaly, setAnalyzingAnomaly] = useState(false);
  const [lastUpload, setLastUpload] = useState<UploadHistoryRecord | null>(null);
  const [uploadHistory, setUploadHistory] = useState<UploadHistoryRecord[]>([]);
  const [analyzeResult, setAnalyzeResult] = useState<LogAnomalyAnalyzeResult | null>(null);

  const persistUploadHistory = (records: UploadHistoryRecord[]) => {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(records));
  };

  const fetchData = async () => {
    setLoadingStats(true);
    try {
      const statsData = await logsApi.getStats();
      setStats(statsData);
      message.success('日志统计已刷新');
    } catch (error) {
      message.error('刷新数据失败');
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    void fetchData();
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
      } catch (error) {
        message.error('上传失败，请稍后重试');
      } finally {
        setUploading(false);
      }
      return false;
    },
  };

  const handleAnalyzeAnomalyLogs = async () => {
    if ((stats?.anomaly_count || 0) <= 0) {
      message.info('当前没有异常日志，无需触发 RCA');
      return;
    }
    setAnalyzingAnomaly(true);
    try {
      const result = await alertsApi.analyzeFromLogs({
        lookback_minutes: 60,
        max_logs: 300,
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
            <Button
              type="primary"
              onClick={() => void handleAnalyzeAnomalyLogs()}
              loading={analyzingAnomaly}
              disabled={(stats?.anomaly_count || 0) <= 0}
            >
              分析异常日志（RCA）
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
          <Button
            size="small"
            onClick={() => {
              setUploadHistory([]);
              setLastUpload(null);
              localStorage.removeItem(HISTORY_STORAGE_KEY);
              message.success('已清空上传记录');
            }}
            disabled={uploadHistory.length === 0}
          >
            清空记录
          </Button>
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
          </Space>
        )}
      </Card>
    </Space>
  );
};

export default LogUpload;
