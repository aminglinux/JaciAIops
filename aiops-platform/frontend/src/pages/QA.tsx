import { useEffect, useMemo, useState } from 'react';
import { Alert, Card, Input, Button, List, Tag, Spin, message, Typography, Space, Divider, Switch } from 'antd';
import { SendOutlined, QuestionCircleOutlined } from '@ant-design/icons';

import { knowledgeApi, llmApi } from '../services/api';
import type { LLMRuntimeBinding } from '../types';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Message {
  id: number;
  type: 'user' | 'assistant';
  content: string;
  loading?: boolean;
  extra?: {
    intent?: {
      intent: string;
      entities: Record<string, string>;
      confidence: string;
    };
    knowledge?: string;
    mode?: string;
  };
}

const QA = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      type: 'assistant',
      content: '你好！我是AIOps智能问答助手。你可以问我关于运维的问题，例如：\n• 订单服务的依赖关系是什么？\n• 如何处理数据库连接池耗尽？\n• 最近有哪些故障案例？',
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [analyzeProblem, setAnalyzeProblem] = useState(false);
  const [runtimeBindings, setRuntimeBindings] = useState<LLMRuntimeBinding[]>([]);
  const [runtimeLoading, setRuntimeLoading] = useState(false);

  useEffect(() => {
    const fetchRuntimeConfig = async () => {
      setRuntimeLoading(true);
      try {
        const runtimeConfig = await llmApi.getRuntimeConfig();
        setRuntimeBindings(runtimeConfig.bindings || []);
      } catch (error) {
        console.error('获取运行时模型配置失败', error);
      } finally {
        setRuntimeLoading(false);
      }
    };
    fetchRuntimeConfig();
  }, []);

  const activeRuntimeBinding = useMemo(() => {
    const sceneKey = analyzeProblem ? 'master_planner' : 'general_chat';
    return runtimeBindings.find((binding) => binding.sceneKey === sceneKey);
  }, [analyzeProblem, runtimeBindings]);

  const handleSend = async () => {
    if (!input.trim()) {
      message.warning('请输入问题');
      return;
    }

    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      content: input,
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const assistantMessage: Message = {
      id: Date.now() + 1,
      type: 'assistant',
      content: '',
      loading: true,
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const response = await knowledgeApi.chat(input, analyzeProblem);
      
      const updatedMessage: Message = {
        id: assistantMessage.id,
        type: 'assistant',
        content: (response as { answer?: string }).answer || '抱歉，我无法回答这个问题。',
        loading: false,
        extra: {
          intent: (response as { intent?: { intent: string; entities: Record<string, string>; confidence: string } }).intent,
          knowledge: (response as { knowledge?: { knowledge_report?: string } }).knowledge?.knowledge_report,
          mode: (response as { mode?: string }).mode,
        },
      };
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? updatedMessage : m));
    } catch (error) {
      const errorMessage: Message = {
        id: assistantMessage.id,
        type: 'assistant',
        content: '抱歉，查询过程中出现错误，请稍后重试。',
        loading: false,
      };
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? errorMessage : m));
    } finally {
      setLoading(false);
    }
  };

  const getIntentColor = (intent: string) => {
    const colors: Record<string, string> = { 
      DIAGNOSE: 'blue', 
      QUERY_STATUS: 'green', 
      EXECUTE_FIX: 'orange', 
      GENERAL_QA: 'purple' 
    };
    return colors[intent] || 'default';
  };

  return (
    <div style={{ height: 'calc(100vh - 144px)', display: 'flex', flexDirection: 'column' }}>
      <Card 
        title={
          <span>
            <QuestionCircleOutlined style={{ marginRight: 8 }} />
            智能问答
          </span>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, overflow: 'auto', padding: 16 }}
      >
        <List
          dataSource={messages}
          renderItem={(item) => (
            <div style={{ 
              marginBottom: 16, 
              textAlign: item.type === 'user' ? 'right' : 'left' 
            }}>
              <div style={{
                display: 'inline-block',
                maxWidth: '80%',
                textAlign: 'left',
                padding: '12px 16px',
                borderRadius: 8,
                background: item.type === 'user' ? '#1890ff' : '#f5f5f5',
                color: item.type === 'user' ? '#fff' : 'inherit',
              }}>
                {item.loading ? (
                  <Spin size="small" />
                ) : (
                  <>
                    <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                      {item.content}
                    </Paragraph>
                    
                    {item.extra?.intent && (
                      <div style={{ marginTop: 12 }}>
                        <Divider style={{ margin: '8px 0' }} />
                        <Space size={4} wrap>
                          {item.extra.mode && (
                            <Tag color={item.extra.mode === 'analysis' ? 'red' : 'cyan'}>
                              {item.extra.mode === 'analysis' ? '分析问题' : '通用问答'}
                            </Tag>
                          )}
                          <Tag color={getIntentColor(item.extra.intent.intent)}>
                            {item.extra.intent.intent}
                          </Tag>
                          <Tag>置信度: {item.extra.intent.confidence}</Tag>
                          {item.extra.intent.entities.service && (
                            <Tag color="blue">服务: {item.extra.intent.entities.service}</Tag>
                          )}
                        </Space>
                      </div>
                    )}
                    
                    {item.extra?.knowledge && (
                      <div style={{ marginTop: 12 }}>
                        <Divider style={{ margin: '8px 0' }} />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          知识库参考：
                        </Text>
                        <Paragraph 
                          style={{ 
                            margin: 0, 
                            fontSize: 12, 
                            whiteSpace: 'pre-wrap',
                            color: item.type === 'user' ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.45)'
                          }}
                          ellipsis={{ rows: 3, expandable: true }}
                        >
                          {item.extra.knowledge}
                        </Paragraph>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        />
      </Card>

      <Card style={{ marginTop: 16 }}>
        <Alert
          type={activeRuntimeBinding?.source === 'database' ? 'success' : 'warning'}
          showIcon
          style={{ marginBottom: 12 }}
          message={
            runtimeLoading
              ? '正在读取当前模型绑定...'
              : analyzeProblem
                ? '当前为“分析问题”模式'
                : '当前为“通用问答”模式'
          }
          description={
            runtimeLoading
              ? '请稍候'
              : activeRuntimeBinding
                ? `当前使用 ${activeRuntimeBinding.providerName} / ${activeRuntimeBinding.model}${activeRuntimeBinding.source === 'env' ? '（未绑定场景模型，使用环境变量 fallback）' : ''}`
                : '暂未读取到模型绑定信息'
          }
        />
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary">
            默认是通用问答；打开开关后，才会走运维问题分析流程。
          </Text>
          <Space>
            <Text strong>分析问题</Text>
            <Switch checked={analyzeProblem} onChange={setAnalyzeProblem} />
          </Space>
        </div>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={analyzeProblem ? '输入要分析的运维问题...' : '输入你的问题，和助手直接对话...'}
            autoSize={{ minRows: 1, maxRows: 3 }}
            style={{ flex: 1 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Button 
            type="primary" 
            icon={<SendOutlined />} 
            onClick={handleSend}
            loading={loading}
            style={{ height: 'auto' }}
          >
            发送
          </Button>
        </Space.Compact>
      </Card>
    </div>
  );
};

export default QA;
