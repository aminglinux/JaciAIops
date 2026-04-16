import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';

import AlertSectionHeader from '../components/AlertSectionHeader';
import { alertsApi } from '../services/api';
import type { AlertAnalysisResult, AlertAnalyzeRequest } from '../types';

const { TextArea } = Input;
const { Paragraph, Text } = Typography;

type AlertFormValues = {
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
  labels?: string;
  annotations?: string;
  source?: string;
  lookback_minutes?: number;
};

const severityColorMap: Record<string, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
};

const formatJson = (value: unknown) => JSON.stringify(value ?? {}, null, 2);

const parseJsonField = (value?: string, fieldName?: string) => {
  if (!value?.trim()) {
    return {};
  }

  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    throw new Error();
  } catch (error) {
    throw new Error(`${fieldName} 需要是合法的 JSON 对象`);
  }
};

const AlertAnalysis = () => {
  const [form] = Form.useForm<AlertFormValues>();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AlertAnalysisResult | null>(null);

  const initialValues = useMemo<Partial<AlertFormValues>>(
    () => ({
      alert_name: '',
      severity: 'warning',
      source: 'custom',
      lookback_minutes: 15,
      labels: '{}',
      annotations: '{}',
    }),
    []
  );

  const handleSubmit = async (values: AlertFormValues) => {
    try {
      const payload: AlertAnalyzeRequest = {
        alert_name: values.alert_name.trim(),
        severity: values.severity || 'warning',
        service: values.service?.trim() || undefined,
        instance: values.instance?.trim() || undefined,
        metric_name: values.metric_name?.trim() || undefined,
        metric_value: values.metric_value,
        threshold: values.threshold,
        starts_at: values.starts_at?.trim() || undefined,
        ends_at: values.ends_at?.trim() || undefined,
        description: values.description?.trim() || undefined,
        labels: parseJsonField(values.labels, 'labels'),
        annotations: parseJsonField(values.annotations, 'annotations'),
        source: values.source || 'custom',
        lookback_minutes: values.lookback_minutes || 15,
      };

      setLoading(true);
      const response = await alertsApi.analyze(payload);
      setResult(response);
      message.success('告警根因分析完成');
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '告警分析失败';
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const decision = result?.final_decision;
  const rca = result?.rca ?? {};
  const stages = (rca.stages ?? null) as Record<string, unknown> | null;
  const rawResponse = typeof rca.raw_response === 'string' ? rca.raw_response : '';
  const rcaError = typeof rca.error === 'string' ? rca.error : '';

  return (
    <div>
      <AlertSectionHeader
        title="手工告警分析"
        tag="RCA Playground"
        description="输入告警名称、服务、指标和上下文信息，直接触发一次根因分析流程，适合手工验证和演示场景。"
        extra={(
          <Button
            onClick={() => {
              form.resetFields();
              form.setFieldsValue(initialValues);
            }}
          >
            重置表单
          </Button>
        )}
      />
      <Card title="告警分析" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical" initialValues={initialValues} onFinish={handleSubmit}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 16,
            }}
          >
            <Form.Item label="告警名称" name="alert_name" rules={[{ required: true, message: '请输入告警名称' }]}>
              <Input placeholder="例如：OrderServiceHighLatency" />
            </Form.Item>
            <Form.Item label="告警级别" name="severity">
              <Select
                options={[
                  { label: 'warning', value: 'warning' },
                  { label: 'critical', value: 'critical' },
                  { label: 'info', value: 'info' },
                ]}
              />
            </Form.Item>
            <Form.Item label="服务" name="service">
              <Input placeholder="例如：order-service" />
            </Form.Item>
            <Form.Item label="实例/IP/Pod" name="instance">
              <Input placeholder="例如：10.0.0.12:8080" />
            </Form.Item>
            <Form.Item label="指标名称" name="metric_name">
              <Input placeholder="例如：http_request_duration_seconds" />
            </Form.Item>
            <Form.Item label="当前值" name="metric_value">
              <InputNumber style={{ width: '100%' }} placeholder="例如：2.31" />
            </Form.Item>
            <Form.Item label="阈值" name="threshold">
              <InputNumber style={{ width: '100%' }} placeholder="例如：1.5" />
            </Form.Item>
            <Form.Item label="回看窗口（分钟）" name="lookback_minutes">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="开始时间" name="starts_at">
              <Input placeholder="例如：2026-04-16T10:30:00Z" />
            </Form.Item>
            <Form.Item label="结束时间" name="ends_at">
              <Input placeholder="例如：2026-04-16T10:45:00Z" />
            </Form.Item>
            <Form.Item label="来源" name="source">
              <Input placeholder="custom" />
            </Form.Item>
          </div>

          <Form.Item label="告警描述" name="description">
            <TextArea rows={3} placeholder="补充当前症状、影响范围、业务背景" />
          </Form.Item>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: 16,
            }}
          >
            <Form.Item label="labels (JSON)" name="labels">
              <TextArea rows={6} placeholder='{"service":"order-service","instance":"10.0.0.12"}' />
            </Form.Item>
            <Form.Item label="annotations (JSON)" name="annotations">
              <TextArea rows={6} placeholder='{"summary":"订单服务延迟升高"}' />
            </Form.Item>
          </div>

          <Space>
            <Button type="primary" htmlType="submit" icon={<ThunderboltOutlined />} loading={loading}>
              开始分析
            </Button>
          </Space>
        </Form>
      </Card>

      {result && (
        <>
          {decision?.root_cause_summary && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="初步根因结论"
              description={decision.root_cause_summary}
            />
          )}

          <Collapse
            defaultActiveKey={['alert', 'decision', 'stages']}
            items={[
              {
                key: 'alert',
                label: '标准化告警',
                children: (
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="告警名称">{result.alert.alert_name}</Descriptions.Item>
                    <Descriptions.Item label="告警级别">
                      <Tag color={severityColorMap[result.alert.severity] || 'default'}>{result.alert.severity}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="服务">{result.alert.service || '-'}</Descriptions.Item>
                    <Descriptions.Item label="实例">{result.alert.instance || '-'}</Descriptions.Item>
                    <Descriptions.Item label="指标">{result.alert.metric_name || '-'}</Descriptions.Item>
                    <Descriptions.Item label="当前值">{result.alert.metric_value ?? '-'}</Descriptions.Item>
                    <Descriptions.Item label="阈值">{result.alert.threshold ?? '-'}</Descriptions.Item>
                    <Descriptions.Item label="回看窗口">{result.alert.lookback_minutes} 分钟</Descriptions.Item>
                    <Descriptions.Item label="开始时间">{result.alert.starts_at || '-'}</Descriptions.Item>
                    <Descriptions.Item label="结束时间">{result.alert.ends_at || '-'}</Descriptions.Item>
                    <Descriptions.Item label="来源">{result.alert.source}</Descriptions.Item>
                    <Descriptions.Item label="描述">{result.alert.description || '-'}</Descriptions.Item>
                  </Descriptions>
                ),
              },
              {
                key: 'query',
                label: '生成的 RCA 查询',
                children: <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{result.query}</Paragraph>,
              },
              {
                key: 'decision',
                label: '最终决策',
                children: decision ? (
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="风险级别">
                      <Tag color={decision.risk_level === 'HIGH' ? 'red' : decision.risk_level === 'MEDIUM' ? 'orange' : 'green'}>
                        {decision.risk_level}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="问题类型">{decision.problem_type || '-'}</Descriptions.Item>
                    <Descriptions.Item label="根因">{decision.root_cause || '-'}</Descriptions.Item>
                    <Descriptions.Item label="影响范围">{decision.impact || '-'}</Descriptions.Item>
                    <Descriptions.Item label="建议">{decision.recommendation || '-'}</Descriptions.Item>
                    <Descriptions.Item label="动作方案">{decision.action_plan || '-'}</Descriptions.Item>
                    <Descriptions.Item label="推理说明">{decision.reasoning || '-'}</Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Text type="secondary">暂无结构化决策结果</Text>
                ),
              },
              {
                key: 'stages',
                label: '分析阶段输出',
                children: stages ? (
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {formatJson(stages)}
                  </pre>
                ) : (
                  <Text type="secondary">暂无阶段明细</Text>
                ),
              },
              {
                key: 'raw',
                label: '原始响应',
                children: rawResponse ? (
                  <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{rawResponse}</Paragraph>
                ) : (
                  <Text type="secondary">暂无原始响应</Text>
                ),
              },
              {
                key: 'meta',
                label: '元数据',
                children: (
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="模式">{result.mode}</Descriptions.Item>
                    <Descriptions.Item label="RCA 错误">{rcaError || '-'}</Descriptions.Item>
                    <Descriptions.Item label="labels">
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {formatJson(result.alert.labels)}
                      </pre>
                    </Descriptions.Item>
                    <Descriptions.Item label="annotations">
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {formatJson(result.alert.annotations)}
                      </pre>
                    </Descriptions.Item>
                  </Descriptions>
                ),
              },
            ]}
          />
        </>
      )}
    </div>
  );
};

export default AlertAnalysis;
