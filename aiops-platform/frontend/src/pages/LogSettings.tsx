import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Descriptions, Form, Input, Select, Space, Switch, Tag, Typography, message } from 'antd';
import type { AxiosError } from 'axios';

import { logsApi } from '../services/api';
import type { LogSourceConfigPayload, LogSourceTestResult } from '../types';

const LogSettings = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingElastic, setTestingElastic] = useState(false);
  const [testingLoki, setTestingLoki] = useState(false);
  const [passwordMasked, setPasswordMasked] = useState('');
  const [apiKeyMasked, setApiKeyMasked] = useState('');
  const [elasticResult, setElasticResult] = useState<LogSourceTestResult | null>(null);
  const [lokiResult, setLokiResult] = useState<LogSourceTestResult | null>(null);
  const authType = Form.useWatch('elasticsearch_auth_type', form);

  const resultTone = useMemo(
    () => ({
      elastic: elasticResult?.success ? 'success' : 'error',
      loki: lokiResult?.success ? 'success' : 'error',
    }),
    [elasticResult, lokiResult]
  );

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await logsApi.getConfig();
      form.setFieldsValue({
        elasticsearch_enabled: config.elasticsearchEnabled,
        elasticsearch_url: config.elasticsearchUrl,
        elasticsearch_index_pattern: config.elasticsearchIndexPattern,
        elasticsearch_auth_type: config.elasticsearchAuthType || 'none',
        elasticsearch_username: config.elasticsearchUsername || '',
        elasticsearch_password: '',
        elasticsearch_api_key: '',
        elasticsearch_tls_verify: config.elasticsearchTlsVerify,
        loki_enabled: config.lokiEnabled,
        loki_url: config.lokiUrl,
      });
      setPasswordMasked(config.elasticsearchPasswordMasked || '');
      setApiKeyMasked(config.elasticsearchApiKeyMasked || '');
    } catch (error) {
      message.error('读取日志源配置失败');
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const handleSave = async (values: LogSourceConfigPayload) => {
    setSaving(true);
    try {
      await logsApi.updateConfig(values);
      message.success('日志源配置已保存');
      await loadConfig();
    } catch (error) {
      message.error('保存日志源配置失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      const values = (await form.validateFields()) as LogSourceConfigPayload;
      setTestingElastic(true);
      const result = await logsApi.testConfig(values);
      setElasticResult(result);
      message.success(result.message);
    } catch (error) {
      const axiosError = error as AxiosError<{ detail?: string }>;
      const detail = axiosError.response?.data?.detail;
      if (!detail && error instanceof Error && error.message) {
        message.error(error.message);
      } else if (detail) {
        message.error(detail);
      }
      if (detail) {
        setElasticResult({
          success: false,
          message: detail,
        });
      }
    } finally {
      setTestingElastic(false);
    }
  };

  const handleTestLokiConnection = async () => {
    try {
      const values = (await form.validateFields(['loki_enabled', 'loki_url'])) as Pick<LogSourceConfigPayload, 'loki_enabled' | 'loki_url'>;
      setTestingLoki(true);
      const payload = {
        ...(form.getFieldsValue() as LogSourceConfigPayload),
        ...values,
      };
      const result = await logsApi.testLokiConfig(payload);
      setLokiResult(result);
      message.success(result.message);
    } catch (error) {
      const axiosError = error as AxiosError<{ detail?: string }>;
      const detail = axiosError.response?.data?.detail;
      if (!detail && error instanceof Error && error.message) {
        message.error(error.message);
      } else if (detail) {
        message.error(detail);
      }
      if (detail) {
        setLokiResult({
          success: false,
          message: detail,
        });
      }
    } finally {
      setTestingLoki(false);
    }
  };

  return (
    <Card title="日志源配置" loading={loading}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        description="在这里配置日志列表查询使用的 Elasticsearch 和 Loki 地址。Elasticsearch 如开启认证，密钥会加密保存，页面只展示脱敏结果。"
      />
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          elasticsearch_auth_type: 'none',
          elasticsearch_tls_verify: true,
        }}
        onFinish={(values) => {
          void handleSave(values as LogSourceConfigPayload);
        }}
      >
        <Space style={{ width: '100%' }} size={16} align="start" wrap>
          <Card size="small" title="Elasticsearch" style={{ flex: 1, minWidth: 320 }}>
            <Form.Item label="启用 Elasticsearch" name="elasticsearch_enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="Elasticsearch URL" name="elasticsearch_url" rules={[{ required: true, message: '请输入 Elasticsearch 地址' }]}>
              <Input placeholder="例如 http://localhost:9200" />
            </Form.Item>
            <Form.Item label="Index Pattern" name="elasticsearch_index_pattern" rules={[{ required: true, message: '请输入索引模式' }]}>
              <Input placeholder="例如 logstash-*" />
            </Form.Item>
            <Form.Item label="认证方式" name="elasticsearch_auth_type">
              <Select
                options={[
                  { label: '无认证', value: 'none' },
                  { label: 'Basic Auth', value: 'basic' },
                  { label: 'API Key', value: 'api_key' },
                ]}
              />
            </Form.Item>
            {authType === 'basic' && (
              <>
                <Form.Item label="用户名" name="elasticsearch_username" preserve={false} rules={[{ required: true, message: '请输入用户名' }]}>
                  <Input placeholder="例如 elastic" autoComplete="username" />
                </Form.Item>
                <Form.Item
                  label="密码"
                  name="elasticsearch_password"
                  preserve={false}
                  extra={passwordMasked ? `当前密码：${passwordMasked}，留空表示不修改` : '首次配置 Basic Auth 时请输入密码'}
                  rules={[
                    {
                      validator: async (_, value?: string) => {
                        if (passwordMasked || value) {
                          return;
                        }
                        throw new Error('请输入密码');
                      },
                    },
                  ]}
                >
                  <Input.Password placeholder="请输入新密码" autoComplete="new-password" />
                </Form.Item>
              </>
            )}
            {authType === 'api_key' && (
              <Form.Item
                label="API Key"
                name="elasticsearch_api_key"
                preserve={false}
                extra={apiKeyMasked ? `当前 API Key：${apiKeyMasked}，留空表示不修改` : '请输入 Elasticsearch API Key'}
                rules={[
                  {
                    validator: async (_, value?: string) => {
                      if (apiKeyMasked || value) {
                        return;
                      }
                      throw new Error('请输入 API Key');
                    },
                  },
                ]}
              >
                <Input.Password placeholder="请输入 API Key" autoComplete="off" />
              </Form.Item>
            )}
            <Form.Item
              label="TLS 证书校验"
              name="elasticsearch_tls_verify"
              valuePropName="checked"
              extra={<Typography.Text type="secondary">HTTPS 使用自签名证书时可临时关闭，生产环境建议开启。</Typography.Text>}
            >
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>
            <Space style={{ marginTop: 8 }}>
              <Button onClick={() => void handleTestConnection()} loading={testingElastic}>
                测试 Elasticsearch 连接
              </Button>
              <Typography.Text type="secondary">会使用当前表单中的地址和认证信息测试，不必先保存。</Typography.Text>
            </Space>
            {elasticResult && (
              <Card
                size="small"
                style={{ marginTop: 16, borderRadius: 12 }}
                bodyStyle={{ padding: 12 }}
                title={
                  <Space>
                    <span>Elasticsearch 测试结果</span>
                    <Tag color={resultTone.elastic === 'success' ? 'green' : 'red'}>
                      {elasticResult.success ? '连接成功' : '连接失败'}
                    </Tag>
                  </Space>
                }
              >
                <Typography.Paragraph style={{ marginBottom: 12 }}>{elasticResult.message}</Typography.Paragraph>
                {elasticResult.success && elasticResult.details ? (
                  <Descriptions size="small" column={1} bordered>
                    <Descriptions.Item label="集群名称">{elasticResult.details.clusterName || '-'}</Descriptions.Item>
                    <Descriptions.Item label="版本">{elasticResult.details.version || '-'}</Descriptions.Item>
                    <Descriptions.Item label="认证方式">{elasticResult.details.authenticatedAs || '-'}</Descriptions.Item>
                    <Descriptions.Item label="集群 UUID">{elasticResult.details.clusterUuid || '-'}</Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Alert type="error" showIcon message={elasticResult.message} />
                )}
              </Card>
            )}
          </Card>
          <Card size="small" title="Loki" style={{ flex: 1, minWidth: 320 }}>
            <Form.Item label="启用 Loki" name="loki_enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="Loki URL" name="loki_url" rules={[{ required: true, message: '请输入 Loki 地址' }]}>
              <Input placeholder="例如 http://localhost:3100" />
            </Form.Item>
            <Space style={{ marginTop: 8 }}>
              <Button onClick={() => void handleTestLokiConnection()} loading={testingLoki}>
                测试 Loki 连接
              </Button>
              <Typography.Text type="secondary">会访问 Loki 标签接口验证连通性。</Typography.Text>
            </Space>
            {lokiResult && (
              <Card
                size="small"
                style={{ marginTop: 16, borderRadius: 12 }}
                bodyStyle={{ padding: 12 }}
                title={
                  <Space>
                    <span>Loki 测试结果</span>
                    <Tag color={resultTone.loki === 'success' ? 'green' : 'red'}>
                      {lokiResult.success ? '连接成功' : '连接失败'}
                    </Tag>
                  </Space>
                }
              >
                <Typography.Paragraph style={{ marginBottom: 12 }}>{lokiResult.message}</Typography.Paragraph>
                {lokiResult.success && lokiResult.details ? (
                  <Descriptions size="small" column={1} bordered>
                    <Descriptions.Item label="地址">{lokiResult.details.endpoint || '-'}</Descriptions.Item>
                    <Descriptions.Item label="状态">{lokiResult.details.status || '-'}</Descriptions.Item>
                    <Descriptions.Item label="标签数量">{String(lokiResult.details.labelsCount ?? '-')}</Descriptions.Item>
                    <Descriptions.Item label="样例标签">{lokiResult.details.sampleLabels || '-'}</Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Alert type="error" showIcon message={lokiResult.message} />
                )}
              </Card>
            )}
          </Card>
        </Space>
        <div style={{ marginTop: 16 }}>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存日志源配置
          </Button>
        </div>
      </Form>
    </Card>
  );
};

export default LogSettings;
