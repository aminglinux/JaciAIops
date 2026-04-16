import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Descriptions, Divider, Drawer, Modal, Select, Space, Spin, Table, Tag, Typography, message } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';

import AlertSectionHeader from '../components/AlertSectionHeader';
import { alertsApi } from '../services/api';
import type { AlertEventDetail, AlertEventSummary } from '../types';

const { Paragraph, Text } = Typography;

const severityColorMap: Record<string, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
};

const statusColorMap: Record<string, string> = {
  completed: 'green',
  failed: 'red',
  processing: 'blue',
};

const logEvidenceColorMap: Record<string, string> = {
  matched: 'red',
  weak_matched: 'orange',
  not_found: 'default',
};

const AlertCenter = () => {
  const navigate = useNavigate();
  const [events, setEvents] = useState<AlertEventSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<AlertEventDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const rootCauseSummary = typeof selectedEvent?.final_decision?.root_cause_summary === 'string'
    ? selectedEvent.final_decision.root_cause_summary
    : undefined;
  const finalDecision = selectedEvent?.final_decision;
  const logEvidence = finalDecision?.log_evidence;
  const evidenceChain = finalDecision?.evidence_chain ?? [];
  const propagationPath = finalDecision?.propagation_path ?? [];
  const affectedServices = finalDecision?.affected_services ?? [];
  const decisionRiskColor =
    finalDecision?.risk_level === 'HIGH'
      ? 'red'
      : finalDecision?.risk_level === 'MEDIUM'
        ? 'orange'
        : 'green';
  const alertmanagerConfigExample = useMemo(
    () => `route:
  receiver: aiops-rca
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 1h

receivers:
  - name: aiops-rca
    webhook_configs:
      - url: 'http://your-aiops-backend/api/alerts/webhook/alertmanager'
        send_resolved: true`,
    []
  );

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await alertsApi.listEvents({
        limit: 50,
        source: sourceFilter,
        status: statusFilter,
      });
      setEvents(data.events);
    } catch (error) {
      message.error('获取告警事件失败');
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, statusFilter]);

  useEffect(() => {
    void fetchEvents();
  }, [fetchEvents]);

  const openDetail = async (eventId: number) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    setSelectedEvent(null);
    try {
      const data = await alertsApi.getEvent(eventId);
      setSelectedEvent(data);
    } catch (error) {
      message.error('获取告警详情失败');
      setDrawerOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '告警',
      dataIndex: 'alert_name',
      key: 'alert_name',
      render: (value: string, record: AlertEventSummary) => (
        <a onClick={() => void openDetail(record.id)}>{value}</a>
      ),
    },
    {
      title: '级别',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (value: string) => <Tag color={severityColorMap[value] || 'default'}>{value}</Tag>,
    },
    {
      title: '服务',
      dataIndex: 'service',
      key: 'service',
      width: 160,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '实例',
      dataIndex: 'instance',
      key: 'instance',
      width: 180,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 120,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string) => <Tag color={statusColorMap[value] || 'default'}>{value}</Tag>,
    },
    {
      title: '摘要',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (value: string) => value || '-',
    },
  ];

  return (
    <div>
      <AlertSectionHeader
        title="告警事件"
        tag="Event Center"
        description="集中查看 Alertmanager 或手工触发进入平台的告警事件，并下钻查看根因分析结果和证据链。"
        extra={(
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchEvents()}>
              刷新列表
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/alerts/analyze')}>
              手工分析
            </Button>
          </Space>
        )}
      />
      <Card
        title="告警中心"
        extra={(
          <Space>
            <Select
              allowClear
              placeholder="来源"
              style={{ width: 140 }}
              value={sourceFilter}
              onChange={setSourceFilter}
              options={[
                { label: 'custom', value: 'custom' },
                { label: 'alertmanager', value: 'alertmanager' },
              ]}
            />
            <Select
              allowClear
              placeholder="状态"
              style={{ width: 140 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { label: 'completed', value: 'completed' },
                { label: 'failed', value: 'failed' },
              ]}
            />
          </Space>
        )}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="接入说明"
          description={(
            <Space direction="vertical" size={8}>
              <span>将 Alertmanager webhook 指向 `/api/alerts/webhook/alertmanager` 后，这里会自动沉淀收到的告警与 RCA 结果。</span>
              <Button type="link" style={{ padding: 0, width: 'fit-content' }} onClick={() => setConfigModalOpen(true)}>
                查看 Alertmanager 配置示例
              </Button>
            </Space>
          )}
        />

        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={events}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Drawer
        title={selectedEvent ? `告警详情 #${selectedEvent.id}` : '告警详情'}
        width={760}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {detailLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
            <Spin />
          </div>
        ) : selectedEvent && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {rootCauseSummary && (
              <Alert
                type="warning"
                showIcon
                message="初步根因结论"
                description={rootCauseSummary}
              />
            )}

            <Card size="small" title="基本信息">
              <Descriptions column={2} size="small">
                <Descriptions.Item label="告警名称">{selectedEvent.alert_name}</Descriptions.Item>
                <Descriptions.Item label="级别">
                  <Tag color={severityColorMap[selectedEvent.severity] || 'default'}>{selectedEvent.severity}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="服务">{selectedEvent.service || '-'}</Descriptions.Item>
                <Descriptions.Item label="实例">{selectedEvent.instance || '-'}</Descriptions.Item>
                <Descriptions.Item label="来源">{selectedEvent.source}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={statusColorMap[selectedEvent.status] || 'default'}>{selectedEvent.status}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="开始时间">{selectedEvent.starts_at ? dayjs(selectedEvent.starts_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
                <Descriptions.Item label="结束时间">{selectedEvent.ends_at ? dayjs(selectedEvent.ends_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
                <Descriptions.Item label="错误信息">{selectedEvent.error_message || '-'}</Descriptions.Item>
                <Descriptions.Item label="指纹">{selectedEvent.fingerprint || '-'}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card size="small" title="分析查询">
              <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{selectedEvent.query}</Paragraph>
            </Card>

            <Card size="small" title="证据链">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="受影响服务">
                  {affectedServices.length > 0 ? affectedServices.map((item) => <Tag key={item}>{item}</Tag>) : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="传播路径">
                  {propagationPath.length > 0 ? (
                    <Space wrap split={<span style={{ color: '#999' }}>→</span>}>
                      {propagationPath.map((item) => <Tag key={item} color="blue">{item}</Tag>)}
                    </Space>
                  ) : (
                    '-'
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="关键证据">
                  {evidenceChain.length > 0 ? (
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      {evidenceChain.map((item, index) => (
                        <div
                          key={`${item}-${index}`}
                          style={{ padding: '8px 12px', background: '#fafafa', borderRadius: 8, border: '1px solid #f0f0f0' }}
                        >
                          {item}
                        </div>
                      ))}
                    </Space>
                  ) : (
                    <Text type="secondary">暂无结构化证据链</Text>
                  )}
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card size="small" title="日志证据">
              <Descriptions column={2} size="small">
                <Descriptions.Item label="命中状态">
                  <Tag color={logEvidenceColorMap[logEvidence?.status || ''] || 'default'}>
                    {logEvidence?.status || 'not_found'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="日志置信度">
                  <Tag>{logEvidence?.confidence || '-'}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="可疑组件">
                  {logEvidence?.suspected_component || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="匹配分数">
                  {logEvidence?.match_score ?? '-'}
                </Descriptions.Item>
                <Descriptions.Item label="命中字段">
                  {logEvidence?.matched_fields?.length ? logEvidence.matched_fields.map((item) => <Tag key={item}>{item}</Tag>) : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="日志来源">
                  {logEvidence?.source_type || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="摘要">
                  {logEvidence?.summary || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="命中模式">
                  {logEvidence?.top_patterns?.length ? logEvidence.top_patterns.map((item) => <Tag key={item} color="orange">{item}</Tag>) : '-'}
                </Descriptions.Item>
              </Descriptions>

              {logEvidence?.sample_logs?.length ? (
                <>
                  <Divider style={{ margin: '16px 0' }} />
                  <Text strong>日志样本</Text>
                  <Space direction="vertical" size={8} style={{ width: '100%', marginTop: 12 }}>
                    {logEvidence.sample_logs.map((item, index) => (
                      <pre
                        key={`${item}-${index}`}
                        style={{ margin: 0, padding: 12, background: '#fff7e6', borderRadius: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                      >
                        {item}
                      </pre>
                    ))}
                  </Space>
                </>
              ) : null}
            </Card>

            <Card size="small" title="最终决策">
              <Descriptions column={2} size="small">
                <Descriptions.Item label="决策状态">
                  <Tag color={finalDecision?.decision === 'ERROR' ? 'red' : 'blue'}>
                    {finalDecision?.decision || '-'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="问题类型">
                  {finalDecision?.problem_type || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="风险等级">
                  <Tag color={decisionRiskColor}>
                    {finalDecision?.risk_level || '-'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="总体置信度">
                  <Tag>{finalDecision?.confidence || '-'}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="根因">
                  {finalDecision?.root_cause || rootCauseSummary || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="影响范围">
                  {finalDecision?.impact || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="修复建议">
                  {finalDecision?.recommendation || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="行动方案">
                  {finalDecision?.action_plan || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="分析摘要">
                  {finalDecision?.analysis_summary || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="推理说明">
                  {finalDecision?.reasoning || '-'}
                </Descriptions.Item>
                {finalDecision?.error && (
                  <Descriptions.Item label="错误信息">
                    <Text type="danger">{finalDecision.error}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>

              <Divider style={{ margin: '16px 0' }} />
              <Text strong>原始决策 JSON</Text>
              <pre style={{ margin: '12px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#fafafa', padding: 12, borderRadius: 8 }}>
                {JSON.stringify(selectedEvent.final_decision ?? {}, null, 2)}
              </pre>
            </Card>

            <Card size="small" title="RCA 结果">
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(selectedEvent.rca ?? {}, null, 2)}
              </pre>
            </Card>

            <Card size="small" title="标签与注解">
              <Text strong>labels</Text>
              <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(selectedEvent.labels ?? {}, null, 2)}
              </pre>
              <Text strong>annotations</Text>
              <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(selectedEvent.annotations ?? {}, null, 2)}
              </pre>
            </Card>
          </Space>
        )}
      </Drawer>
      <Modal
        title="Alertmanager 配置示例"
        open={configModalOpen}
        onCancel={() => setConfigModalOpen(false)}
        footer={[
          <Button key="close" type="primary" onClick={() => setConfigModalOpen(false)}>
            知道了
          </Button>,
        ]}
        width={720}
      >
        <Paragraph>
          将下面示例中的 `your-aiops-backend` 替换成实际的 AIOps 服务地址即可。
        </Paragraph>
        <pre style={{ margin: 0, padding: 16, background: '#f7f7f7', borderRadius: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {alertmanagerConfigExample}
        </pre>
      </Modal>
    </div>
  );
};

export default AlertCenter;
