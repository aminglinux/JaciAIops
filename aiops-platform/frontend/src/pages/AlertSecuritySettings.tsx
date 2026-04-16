import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Switch, message } from 'antd';
import { SafetyOutlined } from '@ant-design/icons';

import AlertSectionHeader from '../components/AlertSectionHeader';
import { alertsApi } from '../services/api';
import type { AlertWebhookSecurityConfigPayload } from '../types';

const ipv4Segment = '(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)';
const ipv4Regex = new RegExp(`^${ipv4Segment}(\\.${ipv4Segment}){3}$`);
const cidrRegex = new RegExp(`^${ipv4Segment}(\\.${ipv4Segment}){3}\\/(3[0-2]|[12]?\\d)$`);

const validateWhitelist = async (_: unknown, value?: string) => {
  const normalized = (value || '').trim();
  if (!normalized) {
    return;
  }

  const invalidItems = normalized
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !ipv4Regex.test(item) && !cidrRegex.test(item));

  if (invalidItems.length > 0) {
    throw new Error(`格式不正确: ${invalidItems.join(', ')}`);
  }
};

const AlertSecuritySettings = () => {
  const [form] = Form.useForm<AlertWebhookSecurityConfigPayload>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadSecurityConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await alertsApi.getSecurityConfig();
      form.setFieldsValue({
        ip_whitelist: config.ipWhitelistText,
        trust_proxy_headers: config.trustProxyHeaders,
      });
    } catch (error) {
      message.error('读取告警安全配置失败');
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    void loadSecurityConfig();
  }, [loadSecurityConfig]);

  const handleSave = async (values: AlertWebhookSecurityConfigPayload) => {
    setSaving(true);
    try {
      await alertsApi.updateSecurityConfig(values);
      message.success('告警白名单配置已保存');
      await loadSecurityConfig();
    } catch (error) {
      message.error('保存告警白名单配置失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <AlertSectionHeader
        title="告警安全配置"
        tag="Security"
        description="集中管理 Alertmanager webhook 的来源访问控制，建议只允许固定出口 IP 或办公网段访问。"
        extra={(
          <Button type="primary" icon={<SafetyOutlined />} onClick={() => void form.submit()} loading={saving}>
            保存配置
          </Button>
        )}
      />
      <Card loading={loading}>
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="Webhook 来源控制"
          description="支持配置单个 IP、多个 IP 或 CIDR 网段，多个值用英文逗号分隔。开启代理头信任后，会优先读取 X-Forwarded-For / X-Real-IP。"
        />
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => {
            void handleSave(values as AlertWebhookSecurityConfigPayload);
          }}
        >
          <Form.Item
            label="IP 白名单"
            name="ip_whitelist"
            extra="支持 IPv4 和 CIDR，多个值请用英文逗号分隔。留空表示不启用白名单限制。"
            rules={[{ validator: validateWhitelist }]}
          >
            <Input.TextArea
              rows={3}
              placeholder="例如：10.10.10.8,10.10.10.9,192.168.1.0/24"
            />
          </Form.Item>
          <Form.Item label="信任代理头" name="trust_proxy_headers" valuePropName="checked">
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default AlertSecuritySettings;
