import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Switch, message } from 'antd';

import { logsApi } from '../services/api';
import type { LogSourceConfigPayload } from '../types';

const LogSettings = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await logsApi.getConfig();
      form.setFieldsValue({
        elasticsearch_enabled: config.elasticsearchEnabled,
        elasticsearch_url: config.elasticsearchUrl,
        elasticsearch_index_pattern: config.elasticsearchIndexPattern,
        loki_enabled: config.lokiEnabled,
        loki_url: config.lokiUrl,
      });
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
        description="在这里配置日志列表查询使用的 Elasticsearch 和 Loki 地址。保存后，日志列表页面会立即使用新配置。"
      />
      <Form
        form={form}
        layout="vertical"
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
