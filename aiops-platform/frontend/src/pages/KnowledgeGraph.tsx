import { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, List, Tag, message, Typography, Space, Divider, Tabs, Row, Col, Statistic, Alert, Form, Select, InputNumber, Switch, Upload, Modal, Popconfirm } from 'antd';
import { SearchOutlined, ApiOutlined, BookOutlined, ApartmentOutlined, ClockCircleOutlined, WarningOutlined, EditOutlined, SettingOutlined, UploadOutlined, InboxOutlined, FullscreenOutlined, DeleteOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';

import { knowledgeApi, observabilityRuntimeApi } from '../services/api';
import type { RuntimeTopologySnapshot, RuntimeGraphConfigPayload } from '../types';
import { useAuth } from '../contexts/AuthContext';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const NODE_TYPE_OPTIONS = ['Service', 'Server', 'Database', 'Cache', 'MQ', 'Gateway', 'Cluster', 'Namespace', 'Application', 'Middleware'];
const RELATION_TYPE_OPTIONS = ['DEPENDS_ON', 'RUNS_ON', 'CONNECTED_TO', 'CALLS', 'BELONGS_TO', 'USES_DB', 'USES_CACHE', 'USES_MQ'];
const TOPOLOGY_CATEGORIES = ['Server', 'Database', 'Service', 'Network', 'Infra'];

const getApiErrorMessage = (error: unknown, fallback: string) => {
  const response = (error as { response?: { data?: { detail?: string; message?: string } } }).response;
  return response?.data?.detail || response?.data?.message || fallback;
};

const looksLikeServiceName = (value: string) => /^[A-Za-z][A-Za-z0-9_-]{2,}$/.test(value);

interface KGNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

interface KGEdge {
  id?: string;
  source: string;
  target: string;
  type: string;
  properties?: Record<string, unknown>;
}

interface RAGDocument {
  content?: string;
  source?: string;
  page?: number;
  summary?: string;
  score?: number;
  rerank_score?: number;
  combined_score?: number;
}

interface RAGResult {
  answer: string;
  source: string;
  documents: RAGDocument[];
  best_score: number;
  use_context: boolean;
  mode: string;
}

interface KGResult {
  service?: string;
  properties?: Record<string, string | number>;
  dependencies?: Array<{ name: string; type: string }>;
  servers?: Array<{ name: string; ip: string }>;
  databases?: Array<{ name: string; type: string }>;
  matched_nodes?: Array<{ type: string; name: string; properties: Record<string, unknown> }>;
}

interface KGQueryResult {
  query: string;
  result?: KGResult;
  source: string;
  error?: string;
}

const KnowledgeGraph = () => {
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('kg');
  const [searchInput, setSearchInput] = useState('');
  const [ragInput, setRagInput] = useState('');
  const [runtimeInput, setRuntimeInput] = useState('order-service');
  const [loading, setLoading] = useState(false);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [savingRuntimeConfig, setSavingRuntimeConfig] = useState(false);
  const [submittingManualEntry, setSubmittingManualEntry] = useState(false);
  const [importingGraphData, setImportingGraphData] = useState(false);
  const [editingNode, setEditingNode] = useState<KGNode | null>(null);
  const [editingRelation, setEditingRelation] = useState<KGEdge | null>(null);
  const [savingNode, setSavingNode] = useState(false);
  const [savingRelation, setSavingRelation] = useState(false);
  const [kgResult, setKgResult] = useState<KGQueryResult | null>(null);
  const [ragResult, setRagResult] = useState<RAGResult | null>(null);
  const [topologyData, setTopologyData] = useState<{ nodes: KGNode[]; edges: KGEdge[] } | null>(null);
  const [topologyLoaded, setTopologyLoaded] = useState(false);
  const [topologyFullscreenOpen, setTopologyFullscreenOpen] = useState(false);
  const [runtimeTopology, setRuntimeTopology] = useState<RuntimeTopologySnapshot | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const fullscreenChartRef = useRef<HTMLDivElement>(null);
  const fullscreenChartInstance = useRef<echarts.ECharts | null>(null);
  const runtimeChartRef = useRef<HTMLDivElement>(null);
  const runtimeChartInstance = useRef<echarts.ECharts | null>(null);
  const [runtimeConfigForm] = Form.useForm();
  const [manualEntryForm] = Form.useForm();
  const [nodeEditForm] = Form.useForm();
  const [relationEditForm] = Form.useForm();

  const handleSearchKG = async (keyword?: string) => {
    const query = (keyword ?? searchInput).trim();
    if (!query) {
      message.warning('请输入服务名称或查询语句');
      return;
    }

    setLoading(true);
    try {
      const response = await knowledgeApi.queryKG(undefined, query);
      setKgResult(response as KGQueryResult);

      if (looksLikeServiceName(query)) {
        const topology = await knowledgeApi.getTopology(query, 1);
        setTopologyData(topology as { nodes: KGNode[]; edges: KGEdge[] });
      } else {
        setTopologyData(null);
      }
    } catch (error) {
      message.error('查询失败');
    } finally {
      setLoading(false);
    }
  };

  const loadExistingTopology = async () => {
    setLoading(true);
    try {
      const topology = await knowledgeApi.getTopology(undefined, 2);
      setTopologyData(topology as { nodes: KGNode[]; edges: KGEdge[] });
      setTopologyLoaded(true);
    } catch (error) {
      message.error('加载已有图谱数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRAGQuery = async (question?: string) => {
    const query = (question ?? ragInput).trim();
    if (!query) {
      message.warning('请输入问题');
      return;
    }

    setLoading(true);
    try {
      const response = await knowledgeApi.queryRAG(query);
      setRagResult(response as RAGResult);
    } catch (error) {
      message.error('RAG 查询失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRuntimeTopologyQuery = async (serviceName?: string) => {
    const service = (serviceName ?? runtimeInput).trim();
    if (!service) {
      message.warning('请输入服务名');
      return;
    }

    setRuntimeLoading(true);
    try {
      const response = await observabilityRuntimeApi.getTopology(service, 15);
      setRuntimeTopology(response);
    } catch (error) {
      message.error('查询运行时拓扑失败，请确认 Jaeger 已接入且服务名正确');
      setRuntimeTopology(null);
    } finally {
      setRuntimeLoading(false);
    }
  };

  const loadRuntimeGraphConfig = async () => {
    try {
      const config = await knowledgeApi.getRuntimeGraphConfig();
      runtimeConfigForm.setFieldsValue({
        trace_backend: config.traceBackend,
        jaeger_query_url: config.jaegerQueryUrl,
        tempo_query_url: config.tempoQueryUrl,
        trace_query_timeout: config.traceQueryTimeout,
        trace_default_lookback_minutes: config.traceDefaultLookbackMinutes,
        runtime_graph_enabled: config.runtimeGraphEnabled,
        service_list_text: (config.serviceList || []).join('\n'),
      });
    } catch (error) {
      console.error('加载运行时配置失败', error);
    }
  };

  const handleSaveRuntimeConfig = async (values: Record<string, unknown>) => {
    const payload: RuntimeGraphConfigPayload = {
      trace_backend: String(values.trace_backend || 'jaeger'),
      jaeger_query_url: String(values.jaeger_query_url || ''),
      tempo_query_url: String(values.tempo_query_url || ''),
      trace_query_timeout: Number(values.trace_query_timeout || 15),
      trace_default_lookback_minutes: Number(values.trace_default_lookback_minutes || 15),
      runtime_graph_enabled: Boolean(values.runtime_graph_enabled),
      service_list: String(values.service_list_text || '')
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
    };

    setSavingRuntimeConfig(true);
    try {
      await knowledgeApi.updateRuntimeGraphConfig(payload);
      message.success('运行时拓扑配置已保存');
      await loadRuntimeGraphConfig();
    } catch (error) {
      message.error('保存运行时拓扑配置失败');
    } finally {
      setSavingRuntimeConfig(false);
    }
  };

  const handleCreateManualEntry = async (values: Record<string, unknown>) => {
    const sourceProperties: Record<string, unknown> = {};
    if (values.source_description) sourceProperties.description = values.source_description;
    if (values.source_ip) sourceProperties.ip = values.source_ip;
    if (values.source_owner) sourceProperties.owner = values.source_owner;
    if (values.source_environment) sourceProperties.environment = values.source_environment;

    const relationEnabled = Boolean(values.relation_enabled);
    const targetProperties: Record<string, unknown> = {};
    if (values.target_description) targetProperties.description = values.target_description;
    if (values.target_ip) targetProperties.ip = values.target_ip;

    setSubmittingManualEntry(true);
    try {
      await knowledgeApi.createManualEntry({
        source_type: String(values.source_type),
        source_name: String(values.source_name),
        source_properties: sourceProperties,
        relation: relationEnabled
          ? {
              target_type: String(values.target_type),
              target_name: String(values.target_name),
              relation_type: String(values.relation_type),
              target_properties: targetProperties,
            }
          : null,
      });
      message.success('知识图谱录入成功');
      manualEntryForm.resetFields();
    } catch (error) {
      message.error('知识图谱录入失败');
    } finally {
      setSubmittingManualEntry(false);
    }
  };

  const handleImportGraphData = async (file: File) => {
    setImportingGraphData(true);
    try {
      const result = await knowledgeApi.importGraphData(file);
      if (result.failed && result.failed > 0) {
        message.warning(`部分导入成功：${result.nodes} 个节点，${result.relations} 条关系，失败 ${result.failed} 条`);
      } else {
        message.success(`导入成功：${result.nodes} 个节点，${result.relations} 条关系`);
      }
    } catch (error) {
      message.error(getApiErrorMessage(error, '导入图谱数据失败'));
    } finally {
      setImportingGraphData(false);
    }
    return false;
  };

  const openNodeEditModal = (node: KGNode) => {
    setEditingNode(node);
    nodeEditForm.setFieldsValue({
      name: node.label,
      propertiesText: JSON.stringify(node.properties || {}, null, 2),
    });
  };

  const openRelationEditModal = (relation: KGEdge) => {
    setEditingRelation(relation);
    relationEditForm.setFieldsValue({
      relation_type: relation.type,
      propertiesText: JSON.stringify(relation.properties || {}, null, 2),
    });
  };

  const handleSaveNodeEdit = async (values: Record<string, unknown>) => {
    if (!editingNode) return;
    setSavingNode(true);
    try {
      const properties = JSON.parse(String(values.propertiesText || '{}')) as Record<string, unknown>;
      await knowledgeApi.updateGraphNode(editingNode.id, {
        name: String(values.name || '').trim(),
        properties,
      });
      message.success('节点更新成功');
      setEditingNode(null);
      nodeEditForm.resetFields();
      await loadExistingTopology();
    } catch (error) {
      message.error(getApiErrorMessage(error, '节点更新失败'));
    } finally {
      setSavingNode(false);
    }
  };

  const handleDeleteNode = async (node: KGNode) => {
    try {
      await knowledgeApi.deleteGraphNode(node.id);
      message.success('节点删除成功');
      await loadExistingTopology();
    } catch (error) {
      message.error(getApiErrorMessage(error, '节点删除失败'));
    }
  };

  const handleSaveRelationEdit = async (values: Record<string, unknown>) => {
    if (!editingRelation?.id) return;
    setSavingRelation(true);
    try {
      const properties = JSON.parse(String(values.propertiesText || '{}')) as Record<string, unknown>;
      await knowledgeApi.updateGraphRelation(editingRelation.id, {
        relation_type: String(values.relation_type || '').trim(),
        properties,
      });
      message.success('关系更新成功');
      setEditingRelation(null);
      relationEditForm.resetFields();
      await loadExistingTopology();
    } catch (error) {
      message.error(getApiErrorMessage(error, '关系更新失败'));
    } finally {
      setSavingRelation(false);
    }
  };

  const handleDeleteRelation = async (relation: KGEdge) => {
    if (!relation.id) return;
    try {
      await knowledgeApi.deleteGraphRelation(relation.id);
      message.success('关系删除成功');
      await loadExistingTopology();
    } catch (error) {
      message.error(getApiErrorMessage(error, '关系删除失败'));
    }
  };

  useEffect(() => {
    if (chartRef.current && topologyData) {
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current);
      }

      const nodes = topologyData.nodes.map((node) => ({
        id: node.id,
        name: node.label,
        symbolSize: 50,
        category: getNodeCategory(node.type),
        itemStyle: {
          color: getNodeColor(node.type),
        },
        label: {
          show: true,
          fontSize: 12,
        },
      }));

      const nodeIds = new Set(nodes.map((node) => node.id));
      const links = topologyData.edges
        .filter((edge) => edge.source && edge.target && nodeIds.has(edge.source) && nodeIds.has(edge.target))
        .map((edge) => ({
          source: edge.source,
          target: edge.target,
          value: edge.type,
          lineStyle: {
            curveness: 0.2,
          },
          label: {
            show: true,
            formatter: edge.type,
            fontSize: 10,
          },
        }));

      chartInstance.current.clear();
      const option = {
        title: {
          text: '架构拓扑图',
          left: 'center',
        },
        tooltip: {
          trigger: 'item',
          formatter: (params: { dataType: string; data: { name?: string; value?: string } }) => {
            if (params.dataType === 'node') {
              return `节点: ${params.data.name}`;
            }
            return `${params.data.value}`;
          },
        },
        legend: {
          data: TOPOLOGY_CATEGORIES,
          top: 30,
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            data: nodes,
            links,
            categories: TOPOLOGY_CATEGORIES.map((name) => ({ name })),
            roam: true,
            label: {
              show: true,
              position: 'right',
            },
            force: {
              repulsion: 200,
              edgeLength: 120,
            },
            emphasis: {
              focus: 'adjacency',
              lineStyle: {
                width: 3,
              },
            },
          },
        ],
      };

      chartInstance.current.setOption(option);
      setTimeout(() => {
        chartInstance.current?.resize();
      }, 0);
    }
  }, [topologyData]);

  useEffect(() => {
    if (fullscreenChartRef.current && topologyData && topologyFullscreenOpen) {
      if (!fullscreenChartInstance.current) {
        fullscreenChartInstance.current = echarts.init(fullscreenChartRef.current);
      }

      const nodes = topologyData.nodes.map((node) => ({
        id: node.id,
        name: node.label,
        symbolSize: 62,
        category: getNodeCategory(node.type),
        itemStyle: {
          color: getNodeColor(node.type),
        },
        label: {
          show: true,
          fontSize: 13,
        },
      }));

      const nodeIds = new Set(nodes.map((node) => node.id));
      const links = topologyData.edges
        .filter((edge) => edge.source && edge.target && nodeIds.has(edge.source) && nodeIds.has(edge.target))
        .map((edge) => ({
          source: edge.source,
          target: edge.target,
          value: edge.type,
          lineStyle: {
            curveness: 0.18,
          },
          label: {
            show: true,
            formatter: edge.type,
            fontSize: 11,
          },
        }));

      fullscreenChartInstance.current.clear();
      fullscreenChartInstance.current.setOption({
        title: {
          text: '架构拓扑图',
          left: 'center',
        },
        tooltip: {
          trigger: 'item',
          formatter: (params: { dataType: string; data: { name?: string; value?: string } }) => {
            if (params.dataType === 'node') {
              return `节点: ${params.data.name}`;
            }
            return `${params.data.value}`;
          },
        },
        legend: {
          data: TOPOLOGY_CATEGORIES,
          top: 30,
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            data: nodes,
            links,
            categories: TOPOLOGY_CATEGORIES.map((name) => ({ name })),
            roam: true,
            draggable: true,
            label: {
              show: true,
              position: 'right',
            },
            force: {
              repulsion: 420,
              edgeLength: 180,
            },
            emphasis: {
              focus: 'adjacency',
            },
          },
        ],
      });
      setTimeout(() => {
        fullscreenChartInstance.current?.resize();
      }, 0);
    }
  }, [topologyData, topologyFullscreenOpen]);

  useEffect(() => {
    const handleResize = () => {
      chartInstance.current?.resize();
      fullscreenChartInstance.current?.resize();
      runtimeChartInstance.current?.resize();
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (isAdmin) {
      void loadRuntimeGraphConfig();
    }
  }, [isAdmin]);

  useEffect(() => {
    if (runtimeChartRef.current && runtimeTopology) {
      if (!runtimeChartInstance.current) {
        runtimeChartInstance.current = echarts.init(runtimeChartRef.current);
      }

      const centerNode = {
        id: runtimeTopology.service,
        name: runtimeTopology.service,
        symbolSize: 68,
        itemStyle: { color: '#1677ff' },
        label: { show: true, fontSize: 13, fontWeight: 600 },
      };

      const upstreamNodes = runtimeTopology.upstream.map((dependency) => ({
        id: `upstream-${dependency.source_service}`,
        name: dependency.source_service,
        symbolSize: 52,
        itemStyle: { color: '#52c41a' },
        label: { show: true, fontSize: 12 },
      }));

      const downstreamNodes = runtimeTopology.downstream.map((dependency) => ({
        id: `downstream-${dependency.target_service}`,
        name: dependency.target_service,
        symbolSize: 52,
        itemStyle: { color: '#faad14' },
        label: { show: true, fontSize: 12 },
      }));

      const anomalyNodes = runtimeTopology.anomalies.slice(0, 5).map((anomaly, index) => ({
        id: `anomaly-${index}-${anomaly.span_name}`,
        name: `${anomaly.span_name}`,
        symbolSize: 42,
        itemStyle: { color: '#ff4d4f' },
        label: { show: true, fontSize: 11 },
      }));

      const links = [
        ...runtimeTopology.upstream.map((dependency) => ({
          source: `upstream-${dependency.source_service}`,
          target: runtimeTopology.service,
          value: `调用 ${dependency.call_count} 次`,
          lineStyle: { color: '#52c41a', curveness: 0.12 },
          label: { show: true, formatter: `${dependency.avg_latency_ms.toFixed(0)}ms`, fontSize: 10 },
        })),
        ...runtimeTopology.downstream.map((dependency) => ({
          source: runtimeTopology.service,
          target: `downstream-${dependency.target_service}`,
          value: dependency.dependency_type,
          lineStyle: { color: '#faad14', curveness: 0.12 },
          label: { show: true, formatter: `${dependency.avg_latency_ms.toFixed(0)}ms`, fontSize: 10 },
        })),
        ...runtimeTopology.anomalies.slice(0, 5).map((anomaly, index) => ({
          source: runtimeTopology.service,
          target: `anomaly-${index}-${anomaly.span_name}`,
          value: anomaly.anomaly_type,
          lineStyle: { color: '#ff4d4f', type: 'dashed', curveness: 0.25 },
          label: { show: true, formatter: `${anomaly.duration_ms.toFixed(0)}ms`, fontSize: 10 },
        })),
      ];

      runtimeChartInstance.current.clear();
      runtimeChartInstance.current.setOption({
        title: {
          text: `运行时拓扑 · ${runtimeTopology.service}`,
          left: 'center',
        },
        tooltip: {
          trigger: 'item',
          formatter: (params: { dataType: string; data: { name?: string; value?: string } }) =>
            params.dataType === 'node' ? `节点: ${params.data.name}` : `${params.data.value || ''}`,
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            data: [centerNode, ...upstreamNodes, ...downstreamNodes, ...anomalyNodes],
            links,
            label: { position: 'right' },
            force: {
              repulsion: 260,
              edgeLength: 140,
            },
            emphasis: {
              focus: 'adjacency',
            },
          },
        ],
      });
      setTimeout(() => {
        runtimeChartInstance.current?.resize();
      }, 0);
    }
  }, [runtimeTopology]);

  const getNodeCategory = (type: string): string => {
    const categories: Record<string, string> = {
      Server: 'Server',
      Database: 'Database',
      Service: 'Service',
      NetworkDevice: 'Network',
      Infra: 'Infra',
    };
    return categories[type] || 'Infra';
  };

  const getNodeColor = (type: string): string => {
    const colors: Record<string, string> = {
      Server: '#5470c6',
      Database: '#91cc75',
      Service: '#fac858',
      NetworkDevice: '#ee6666',
      Infra: '#73c0de',
    };
    return colors[type] || '#73c0de';
  };

  const getTopologyNodeLabel = (nodeId?: string): string => {
    if (!nodeId) return 'unknown';
    return topologyData?.nodes.find((node) => node.id === nodeId)?.label || nodeId;
  };

  const renderKGResult = () => {
    if (!kgResult) return null;

    const result = kgResult.result;

    return (
      <Card title="知识图谱查询结果" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>查询: </Text>
            <Text>{kgResult.query}</Text>
          </div>
          
          {result?.service && (
            <div>
              <Text strong>服务: </Text>
              <Tag color="blue">{result.service}</Tag>
            </div>
          )}

          {result?.properties && (
            <div>
              <Text strong>属性:</Text>
              <div style={{ marginTop: 8 }}>
                {Object.entries(result.properties).map(([key, value]) => (
                  <Tag key={key} style={{ margin: 4 }}>
                    {key}: {String(value)}
                  </Tag>
                ))}
              </div>
            </div>
          )}

          {result?.dependencies && result.dependencies.length > 0 && (
            <div>
              <Text strong>依赖关系:</Text>
              <List
                size="small"
                dataSource={result.dependencies}
                renderItem={(item) => (
                  <List.Item>
                    <Tag color="green">{item.type}</Tag> {item.name}
                  </List.Item>
                )}
              />
            </div>
          )}

          {result?.servers && (
            <div>
              <Text strong>服务器列表:</Text>
              <List
                size="small"
                dataSource={result.servers}
                renderItem={(item) => (
                  <List.Item>
                    {item.name} - {item.ip}
                  </List.Item>
                )}
              />
            </div>
          )}

          {result?.databases && (
            <div>
              <Text strong>数据库列表:</Text>
              <List
                size="small"
                dataSource={result.databases}
                renderItem={(item) => (
                  <List.Item>
                    {item.name} {item.type && `(${item.type})`}
                  </List.Item>
                )}
              />
            </div>
          )}
        </Space>
      </Card>
    );
  };

  return (
    <div>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key)}
      >
        <TabPane
          tab={
            <span>
              <ApiOutlined />
              知识图谱
            </span>
          }
          key="kg"
        >
          <Card
            title="查询知识图谱"
            extra={
              <Button
                size="small"
                onClick={() => {
                  void loadExistingTopology();
                }}
                loading={loading}
              >
                {topologyLoaded ? '刷新已有图谱' : '加载已有图谱'}
              </Button>
            }
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="默认不自动加载全量图谱"
              description="为降低 Neo4j CPU 压力，页面进入后不再自动查询全图。点击右上角按钮后，仅加载一份抽样拓扑；输入服务名查询时仍会加载对应服务的局部拓扑。"
            />
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入服务名称 (如: prod-server-01) 或查询语句 (如: 查询所有服务器)"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onPressEnter={() => {
                  void handleSearchKG();
                }}
              />
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={() => {
                  void handleSearchKG();
                }}
                loading={loading}
              >
                查询
              </Button>
            </Space.Compact>

            <div style={{ marginTop: 16 }}>
              <Text type="secondary">快速查询:</Text>
              <Space style={{ marginLeft: 8 }} wrap>
                <Button size="small" onClick={() => { const value = 'prod-server-01'; setSearchInput(value); handleSearchKG(value); }}>
                  prod-server-01
                </Button>
                <Button size="small" onClick={() => { const value = '查询所有服务器'; setSearchInput(value); handleSearchKG(value); }}>
                  所有服务器
                </Button>
                <Button size="small" onClick={() => { const value = '查询所有数据库'; setSearchInput(value); handleSearchKG(value); }}>
                  所有数据库
                </Button>
              </Space>
            </div>
          </Card>

          {renderKGResult()}

          {!topologyLoaded && !topologyData && (
            <Card style={{ marginTop: 16 }}>
              <Text type="secondary">尚未加载拓扑概览。点击右上角“加载已有图谱”，或直接输入服务名查询局部拓扑。</Text>
            </Card>
          )}

          {topologyData && topologyData.nodes.length > 0 && (
            <>
              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={12}>
                  <Card>
                    <Statistic title="节点数量" value={topologyData.nodes.length} prefix={<ApiOutlined />} />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card>
                    <Statistic title="关系数量" value={topologyData.edges.length} prefix={<ApartmentOutlined />} />
                  </Card>
                </Col>
              </Row>
              <Card
                title="拓扑可视化"
                style={{ marginTop: 16 }}
                extra={
                  <Button
                    type="text"
                    icon={<FullscreenOutlined />}
                    onClick={() => setTopologyFullscreenOpen(true)}
                  >
                    最大化
                  </Button>
                }
              >
                <div ref={chartRef} style={{ width: '100%', height: 400 }} />
              </Card>
              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={12}>
                  <Card title="节点列表">
                    <List
                      size="small"
                      dataSource={topologyData.nodes}
                      pagination={{ pageSize: 8 }}
                      renderItem={(node) => (
                        <List.Item>
                          <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                            <Space wrap>
                              <Tag color="blue">{node.type}</Tag>
                              <Text>{node.label}</Text>
                            </Space>
                            {isAdmin && (
                              <Space size={4}>
                                <Button size="small" icon={<EditOutlined />} onClick={() => openNodeEditModal(node)}>
                                  编辑
                                </Button>
                                <Popconfirm
                                  title="确认删除该节点？"
                                  description="删除节点会同时删除与其相关的所有关系。"
                                  onConfirm={() => {
                                    void handleDeleteNode(node);
                                  }}
                                >
                                  <Button size="small" danger icon={<DeleteOutlined />}>
                                    删除
                                  </Button>
                                </Popconfirm>
                              </Space>
                            )}
                          </div>
                        </List.Item>
                      )}
                    />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="关系列表">
                    <List
                      size="small"
                      dataSource={topologyData.edges}
                      pagination={{ pageSize: 8 }}
                      renderItem={(edge) => (
                        <List.Item>
                          <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                            <Space wrap>
                              <Tag color="green">{edge.type}</Tag>
                              <Text type="secondary">{getTopologyNodeLabel(edge.source)} → {getTopologyNodeLabel(edge.target)}</Text>
                            </Space>
                            {isAdmin && edge.id && (
                              <Space size={4}>
                                <Button size="small" icon={<EditOutlined />} onClick={() => openRelationEditModal(edge)}>
                                  编辑
                                </Button>
                                <Popconfirm
                                  title="确认删除该关系？"
                                  onConfirm={() => {
                                    void handleDeleteRelation(edge);
                                  }}
                                >
                                  <Button size="small" danger icon={<DeleteOutlined />}>
                                    删除
                                  </Button>
                                </Popconfirm>
                              </Space>
                            )}
                          </div>
                        </List.Item>
                      )}
                    />
                  </Card>
                </Col>
              </Row>
            </>
          )}

          {topologyLoaded && (!topologyData || topologyData.nodes.length === 0) && (
            <Card style={{ marginTop: 16 }}>
              <Text type="secondary">当前 Neo4j 中暂未查询到图谱关系数据，可以通过“录入数据”或“导入数据”添加。</Text>
            </Card>
          )}
        </TabPane>

        <TabPane
          tab={
            <span>
              <BookOutlined />
              RAG 知识库
            </span>
          }
          key="rag"
        >
          <Card title="RAG 知识库问答">
            <Space direction="vertical" style={{ width: '100%' }}>
              <TextArea
                placeholder="输入你的运维问题，如：数据库连接池耗尽怎么处理？"
                value={ragInput}
                onChange={(e) => setRagInput(e.target.value)}
                autoSize={{ minRows: 3, maxRows: 6 }}
              />
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={() => {
                  void handleRAGQuery();
                }}
                loading={loading}
              >
                查询知识库
              </Button>
            </Space>

            <div style={{ marginTop: 16 }}>
              <Text type="secondary">示例问题:</Text>
              <Space style={{ marginLeft: 8 }} wrap>
                <Button size="small" onClick={() => { const value = '数据库连接池耗尽怎么处理'; setRagInput(value); handleRAGQuery(value); }}>
                  数据库连接池耗尽
                </Button>
                <Button size="small" onClick={() => { const value = '如何处理服务超时问题'; setRagInput(value); handleRAGQuery(value); }}>
                  服务超时处理
                </Button>
                <Button size="small" onClick={() => { const value = 'Redis 主从切换的影响'; setRagInput(value); handleRAGQuery(value); }}>
                  Redis 主从切换
                </Button>
              </Space>
            </div>
          </Card>

          {ragResult && (
            <Card title="RAG 回答" style={{ marginTop: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Space wrap>
                    <Tag color={ragResult.source === 'ops_rag_service' ? 'green' : 'orange'}>
                      来源: {ragResult.source}
                    </Tag>
                    <Tag color={ragResult.mode === 'RAG' ? 'blue' : 'purple'}>
                      模式: {ragResult.mode}
                    </Tag>
                    <Tag color={ragResult.use_context ? 'cyan' : 'red'}>
                      {ragResult.use_context ? '已使用知识库上下文' : '未命中知识库 (通用回答)'}
                    </Tag>
                    <Tag color={ragResult.best_score >= 0.5 ? 'green' : 'orange'}>
                      相似度: {(ragResult.best_score * 100).toFixed(1)}%
                    </Tag>
                  </Space>
                </div>
                <Divider />
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                  {ragResult.answer}
                </Paragraph>
                
                {ragResult.documents && ragResult.documents.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ marginBottom: 8, fontWeight: 500 }}>
                      📖 引用来源
                    </div>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {ragResult.documents.map((doc, index) => {
                        const score = doc.score || doc.rerank_score || doc.combined_score || 0;
                        const scoreColor = score >= 0.7 ? '🟢' : score >= 0.5 ? '🟡' : '🔴';
                        return (
                          <div 
                            key={index}
                            style={{ 
                              padding: '8px 12px', 
                              background: '#f5f5f5', 
                              borderRadius: 6,
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8
                            }}
                          >
                            <span style={{ fontWeight: 500 }}>
                              {doc.source || `文档 ${index + 1}`}
                            </span>
                            <span>{scoreColor}</span>
                            <span style={{ color: '#666', fontSize: 12 }}>
                              (相似度: {score.toFixed(2)})
                            </span>
                            {doc.page && (
                              <Tag style={{ marginLeft: 4 }}>页码: {doc.page}</Tag>
                            )}
                          </div>
                        );
                      })}
                    </Space>
                  </div>
                )}
                
                {(!ragResult.documents || ragResult.documents.length === 0) && ragResult.use_context && (
                  <div style={{ marginTop: 16, padding: 12, background: '#f0f5ff', borderRadius: 4 }}>
                    <Text type="secondary">
                      📝 该回答基于通用知识生成，未引用特定文档
                    </Text>
                  </div>
                )}
                
                {!ragResult.use_context && (
                  <div style={{ marginTop: 16, padding: 12, background: '#fff7e6', borderRadius: 4 }}>
                    <Text type="warning">
                      ⚠️ 该回答未经过知识库验证，仅供参考。请尝试使用更具体的关键词查询，或联系管理员添加相关文档。
                    </Text>
                  </div>
                )}
              </Space>
            </Card>
          )}
        </TabPane>

        <TabPane
          tab={
            <span>
              <ApartmentOutlined />
              运行时拓扑
            </span>
          }
          key="runtime"
        >
          <Card title="运行时依赖与异常拓扑">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Alert
                type="info"
                showIcon
                description="这里展示的是最近时间窗口内的真实运行时调用关系、异常 Span 和延迟特征，可与知识图谱形成互补。"
              />
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  placeholder="输入服务名，例如 order-service"
                  value={runtimeInput}
                  onChange={(e) => setRuntimeInput(e.target.value)}
                  onPressEnter={() => {
                    void handleRuntimeTopologyQuery();
                  }}
                />
                <Button
                  type="primary"
                  icon={<SearchOutlined />}
                  onClick={() => {
                    void handleRuntimeTopologyQuery();
                  }}
                  loading={runtimeLoading}
                >
                  查询运行时拓扑
                </Button>
              </Space.Compact>
              <div>
                <Text type="secondary">推荐服务:</Text>
                <Space style={{ marginLeft: 8 }} wrap>
                  {['order-service', 'payment-service', 'user-service', 'inventory-service'].map((service) => (
                    <Button key={service} size="small" onClick={() => { setRuntimeInput(service); handleRuntimeTopologyQuery(service); }}>
                      {service}
                    </Button>
                  ))}
                </Space>
              </div>
            </Space>
          </Card>

          {runtimeTopology && (
            <>
              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={8}>
                  <Card>
                    <Statistic
                      title="上游调用方"
                      value={runtimeTopology.upstream.length}
                      prefix={<ApartmentOutlined />}
                    />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card>
                    <Statistic
                      title="下游依赖"
                      value={runtimeTopology.downstream.length}
                      prefix={<ClockCircleOutlined />}
                    />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card>
                    <Statistic
                      title="异常 Span"
                      value={runtimeTopology.anomalies.length}
                      prefix={<WarningOutlined />}
                    />
                  </Card>
                </Col>
              </Row>

              <Card title="运行时关系图" style={{ marginTop: 16 }}>
                <div ref={runtimeChartRef} style={{ width: '100%', height: 460 }} />
              </Card>

              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={12}>
                  <Card title="上游调用方">
                    <List
                      locale={{ emptyText: '最近窗口内未发现明显上游调用' }}
                      dataSource={runtimeTopology.upstream}
                      renderItem={(item) => (
                        <List.Item>
                          <Space direction="vertical" size={2} style={{ width: '100%' }}>
                            <Space wrap>
                              <Tag color="green">{item.source_service}</Tag>
                              <Tag>调用次数 {item.call_count}</Tag>
                              <Tag color="blue">{item.avg_latency_ms.toFixed(0)}ms</Tag>
                              <Tag color={item.error_rate > 0 ? 'red' : 'default'}>
                                错误率 {(item.error_rate * 100).toFixed(1)}%
                              </Tag>
                            </Space>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="下游依赖">
                    <List
                      locale={{ emptyText: '最近窗口内未发现明显下游依赖' }}
                      dataSource={runtimeTopology.downstream}
                      renderItem={(item) => (
                        <List.Item>
                          <Space direction="vertical" size={2} style={{ width: '100%' }}>
                            <Space wrap>
                              <Tag color="gold">{item.target_service}</Tag>
                              <Tag>{item.dependency_type}</Tag>
                              <Tag>调用次数 {item.call_count}</Tag>
                              <Tag color="blue">{item.avg_latency_ms.toFixed(0)}ms</Tag>
                              <Tag color={item.error_rate > 0 ? 'red' : 'default'}>
                                错误率 {(item.error_rate * 100).toFixed(1)}%
                              </Tag>
                            </Space>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </Card>
                </Col>
              </Row>

              <Card title="异常 Span" style={{ marginTop: 16 }}>
                <List
                  locale={{ emptyText: '最近窗口内未发现明显异常 Span' }}
                  dataSource={runtimeTopology.anomalies}
                  renderItem={(item) => (
                    <List.Item>
                      <Space wrap>
                        <Tag color={item.anomaly_type === 'error_span' ? 'red' : 'volcano'}>
                          {item.anomaly_type}
                        </Tag>
                        <Tag>{item.span_name}</Tag>
                        <Tag color="orange">{item.duration_ms.toFixed(0)}ms</Tag>
                        {item.suspected_dependency && (
                          <Tag color="purple">疑似依赖: {item.suspected_dependency}</Tag>
                        )}
                        <Text type="secondary">trace: {item.trace_id}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </Card>
            </>
          )}
        </TabPane>

        {isAdmin && (
          <TabPane
            tab={
              <span>
                <EditOutlined />
                录入数据
              </span>
            }
            key="manual-entry"
          >
            <Card title="录入数据">
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
                description="你可以手动录入服务、服务器、数据库等节点，并为它们建立依赖或部署关系。提交后会直接写入 Neo4j。"
              />
              <Form
                form={manualEntryForm}
                layout="vertical"
                initialValues={{
                  source_type: 'Service',
                  relation_enabled: true,
                  relation_type: 'DEPENDS_ON',
                  target_type: 'Database',
                }}
                onFinish={(values) => {
                  void handleCreateManualEntry(values);
                }}
              >
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="源节点类型" name="source_type" rules={[{ required: true, message: '请选择源节点类型' }]}>
                      <Select options={NODE_TYPE_OPTIONS.map((item) => ({ label: item, value: item }))} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="源节点名称" name="source_name" rules={[{ required: true, message: '请输入源节点名称' }]}>
                      <Input placeholder="例如 order-service" />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="描述" name="source_description">
                      <Input placeholder="可选" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="IP / 地址" name="source_ip">
                      <Input placeholder="例如 10.0.0.12" />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="负责人" name="source_owner">
                      <Input placeholder="例如 ops-team" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="环境" name="source_environment">
                      <Input placeholder="例如 prod / test" />
                    </Form.Item>
                  </Col>
                </Row>

                <Divider />

                <Form.Item label="同时创建关系" name="relation_enabled" valuePropName="checked">
                  <Switch />
                </Form.Item>

                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item label="关系类型" name="relation_type">
                      <Select options={RELATION_TYPE_OPTIONS.map((item) => ({ label: item, value: item }))} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="目标节点类型" name="target_type">
                      <Select options={NODE_TYPE_OPTIONS.map((item) => ({ label: item, value: item }))} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="目标节点名称" name="target_name">
                      <Input placeholder="例如 mysql-master" />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="目标描述" name="target_description">
                      <Input placeholder="可选" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="目标 IP / 地址" name="target_ip">
                      <Input placeholder="可选" />
                    </Form.Item>
                  </Col>
                </Row>

                <Button type="primary" htmlType="submit" loading={submittingManualEntry}>
                  提交录入
                </Button>
              </Form>
            </Card>
          </TabPane>
        )}

        {isAdmin && (
          <TabPane
            tab={
              <span>
                <UploadOutlined />
                导入数据
              </span>
            }
            key="import-data"
          >
            <Card title="导入图谱数据">
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
                description="支持导入 Neo4j 查询导出的 JSON 数组数据。每条记录应包含 `n`、`r`、`m` 三段结构。"
              />
              <Upload.Dragger
                accept=".json"
                multiple={false}
                showUploadList={false}
                beforeUpload={(file) => {
                  void handleImportGraphData(file);
                  return false;
                }}
                disabled={importingGraphData}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽 JSON 文件到这里上传</p>
                <p className="ant-upload-hint">
                  推荐用于导入 `knowledge_graph/neo4j_query_table_data_2026-3-20.json` 这类数据文件
                </p>
              </Upload.Dragger>
              <div style={{ marginTop: 16 }}>
                <Text type="secondary">
                  导入时会按节点名称做 `MERGE`，重复节点会自动合并，关系也会按类型做幂等写入。
                </Text>
              </div>
            </Card>
          </TabPane>
        )}

        {isAdmin && (
          <TabPane
            tab={
              <span>
                <SettingOutlined />
                运行时配置
              </span>
            }
            key="runtime-config"
          >
            <Card title="运行时拓扑配置">
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
                description="在这里配置 Jaeger / Tempo 地址、查询超时、默认回看窗口和服务列表。保存后，智能助手和运行时拓扑页会立即使用新配置。"
              />
              <Form
                form={runtimeConfigForm}
                layout="vertical"
                onFinish={(values) => {
                  void handleSaveRuntimeConfig(values);
                }}
              >
                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item label="启用运行时拓扑" name="runtime_graph_enabled" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="Trace 后端" name="trace_backend" rules={[{ required: true, message: '请选择后端类型' }]}>
                      <Select options={[{ label: 'Jaeger', value: 'jaeger' }]} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="查询超时（秒）" name="trace_query_timeout" rules={[{ required: true, message: '请输入查询超时' }]}>
                      <InputNumber min={1} max={120} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="Jaeger Query URL" name="jaeger_query_url" rules={[{ required: true, message: '请输入 Jaeger 地址' }]}>
                      <Input placeholder="例如 http://jaeger:16686" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="Tempo Query URL" name="tempo_query_url">
                      <Input placeholder="未启用可留空" />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item
                      label="默认回看时间（分钟）"
                      name="trace_default_lookback_minutes"
                      rules={[{ required: true, message: '请输入默认回看时间' }]}
                    >
                      <InputNumber min={1} max={1440} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item
                  label="服务列表"
                  name="service_list_text"
                  extra="每行一个服务名。智能助手在通用问答里会用这份列表自动识别服务并拉取运行时拓扑。"
                >
                  <TextArea autoSize={{ minRows: 8, maxRows: 14 }} placeholder={'order-service\npayment-service\nuser-service'} />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={savingRuntimeConfig}>
                  保存配置
                </Button>
              </Form>
            </Card>
          </TabPane>
        )}
      </Tabs>

      <Modal
        title="拓扑可视化"
        open={topologyFullscreenOpen}
        onCancel={() => setTopologyFullscreenOpen(false)}
        footer={null}
        width="92vw"
        style={{ top: 20 }}
        destroyOnClose={false}
      >
        <div ref={fullscreenChartRef} style={{ width: '100%', height: '78vh' }} />
      </Modal>

      <Modal
        title="编辑节点"
        open={Boolean(editingNode)}
        onCancel={() => {
          setEditingNode(null);
          nodeEditForm.resetFields();
        }}
        onOk={() => {
          void nodeEditForm.submit();
        }}
        confirmLoading={savingNode}
      >
        <Form form={nodeEditForm} layout="vertical" onFinish={(values) => { void handleSaveNodeEdit(values); }}>
          <Form.Item label="节点名称" name="name" rules={[{ required: true, message: '请输入节点名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="属性 JSON" name="propertiesText" rules={[{ required: true, message: '请输入属性 JSON' }]}>
            <TextArea autoSize={{ minRows: 8, maxRows: 16 }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑关系"
        open={Boolean(editingRelation)}
        onCancel={() => {
          setEditingRelation(null);
          relationEditForm.resetFields();
        }}
        onOk={() => {
          void relationEditForm.submit();
        }}
        confirmLoading={savingRelation}
      >
        <Form form={relationEditForm} layout="vertical" onFinish={(values) => { void handleSaveRelationEdit(values); }}>
          <Form.Item label="关系类型" name="relation_type" rules={[{ required: true, message: '请输入关系类型' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="属性 JSON" name="propertiesText" rules={[{ required: true, message: '请输入属性 JSON' }]}>
            <TextArea autoSize={{ minRows: 8, maxRows: 16 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgeGraph;
