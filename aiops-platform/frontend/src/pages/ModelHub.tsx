import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Checkbox,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd';
import { ApiOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';

import { llmApi } from '../services/api';
import type {
  BindingFormValues,
  LLMBinding,
  DiscoveredModel,
  LLMModel,
  LLMProvider,
  ModelFormValues,
  ProviderFormValues,
} from '../types';

const providerTypes = [
  { label: 'OpenAI 兼容', value: 'openai_compatible' },
  { label: 'Azure OpenAI', value: 'azure_openai' },
];

const modelTypes = [
  { label: 'Chat', value: 'chat' },
  { label: 'Embedding', value: 'embedding' },
  { label: 'Rerank', value: 'rerank' },
];

const ModelHub = () => {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [bindings, setBindings] = useState<LLMBinding[]>([]);
  const [loading, setLoading] = useState(false);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [modelModalOpen, setModelModalOpen] = useState(false);
  const [bindingModalOpen, setBindingModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [editingBinding, setEditingBinding] = useState<LLMBinding | null>(null);
  const [discoveryModalOpen, setDiscoveryModalOpen] = useState(false);
  const [discoveryProvider, setDiscoveryProvider] = useState<LLMProvider | null>(null);
  const [discoveredModels, setDiscoveredModels] = useState<DiscoveredModel[]>([]);
  const [selectedDiscoveredModels, setSelectedDiscoveredModels] = useState<string[]>([]);
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [providerForm] = Form.useForm<ProviderFormValues>();
  const [modelForm] = Form.useForm<ModelFormValues>();
  const [bindingForm] = Form.useForm<BindingFormValues>();

  const enabledChatModels = useMemo(
    () => models.filter((model) => model.enabled && model.modelType === 'chat'),
    [models]
  );

  const fetchData = async () => {
    setLoading(true);
    try {
      const [providerData, modelData, bindingData] = await Promise.all([
        llmApi.getProviders(),
        llmApi.getModels(),
        llmApi.getBindings(),
      ]);
      setProviders(providerData);
      setModels(modelData);
      setBindings(bindingData.bindings);
    } catch (error) {
      message.error('获取模型配置失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openProviderModal = (provider?: LLMProvider) => {
    setEditingProvider(provider || null);
    providerForm.resetFields();
    if (provider) {
      providerForm.setFieldsValue({
        name: provider.name,
        provider_code: provider.providerCode,
        provider_type: provider.providerType,
        base_url: provider.baseUrl,
        enabled: provider.enabled,
      });
    } else {
      providerForm.setFieldsValue({
        provider_type: 'openai_compatible',
        enabled: true,
      });
    }
    setProviderModalOpen(true);
  };

  const saveProvider = async () => {
    const values = await providerForm.validateFields();
    try {
      if (editingProvider) {
        const payload: Partial<ProviderFormValues> = { ...values };
        delete payload.provider_code;
        if (!payload.api_key) delete payload.api_key;
        await llmApi.updateProvider(editingProvider.id, payload);
      } else {
        await llmApi.createProvider(values);
      }
      message.success('Provider 已保存');
      setProviderModalOpen(false);
      fetchData();
    } catch (error) {
      message.error('保存 Provider 失败');
    }
  };

  const openModelModal = (model?: LLMModel) => {
    setEditingModel(model || null);
    modelForm.resetFields();
    if (model) {
      modelForm.setFieldsValue({
        provider_id: model.providerId,
        model_id: model.modelId,
        display_name: model.displayName,
        model_type: model.modelType,
        supports_function_calling: model.supportsFunctionCalling,
        supports_streaming: model.supportsStreaming,
        supports_json_mode: model.supportsJsonMode,
        context_window: model.contextWindow || undefined,
        max_output_tokens: model.maxOutputTokens || undefined,
        enabled: model.enabled,
        is_default_candidate: model.isDefaultCandidate,
      });
    } else {
      modelForm.setFieldsValue({
        model_type: 'chat',
        supports_streaming: true,
        supports_function_calling: false,
        supports_json_mode: false,
        enabled: true,
        is_default_candidate: true,
      });
    }
    setModelModalOpen(true);
  };

  const saveModel = async () => {
    const values = await modelForm.validateFields();
    try {
      if (editingModel) {
        const payload: Partial<ModelFormValues> = { ...values };
        delete payload.provider_id;
        delete payload.model_id;
        await llmApi.updateModel(editingModel.id, payload);
      } else {
        await llmApi.createModel(values);
      }
      message.success('模型已保存');
      setModelModalOpen(false);
      fetchData();
    } catch (error) {
      message.error('保存模型失败');
    }
  };

  const openBindingModal = (binding: LLMBinding) => {
    setEditingBinding(binding);
    bindingForm.resetFields();
    bindingForm.setFieldsValue({
      model_id: binding.modelId || undefined,
      temperature: binding.temperature ?? 0.2,
      max_tokens: binding.maxTokens || undefined,
      top_p: binding.topP || undefined,
      enabled: binding.enabled,
    });
    setBindingModalOpen(true);
  };

  const saveBinding = async () => {
    if (!editingBinding) return;
    const values = await bindingForm.validateFields();
    try {
      await llmApi.updateBinding(editingBinding.sceneKey, values);
      message.success('场景绑定已保存');
      setBindingModalOpen(false);
      fetchData();
    } catch (error) {
      message.error('保存场景绑定失败');
    }
  };

  const validateProvider = async (provider: LLMProvider) => {
    try {
      const result = await llmApi.validateProvider(provider.id);
      if (result.success) {
        message.success(result.message);
      } else {
        message.error(result.message);
      }
    } catch (error) {
      message.error('连接测试失败');
    }
  };

  const openDiscoveryModal = async (provider: LLMProvider) => {
    try {
      const result = await llmApi.discoverModels(provider.id);
      setDiscoveryProvider(provider);
      setDiscoveredModels(result.models);
      setSelectedDiscoveredModels(result.models.map((item) => item.modelId));
      setOverwriteExisting(false);
      setDiscoveryModalOpen(true);
    } catch (error) {
      message.error('拉取模型列表失败');
    }
  };

  const syncDiscoveredModels = async () => {
    if (!discoveryProvider) return;
    try {
      const result = await llmApi.syncModels(discoveryProvider.id, {
        model_ids: selectedDiscoveredModels,
        overwrite_existing: overwriteExisting,
      });
      message.success(`同步完成：新增 ${result.created}，更新 ${result.updated}，跳过 ${result.skipped}`);
      setDiscoveryModalOpen(false);
      fetchData();
    } catch (error) {
      message.error('同步模型失败');
    }
  };

  const providerColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'providerCode', key: 'providerCode' },
    { title: '类型', dataIndex: 'providerType', key: 'providerType' },
    { title: 'Base URL', dataIndex: 'baseUrl', key: 'baseUrl', ellipsis: true },
    { title: 'API Key', dataIndex: 'apiKeyMasked', key: 'apiKeyMasked' },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => <Tag color={enabled ? 'green' : 'default'}>{enabled ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: LLMProvider) => (
        <Space>
          <Button size="small" onClick={() => validateProvider(record)}>测试</Button>
          <Button size="small" onClick={() => openDiscoveryModal(record)}>同步模型</Button>
          <Button size="small" onClick={() => openProviderModal(record)}>编辑</Button>
          {!record.isBuiltin && (
            <Popconfirm title="确认删除该 Provider？" onConfirm={async () => {
              await llmApi.deleteProvider(record.id);
              message.success('Provider 已删除');
              fetchData();
            }}>
              <Button size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  const modelColumns = [
    { title: '模型', dataIndex: 'displayName', key: 'displayName' },
    { title: '模型 ID', dataIndex: 'modelId', key: 'modelId' },
    { title: 'Provider', dataIndex: 'providerName', key: 'providerName' },
    { title: '类型', dataIndex: 'modelType', key: 'modelType' },
    {
      title: '能力',
      key: 'capabilities',
      render: (_: unknown, record: LLMModel) => (
        <Space>
          {record.supportsFunctionCalling && <Tag color="blue">Tools</Tag>}
          {record.supportsStreaming && <Tag color="green">Streaming</Tag>}
          {record.supportsJsonMode && <Tag color="purple">JSON</Tag>}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => <Tag color={enabled ? 'green' : 'default'}>{enabled ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: LLMModel) => (
        <Space>
          <Button size="small" onClick={() => openModelModal(record)}>编辑</Button>
          <Popconfirm title="确认删除该模型？" onConfirm={async () => {
            await llmApi.deleteModel(record.id);
            message.success('模型已删除');
            fetchData();
          }}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const bindingColumns = [
    { title: '场景', dataIndex: 'displayName', key: 'displayName' },
    { title: '场景 Key', dataIndex: 'sceneKey', key: 'sceneKey' },
    { title: 'Provider', dataIndex: 'providerName', key: 'providerName' },
    { title: '模型', dataIndex: 'modelName', key: 'modelName' },
    { title: '温度', dataIndex: 'temperature', key: 'temperature' },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (source: string) => <Tag color={source === 'database' ? 'green' : 'orange'}>{source}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: LLMBinding) => (
        <Button size="small" onClick={() => openBindingModal(record)}>绑定模型</Button>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={<Space><ApiOutlined />平台模型管理</Space>}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          </Space>
        }
      >
        <Tabs
          items={[
            {
              key: 'providers',
              label: 'Provider 管理',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => openProviderModal()}>新增 Provider</Button>
                  <Table columns={providerColumns} dataSource={providers} rowKey="id" loading={loading} />
                </Space>
              ),
            },
            {
              key: 'models',
              label: '模型管理',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => openModelModal()}>新增模型</Button>
                  <Table columns={modelColumns} dataSource={models} rowKey="id" loading={loading} />
                </Space>
              ),
            },
            {
              key: 'bindings',
              label: '场景绑定',
              children: <Table columns={bindingColumns} dataSource={bindings} rowKey="sceneKey" loading={loading} />,
            },
          ]}
        />
      </Card>

      <Modal
        title={editingProvider ? '编辑 Provider' : '新增 Provider'}
        open={providerModalOpen}
        onCancel={() => setProviderModalOpen(false)}
        onOk={saveProvider}
        destroyOnClose
      >
        <Form form={providerForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="DashScope" />
          </Form.Item>
          <Form.Item name="provider_code" label="唯一编码" rules={[{ required: true }]}>
            <Input disabled={!!editingProvider} placeholder="dashscope" />
          </Form.Item>
          <Form.Item name="provider_type" label="Provider 类型" rules={[{ required: true }]}>
            <Select options={providerTypes} />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true }]}>
            <Input placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </Form.Item>
          <Form.Item
            name="api_key"
            label={editingProvider ? 'API Key（留空表示不变）' : 'API Key'}
            rules={editingProvider ? [] : [{ required: true }]}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingModel ? '编辑模型' : '新增模型'}
        open={modelModalOpen}
        onCancel={() => setModelModalOpen(false)}
        onOk={saveModel}
        destroyOnClose
      >
        <Form form={modelForm} layout="vertical">
          <Form.Item name="provider_id" label="Provider" rules={[{ required: true }]}>
            <Select
              disabled={!!editingModel}
              options={providers.map((provider) => ({ label: provider.name, value: provider.id }))}
            />
          </Form.Item>
          <Form.Item name="model_id" label="模型 ID" rules={[{ required: true }]}>
            <Input disabled={!!editingModel} placeholder="qwen-plus" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="model_type" label="模型类型" rules={[{ required: true }]}>
            <Select options={modelTypes} />
          </Form.Item>
          <Form.Item name="context_window" label="上下文窗口">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_output_tokens" label="最大输出 Tokens">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Space>
            <Form.Item name="supports_function_calling" label="Tools" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="supports_streaming" label="Streaming" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="supports_json_mode" label="JSON Mode" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item name="is_default_candidate" label="可作为默认模型" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`绑定模型：${editingBinding?.displayName || ''}`}
        open={bindingModalOpen}
        onCancel={() => setBindingModalOpen(false)}
        onOk={saveBinding}
        destroyOnClose
      >
        <Form form={bindingForm} layout="vertical">
          <Form.Item name="model_id" label="模型" rules={[{ required: true }]}>
            <Select
              options={enabledChatModels.map((model) => ({
                label: `${model.providerName} / ${model.displayName}`,
                value: model.id,
              }))}
            />
          </Form.Item>
          <Form.Item name="temperature" label="Temperature">
            <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_tokens" label="Max Tokens">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="top_p" label="Top P">
            <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="enabled" label="启用绑定" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`从 Provider 拉取模型：${discoveryProvider?.name || ''}`}
        open={discoveryModalOpen}
        onCancel={() => setDiscoveryModalOpen(false)}
        onOk={syncDiscoveredModels}
        width={720}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Checkbox
            checked={overwriteExisting}
            onChange={(event) => setOverwriteExisting(event.target.checked)}
          >
            覆盖已存在模型的展示信息
          </Checkbox>
          <Table
            rowKey="modelId"
            pagination={{ pageSize: 8 }}
            rowSelection={{
              selectedRowKeys: selectedDiscoveredModels,
              onChange: (selectedRowKeys) => setSelectedDiscoveredModels(selectedRowKeys as string[]),
            }}
            dataSource={discoveredModels}
            columns={[
              { title: '模型 ID', dataIndex: 'modelId', key: 'modelId' },
              { title: '显示名', dataIndex: 'displayName', key: 'displayName' },
              { title: '类型', dataIndex: 'modelType', key: 'modelType' },
              {
                title: '状态',
                key: 'status',
                render: (_: unknown, record: DiscoveredModel) => (
                  <Space>
                    {record.alreadyImported && <Tag color="blue">已导入</Tag>}
                    {record.supportsFunctionCalling && <Tag color="green">Tools</Tag>}
                  </Space>
                ),
              },
            ]}
          />
        </Space>
      </Modal>
    </div>
  );
};

export default ModelHub;
