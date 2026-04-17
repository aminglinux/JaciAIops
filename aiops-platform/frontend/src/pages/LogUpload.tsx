import { useEffect, useState } from 'react';
import { Card, Typography, Upload, Button, Alert, Space, message, Statistic, Row, Col, Progress, List, Tag, Popconfirm } from 'antd';
import { InboxOutlined, UploadOutlined, FileTextOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';

import { logsApi } from '../services/api';
import type { LogStats, LogUploadResult, UploadBatchSummary } from '../types';

const { Title, Paragraph, Text } = Typography;
const HISTORY_STORAGE_KEY = 'log_upload_history_v1';
const MAX_HISTORY_COUNT = 12;

type UploadHistoryRecord = LogUploadResult & {
  id: string;
};

const LogUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [lastUpload, setLastUpload] = useState<UploadHistoryRecord | null>(null);
  const [uploadHistory, setUploadHistory] = useState<UploadHistoryRecord[]>([]);
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
    } catch {
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
      } catch {
        message.error('上传失败，请稍后重试');
      } finally {
        setUploading(false);
      }
      return false;
    },
  };

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
        description="仅负责上传和批次管理；异常日志分析已迁移到“日志中心 / 异常分析”页面。"
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
              建议上传单个服务或单次故障期间采集的日志，便于后续检索。
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
    </Space>
  );
};

export default LogUpload;
