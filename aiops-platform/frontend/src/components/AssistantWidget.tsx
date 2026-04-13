import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Divider,
  FloatButton,
  Input,
  List,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { CloseOutlined, QuestionCircleOutlined, SendOutlined } from '@ant-design/icons';

import { knowledgeApi, llmApi } from '../services/api';
import type { LLMRuntimeBinding, RuntimeTopologySnapshot } from '../types';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const renderMarkdownToHtml = (markdown: string) => {
  const escaped = escapeHtml(markdown || '');
  const lines = escaped.split('\n');
  const html: string[] = [];
  let inCodeBlock = false;
  let inList = false;

  const closeList = () => {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  };

  const renderInline = (value: string) =>
    value
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>');

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      closeList();
      if (!inCodeBlock) {
        html.push('<pre><code>');
        inCodeBlock = true;
      } else {
        html.push('</code></pre>');
        inCodeBlock = false;
      }
      continue;
    }

    if (inCodeBlock) {
      html.push(`${line}\n`);
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${renderInline(line.replace(/^\s*[-*]\s+/, ''))}</li>`);
      continue;
    }

    closeList();

    if (!line.trim()) {
      html.push('<br />');
      continue;
    }

    if (/^###\s+/.test(line)) {
      html.push(`<h3>${renderInline(line.replace(/^###\s+/, ''))}</h3>`);
      continue;
    }
    if (/^##\s+/.test(line)) {
      html.push(`<h2>${renderInline(line.replace(/^##\s+/, ''))}</h2>`);
      continue;
    }
    if (/^#\s+/.test(line)) {
      html.push(`<h1>${renderInline(line.replace(/^#\s+/, ''))}</h1>`);
      continue;
    }

    html.push(`<p>${renderInline(line)}</p>`);
  }

  closeList();
  if (inCodeBlock) {
    html.push('</code></pre>');
  }

  return html.join('');
};

const markdownMessageStyle = `
  .assistant-markdown { line-height: 1.55; }
  .assistant-markdown p,
  .assistant-markdown ul,
  .assistant-markdown ol,
  .assistant-markdown pre,
  .assistant-markdown h1,
  .assistant-markdown h2,
  .assistant-markdown h3 {
    margin-top: 0;
    margin-bottom: 6px;
  }
  .assistant-markdown p:last-child,
  .assistant-markdown ul:last-child,
  .assistant-markdown ol:last-child,
  .assistant-markdown pre:last-child {
    margin-bottom: 0;
  }
  .assistant-markdown ul,
  .assistant-markdown ol {
    padding-left: 18px;
  }
  .assistant-markdown code {
    background: rgba(0, 0, 0, 0.06);
    padding: 2px 4px;
    border-radius: 4px;
  }
  .assistant-markdown pre {
    background: rgba(0, 0, 0, 0.06);
    padding: 10px 12px;
    border-radius: 8px;
    overflow-x: auto;
  }
`;

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
    runtimeTopology?: RuntimeTopologySnapshot | null;
  };
}

const AssistantWidget = () => {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      type: 'assistant',
      content: '你好，我是智能助手。默认可直接通用问答；打开“分析问题”后，我会按运维分析流程帮你定位问题。',
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [analyzeProblem, setAnalyzeProblem] = useState(false);
  const [runtimeBindings, setRuntimeBindings] = useState<LLMRuntimeBinding[]>([]);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [position, setPosition] = useState({ right: 24, bottom: 88 });
  const [dragging, setDragging] = useState(false);
  const listContainerRef = useRef<HTMLDivElement | null>(null);
  const streamRef = useRef<EventSource | null>(null);
  const dragStateRef = useRef<{ startX: number; startY: number; originRight: number; originBottom: number } | null>(null);

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

  useEffect(() => {
    if (listContainerRef.current) {
      listContainerRef.current.scrollTop = listContainerRef.current.scrollHeight;
    }
  }, [messages, open]);

  useEffect(() => {
    return () => {
      streamRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      if (!dragStateRef.current) return;
      const deltaX = event.clientX - dragStateRef.current.startX;
      const deltaY = event.clientY - dragStateRef.current.startY;

      const nextRight = Math.max(16, dragStateRef.current.originRight - deltaX);
      const nextBottom = Math.max(16, dragStateRef.current.originBottom - deltaY);
      setPosition({ right: nextRight, bottom: nextBottom });
    };

    const handleMouseUp = () => {
      dragStateRef.current = null;
      setDragging(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const activeRuntimeBinding = useMemo(() => {
    const sceneKey = analyzeProblem ? 'master_planner' : 'general_chat';
    return runtimeBindings.find((binding) => binding.sceneKey === sceneKey);
  }, [analyzeProblem, runtimeBindings]);

  const handleSend = async () => {
    if (!input.trim()) {
      message.warning('请输入内容');
      return;
    }

    const currentInput = input;
    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      content: currentInput,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const assistantMessage: Message = {
      id: Date.now() + 1,
      type: 'assistant',
      content: '',
      loading: true,
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      streamRef.current?.close();
      const params = new URLSearchParams({
        question: currentInput,
        analyze_problem: String(analyzeProblem),
      });
      const eventSource = new EventSource(`/api/knowledge/qa/chat/stream?${params.toString()}`);
      streamRef.current = eventSource;

      eventSource.onmessage = (event) => {
        const payload = JSON.parse(event.data) as {
          type: 'meta' | 'delta' | 'done';
          content?: string;
          mode?: string;
          intent?: { intent: string; entities: Record<string, string>; confidence: string };
          knowledge?: { knowledge_report?: string } | null;
          runtime_topology?: RuntimeTopologySnapshot | null;
        };

        if (payload.type === 'meta') {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantMessage.id
                ? {
                    ...item,
                    extra: {
                      intent: payload.intent,
                      knowledge: payload.knowledge?.knowledge_report,
                      mode: payload.mode,
                      runtimeTopology: payload.runtime_topology,
                    },
                  }
                : item
            )
          );
          return;
        }

        if (payload.type === 'delta') {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantMessage.id
                ? {
                    ...item,
                    loading: false,
                    content: `${item.content}${payload.content || ''}`,
                  }
                : item
            )
          );
          return;
        }

        if (payload.type === 'done') {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantMessage.id
                ? {
                    ...item,
                    loading: false,
                    content: item.content || '抱歉，我无法回答这个问题。',
                  }
                : item
            )
          );
          setLoading(false);
          eventSource.close();
          streamRef.current = null;
        }
      };

      eventSource.onerror = async () => {
        eventSource.close();
        streamRef.current = null;
        try {
          const response = await knowledgeApi.chat(currentInput, analyzeProblem);
          const updatedMessage: Message = {
            id: assistantMessage.id,
            type: 'assistant',
            content: (response as { answer?: string }).answer || '抱歉，我无法回答这个问题。',
            loading: false,
            extra: {
              intent: (response as { intent?: { intent: string; entities: Record<string, string>; confidence: string } }).intent,
              knowledge: (response as { knowledge?: { knowledge_report?: string } }).knowledge?.knowledge_report,
              mode: (response as { mode?: string }).mode,
              runtimeTopology: (response as { runtime_topology?: RuntimeTopologySnapshot | null }).runtime_topology || null,
            },
          };
          setMessages((prev) => prev.map((item) => (item.id === assistantMessage.id ? updatedMessage : item)));
        } catch (error) {
          const errorMessage: Message = {
            id: assistantMessage.id,
            type: 'assistant',
            content: '抱歉，查询过程中出现错误，请稍后重试。',
            loading: false,
          };
          setMessages((prev) => prev.map((item) => (item.id === assistantMessage.id ? errorMessage : item)));
        } finally {
          setLoading(false);
        }
      };
    } catch (error) {
      const errorMessage: Message = {
        id: assistantMessage.id,
        type: 'assistant',
        content: '抱歉，查询过程中出现错误，请稍后重试。',
        loading: false,
      };
      setMessages((prev) => prev.map((item) => (item.id === assistantMessage.id ? errorMessage : item)));
      setLoading(false);
    }
  };

  const getIntentColor = (intent: string) => {
    const colors: Record<string, string> = {
      DIAGNOSE: 'blue',
      QUERY_STATUS: 'green',
      EXECUTE_FIX: 'orange',
      GENERAL_QA: 'purple',
    };
    return colors[intent] || 'default';
  };

  const handleDragStart = (event: React.MouseEvent<HTMLDivElement>) => {
    dragStateRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originRight: position.right,
      originBottom: position.bottom,
    };
    setDragging(true);
  };

  return (
    <>
      <style>{markdownMessageStyle}</style>
      <FloatButton
        icon={<QuestionCircleOutlined />}
        type="primary"
        tooltip="智能助手"
        style={{ right: 24, bottom: 24 }}
        onClick={() => setOpen(true)}
      />

      {open && (
        <Card
          title={
            <div
              onMouseDown={handleDragStart}
              style={{
                cursor: dragging ? 'grabbing' : 'grab',
                userSelect: 'none',
                width: '100%',
              }}
            >
              智能助手
            </div>
          }
          extra={<Button type="text" icon={<CloseOutlined />} onClick={() => setOpen(false)} />}
          style={{
            position: 'fixed',
            right: position.right,
            bottom: position.bottom,
            width: 560,
            height: 760,
            zIndex: 1100,
            boxShadow: '0 12px 36px rgba(0,0,0,0.18)',
            borderRadius: 12,
          }}
          bodyStyle={{
            padding: 16,
            height: 'calc(100% - 57px)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
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

          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              默认通用问答；打开开关后才走运维分析流程。
            </Text>
            <Space size={8}>
              <Text strong style={{ fontSize: 12 }}>分析问题</Text>
              <Switch checked={analyzeProblem} onChange={setAnalyzeProblem} />
            </Space>
          </div>

          <div
            ref={listContainerRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              paddingRight: 4,
              marginBottom: 12,
            }}
          >
            <List
              dataSource={messages}
              renderItem={(item) => (
                <div style={{ marginBottom: 12, textAlign: item.type === 'user' ? 'right' : 'left' }}>
                  <div
                    style={{
                      display: 'inline-block',
                      width: 'fit-content',
                      maxWidth: item.type === 'user' ? '56%' : '88%',
                      minWidth: item.type === 'user' ? 72 : undefined,
                      textAlign: 'left',
                      padding: item.type === 'user' ? '8px 10px' : '10px 12px',
                      borderRadius: 12,
                      background: item.type === 'user' ? '#1677ff' : '#f5f5f5',
                      color: item.type === 'user' ? '#fff' : 'inherit',
                    }}
                  >
                    {item.loading ? (
                      <Spin size="small" />
                    ) : (
                      <>
                        <div
                          className="assistant-markdown"
                          style={{ margin: 0 }}
                          dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(item.content) }}
                        />
                        {item.extra?.intent && (
                          <div style={{ marginTop: 10 }}>
                            <Divider style={{ margin: '8px 0' }} />
                            <Space size={4} wrap>
                              {item.extra.mode && (
                                <Tag color={item.extra.mode === 'analysis' ? 'red' : 'cyan'}>
                                  {item.extra.mode === 'analysis' ? '分析问题' : '通用问答'}
                                </Tag>
                              )}
                              <Tag color={getIntentColor(item.extra.intent.intent)}>{item.extra.intent.intent}</Tag>
                              <Tag>置信度: {item.extra.intent.confidence}</Tag>
                              {item.extra.intent.entities.service && <Tag color="blue">服务: {item.extra.intent.entities.service}</Tag>}
                            </Space>
                          </div>
                        )}
                        {item.extra?.knowledge && (
                          <div style={{ marginTop: 10 }}>
                            <Divider style={{ margin: '8px 0' }} />
                            <Text type="secondary" style={{ fontSize: 12 }}>知识库参考：</Text>
                            <Paragraph
                              style={{
                                margin: 0,
                                fontSize: 12,
                                whiteSpace: 'pre-wrap',
                                color: item.type === 'user' ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.45)',
                              }}
                              ellipsis={{ rows: 3, expandable: true }}
                            >
                              {item.extra.knowledge}
                            </Paragraph>
                          </div>
                        )}
                        {item.extra?.runtimeTopology && (
                          <div style={{ marginTop: 10 }}>
                            <Divider style={{ margin: '8px 0' }} />
                            <Text type="secondary" style={{ fontSize: 12 }}>运行时拓扑：</Text>
                            <div style={{ marginTop: 6 }}>
                              {item.extra.runtimeTopology.downstream.slice(0, 3).map((dependency) => (
                                <Tag key={`${dependency.source_service}-${dependency.target_service}`} color="geekblue">
                                  {dependency.target_service} · {dependency.avg_latency_ms.toFixed(0)}ms
                                </Tag>
                              ))}
                              {item.extra.runtimeTopology.anomalies.slice(0, 2).map((anomaly) => (
                                <Tag key={`${anomaly.trace_id}-${anomaly.span_name}`} color="volcano">
                                  {anomaly.span_name} · {anomaly.duration_ms.toFixed(0)}ms
                                </Tag>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}
            />
          </div>

          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={analyzeProblem ? '输入要分析的运维问题...' : '输入你的问题，和助手直接对话...'}
              autoSize={{ minRows: 1, maxRows: 4 }}
              style={{ flex: 1, maxWidth: 460 }}
              onPressEnter={(event) => {
                if (!event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              style={{ height: 'auto', minWidth: 88 }}
            >
              发送
            </Button>
          </Space.Compact>
        </Card>
      )}
    </>
  );
};

export default AssistantWidget;
