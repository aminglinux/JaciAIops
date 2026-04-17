import { useEffect, useState, useCallback } from 'react';
import { Alert, Button, Card, DatePicker, Input, Modal, Select, Space, Switch, Table, Tag, Typography, message } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import { useLocation } from 'react-router-dom';

import { logsApi } from '../services/api';
import type { Log } from '../types';

const { Text } = Typography;
const { RangePicker } = DatePicker;

const LogList = () => {
  const location = useLocation();
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(false);
  const [sourceType, setSourceType] = useState<string>('local');
  const [levelFilter, setLevelFilter] = useState<string | undefined>();
  const [keywordFilter, setKeywordFilter] = useState('');
  const [serviceFilter, setServiceFilter] = useState('');
  const [timeRange, setTimeRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [incidentOnly, setIncidentOnly] = useState(false);
  const [uploadedOnly, setUploadedOnly] = useState(false);
  const [queryState, setQueryState] = useState({
    sourceType: 'local',
    level: undefined as string | undefined,
    levels: undefined as string | undefined,
    keyword: '',
    service: '',
    uploadedOnly: false,
    startTime: undefined as string | undefined,
    endTime: undefined as string | undefined,
    incidentOnly: false,
  });
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await logsApi.queryLogs({
        source_type: queryState.sourceType,
        keyword: queryState.keyword || undefined,
        level: queryState.level,
        levels: queryState.levels,
        service: queryState.service || undefined,
        uploaded_only: queryState.sourceType === 'local' ? queryState.uploadedOnly : false,
        start_time: queryState.startTime,
        end_time: queryState.endTime,
        incident_only: queryState.incidentOnly,
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setLogs(data);
      setPagination((prev) => ({
        ...prev,
        total: (prev.current - 1) * prev.pageSize + data.length + (data.length === prev.pageSize ? 1 : 0),
      }));
    } catch (error) {
      message.error('获取日志失败');
    } finally {
      setLoading(false);
    }
  }, [queryState, pagination.current, pagination.pageSize]);

  useEffect(() => {
    void fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const source = params.get('source');
    const service = params.get('service');
    const incident = params.get('incident');
    const minutes = params.get('minutes');
    const uploaded = params.get('uploaded');

    if (!source && !service && !incident && !minutes && !uploaded) {
      return;
    }

    const nextIncidentOnly = incident === '1' || incident === 'true';
    const nextSourceType = source || 'local';
    const nextUploadedOnly = uploaded === '1' || uploaded === 'true';
    const nextService = service || '';
    const nextMinutes = Number(minutes || 30);
    const nextTimeRange = nextIncidentOnly
      ? [dayjs().subtract(Number.isFinite(nextMinutes) ? nextMinutes : 30, 'minute'), dayjs()] as [Dayjs, Dayjs]
      : null;

    setSourceType(nextSourceType);
    setServiceFilter(nextService);
    setIncidentOnly(nextIncidentOnly);
    setUploadedOnly(nextSourceType === 'local' ? nextUploadedOnly : false);
    setLevelFilter(undefined);
    setTimeRange(nextTimeRange);
    setPagination((prev) => ({ ...prev, current: 1, total: 0 }));
    setQueryState({
      sourceType: nextSourceType,
      level: undefined,
      levels: nextIncidentOnly ? 'ERROR,WARN' : undefined,
      keyword: '',
      service: nextService,
      uploadedOnly: nextSourceType === 'local' ? nextUploadedOnly : false,
      startTime: nextTimeRange?.[0]?.toISOString(),
      endTime: nextTimeRange?.[1]?.toISOString(),
      incidentOnly: nextIncidentOnly,
    });
  }, [location.search]);

  useEffect(() => {
    if (incidentOnly && !timeRange) {
      setTimeRange([dayjs().subtract(30, 'minute'), dayjs()]);
    }
  }, [incidentOnly, timeRange]);

  const applyFilters = () => {
    const effectiveTimeRange = incidentOnly
      ? (timeRange ?? [dayjs().subtract(30, 'minute'), dayjs()])
      : timeRange;
    setPagination((prev) => ({ ...prev, current: 1, total: 0 }));
    if (incidentOnly && !timeRange) {
      setTimeRange(effectiveTimeRange);
    }
    setQueryState({
      sourceType,
      level: incidentOnly ? undefined : levelFilter,
      levels: incidentOnly ? 'ERROR,WARN' : undefined,
      keyword: keywordFilter.trim(),
      service: serviceFilter.trim(),
      uploadedOnly: sourceType === 'local' ? uploadedOnly : false,
      startTime: effectiveTimeRange?.[0]?.toISOString(),
      endTime: effectiveTimeRange?.[1]?.toISOString(),
      incidentOnly,
    });
  };

  const handleFeedback = async (logId: string | number, feedbackType: boolean) => {
    try {
      await logsApi.submitFeedback(Number(logId), feedbackType);
      message.success('反馈已提交');
      void fetchLogs();
    } catch (error) {
      message.error('提交失败');
      }
  };

  const showDetail = (log: Log) => {
    Modal.info({
      title: '日志详情',
      width: 860,
      content: (
        <div style={{ marginTop: 16 }}>
          <p><Text strong>时间：</Text>{dayjs(log.timestamp).format('YYYY-MM-DD HH:mm:ss')}</p>
          <p><Text strong>级别：</Text><Tag color={log.level === 'ERROR' ? 'red' : log.level === 'WARN' ? 'orange' : 'blue'}>{log.level}</Tag></p>
          <p><Text strong>来源：</Text>{log.source}</p>
          <p><Text strong>来源类型：</Text>{log.source_type || 'local'}</p>
          {log.service && <p><Text strong>服务：</Text>{log.service}</p>}
          <p><Text strong>异常分数：</Text>{log.anomaly_score?.toFixed(3) || 'N/A'}</p>
          <p><Text strong>用户反馈：</Text>
            {log.user_feedback === null ? '未标注' : log.user_feedback ? '误报' : '确认异常'}
          </p>
          {log.labels && Object.keys(log.labels).length > 0 && (
            <p>
              <Text strong>标签：</Text>
              {Object.entries(log.labels).map(([key, value]) => <Tag key={key}>{key}: {value}</Tag>)}
            </p>
          )}
          <p><Text strong>内容：</Text></p>
          <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, overflow: 'auto', maxHeight: 240 }}>
            {log.content}
          </pre>
          {log.raw && (
            <>
              <p><Text strong>原始数据：</Text></p>
              <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, overflow: 'auto', maxHeight: 240 }}>
                {JSON.stringify(log.raw, null, 2)}
              </pre>
            </>
          )}
        </div>
      ),
    });
  };

  const isLocalSource = sourceType === 'local';

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 90,
      render: (level: string) => {
        const colorMap: Record<string, string> = { ERROR: 'red', WARN: 'orange', INFO: 'blue', DEBUG: 'gray' };
        return <Tag color={colorMap[level] || 'default'}>{level}</Tag>;
      },
    },
    {
      title: '来源',
      key: 'source',
      width: 180,
      render: (_: unknown, record: Log) => (
        <Space size={4} wrap>
          <Tag color={record.source_type === 'elasticsearch' ? 'gold' : record.source_type === 'loki' ? 'cyan' : 'blue'}>
            {record.source_type || 'local'}
          </Tag>
          <Text>{record.source}</Text>
        </Space>
      ),
    },
    {
      title: '服务',
      dataIndex: 'service',
      key: 'service',
      width: 140,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (text: string, record: Log) => (
        <a onClick={() => showDetail(record)} style={{ color: record.is_anomaly ? '#cf1322' : undefined }}>
          {text}
        </a>
      ),
    },
    {
      title: '异常',
      dataIndex: 'is_anomaly',
      key: 'is_anomaly',
      width: 110,
      render: (isAnomaly: boolean, record: Log) =>
        isAnomaly ? <Tag color="red">异常 ({record.anomaly_score?.toFixed(2)})</Tag> : <Tag color="green">正常</Tag>,
    },
    {
      title: '反馈',
      key: 'feedback',
      width: 120,
      render: (_: unknown, record: Log) => (
        isLocalSource ? (
          <Space size="small">
            <Button
              size="small"
              type="text"
              icon={<CloseCircleOutlined style={{ color: record.user_feedback === true ? '#52c41a' : undefined }} />}
              onClick={() => void handleFeedback(record.id, true)}
              title="标记为误报"
            />
            <Button
              size="small"
              type="text"
              icon={<CheckCircleOutlined style={{ color: record.user_feedback === false ? '#cf1322' : undefined }} />}
              onClick={() => void handleFeedback(record.id, false)}
              title="确认异常"
            />
          </Space>
        ) : (
          <Text type="secondary">仅本地日志支持</Text>
        )
      ),
    },
  ];

  return (
    <div>
      <Card>
        {!isLocalSource && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="当前为外部日志只读模式"
            description="Elasticsearch 和 Loki 日志实时查询后直接展示，不落库；当前版本暂不支持外部日志反馈回写。"
          />
        )}

        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            style={{ width: 160 }}
            value={sourceType}
            onChange={(value) => {
              setSourceType(value);
            }}
            options={[
              { value: 'local', label: '本地日志' },
              { value: 'elasticsearch', label: 'Elasticsearch' },
              { value: 'loki', label: 'Loki' },
            ]}
          />
          <Select
            placeholder="日志级别"
            allowClear
            style={{ width: 120 }}
            value={levelFilter}
            onChange={setLevelFilter}
            disabled={incidentOnly}
            options={[
              { value: 'ERROR', label: 'ERROR' },
              { value: 'WARN', label: 'WARN' },
              { value: 'INFO', label: 'INFO' },
              { value: 'DEBUG', label: 'DEBUG' },
            ]}
          />
          <Input
            placeholder="关键字"
            style={{ width: 180 }}
            value={keywordFilter}
            onChange={(event) => setKeywordFilter(event.target.value)}
            onPressEnter={applyFilters}
          />
          <Input
            placeholder="服务名"
            style={{ width: 180 }}
            value={serviceFilter}
            onChange={(event) => setServiceFilter(event.target.value)}
            onPressEnter={applyFilters}
          />
          <RangePicker
            showTime
            value={timeRange}
            onChange={(value) => setTimeRange(value)}
          />
          <Space size={4}>
            <Switch checked={incidentOnly} onChange={setIncidentOnly} />
            <Text>仅看故障日志</Text>
          </Space>
          {isLocalSource && (
            <Space size={4}>
              <Switch checked={uploadedOnly} onChange={setUploadedOnly} />
              <Text>仅看上传日志</Text>
            </Space>
          )}
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={applyFilters}
          >
            查询
          </Button>
        </Space>

        {incidentOnly && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message="故障日志模式已开启"
            description="默认筛选最近 30 分钟内的 ERROR/WARN 日志，并附带 error、exception、timeout、failed、oom 等故障关键词匹配。"
          />
        )}

        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showTotal: () => `本页 ${logs.length} 条`,
            onChange: (page, pageSize) => setPagination((prev) => ({ ...prev, current: page, pageSize })),
          }}
          size="small"
        />
      </Card>
    </div>
  );
};

export default LogList;
