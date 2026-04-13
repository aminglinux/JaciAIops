import { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, List, Tag, message, Typography, Space, Divider, Tabs } from 'antd';
import { SearchOutlined, ApiOutlined, BookOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';

import { knowledgeApi } from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;
const { TabPane } = Tabs;

interface KGNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

interface KGEdge {
  source: string;
  target: string;
  type: string;
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
  const [searchInput, setSearchInput] = useState('');
  const [ragInput, setRagInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [kgResult, setKgResult] = useState<KGQueryResult | null>(null);
  const [ragResult, setRagResult] = useState<RAGResult | null>(null);
  const [topologyData, setTopologyData] = useState<{ nodes: KGNode[]; edges: KGEdge[] } | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  const handleSearchKG = async () => {
    if (!searchInput.trim()) {
      message.warning('请输入服务名称或查询语句');
      return;
    }

    setLoading(true);
    try {
      const response = await knowledgeApi.queryKG(undefined, searchInput);
      setKgResult(response as KGQueryResult);
      
      const topology = await knowledgeApi.getTopology(searchInput);
      setTopologyData(topology as { nodes: KGNode[]; edges: KGEdge[] });
    } catch (error) {
      message.error('查询失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRAGQuery = async () => {
    if (!ragInput.trim()) {
      message.warning('请输入问题');
      return;
    }

    setLoading(true);
    try {
      const response = await knowledgeApi.queryRAG(ragInput);
      setRagResult(response as RAGResult);
    } catch (error) {
      message.error('RAG 查询失败');
    } finally {
      setLoading(false);
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

      const edges = topologyData.edges.map((edge) => ({
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
          data: ['Server', 'Database', 'Service', 'Network', 'Infra'],
          top: 30,
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            data: nodes,
            edges: edges,
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
    }
  }, [topologyData]);

  useEffect(() => {
    const handleResize = () => {
      chartInstance.current?.resize();
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
      <Tabs defaultActiveKey="kg">
        <TabPane
          tab={
            <span>
              <ApiOutlined />
              知识图谱
            </span>
          }
          key="kg"
        >
          <Card title="查询知识图谱">
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入服务名称 (如: prod-server-01) 或查询语句 (如: 查询所有服务器)"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onPressEnter={handleSearchKG}
              />
              <Button type="primary" icon={<SearchOutlined />} onClick={handleSearchKG} loading={loading}>
                查询
              </Button>
            </Space.Compact>

            <div style={{ marginTop: 16 }}>
              <Text type="secondary">快速查询:</Text>
              <Space style={{ marginLeft: 8 }} wrap>
                <Button size="small" onClick={() => { setSearchInput('prod-server-01'); handleSearchKG(); }}>
                  prod-server-01
                </Button>
                <Button size="small" onClick={() => { setSearchInput('查询所有服务器'); handleSearchKG(); }}>
                  所有服务器
                </Button>
                <Button size="small" onClick={() => { setSearchInput('查询所有数据库'); handleSearchKG(); }}>
                  所有数据库
                </Button>
              </Space>
            </div>
          </Card>

          {renderKGResult()}

          {topologyData && topologyData.nodes.length > 0 && (
            <Card title="拓扑可视化" style={{ marginTop: 16 }}>
              <div ref={chartRef} style={{ width: '100%', height: 400 }} />
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
              <Button type="primary" icon={<SearchOutlined />} onClick={handleRAGQuery} loading={loading}>
                查询知识库
              </Button>
            </Space>

            <div style={{ marginTop: 16 }}>
              <Text type="secondary">示例问题:</Text>
              <Space style={{ marginLeft: 8 }} wrap>
                <Button size="small" onClick={() => setRagInput('数据库连接池耗尽怎么处理')}>
                  数据库连接池耗尽
                </Button>
                <Button size="small" onClick={() => setRagInput('如何处理服务超时问题')}>
                  服务超时处理
                </Button>
                <Button size="small" onClick={() => setRagInput('Redis 主从切换的影响')}>
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
      </Tabs>
    </div>
  );
};

export default KnowledgeGraph;
