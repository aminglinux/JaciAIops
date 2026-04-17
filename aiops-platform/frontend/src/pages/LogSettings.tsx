import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Select, Space, Switch, Typography, message } from 'antd';

import { logsApi } from '../services/api';
import type { LogSourceConfigPayload } from '../types';

const LogSettings = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [passwordMasked, setPasswordMasked] = useState('');
  const [apiKeyMasked, setApiKeyMasked] = useState('');
  const authType = Form.useWatch('elasticsearch_auth_type', form);

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
          </Card>
          <Card size="small" title="Loki" style={{ flex: 1, minWidth: 320 }}>
            <Form.Item label="启用 Loki" name="loki_enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="Loki URL" name="loki_url" rules={[{ required: true, message: '请输入 Loki 地址' }]}>
              <Input placeholder="例如 http://localhost:3100" />
            </Form.Item>
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
