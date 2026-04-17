import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Divider,
  Input,
  List,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { DoubleLeftOutlined, DoubleRightOutlined, DownOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons';

import { knowledgeApi, llmApi } from '../services/api';
import type { ChatHistoryMessage, ChatSessionSummary, DeepDiagnosisChatResult, LLMRuntimeBinding, RuntimeTopologySnapshot } from '../types';

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
  @keyframes assistantBubbleFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
  }
  @keyframes assistantBubblePulse {
    0% { box-shadow: 0 0 0 0 rgba(22, 119, 255, 0.32); }
    70% { box-shadow: 0 0 0 12px rgba(22, 119, 255, 0); }
    100% { box-shadow: 0 0 0 0 rgba(22, 119, 255, 0); }
  }
  .assistant-launcher-bubble {
    animation: assistantBubbleFloat 3.2s ease-in-out infinite;
    transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
  }
  .assistant-launcher-bubble:hover {
    transform: translateY(-4px) scale(1.03);
    box-shadow: 0 18px 38px rgba(22, 119, 255, 0.34) !important;
    filter: saturate(1.08);
  }
  .assistant-launcher-orb {
    animation: assistantBubblePulse 2.4s ease-out infinite;
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
    deepDiagnosis?: {
      status?: string;
      iterations?: number;
      durationSeconds?: number;
      matchedSkills?: string[];
      tools?: string[];
      warnings?: string[];
    };
  };
}

const buildWelcomeMessage = (): Message => ({
  id: 0,
  type: 'assistant',
  content: '你好，我是智能助手。默认可直接通用问答；打开“分析问题”后，我会按运维分析流程帮你定位问题。',
});

const mapHistoryMessage = (message: ChatHistoryMessage): Message => ({
  id: message.id,
  type: message.role,
  content: message.content,
  extra: message.role === 'assistant' ? {
    intent: message.intent || undefined,
    knowledge: message.knowledge?.knowledge_report,
    mode: message.mode || undefined,
    runtimeTopology: message.runtime_topology || null,
    deepDiagnosis: message.knowledge?.deep_diagnosis
      ? {
          status: message.knowledge.deep_diagnosis.status,
          iterations: message.knowledge.deep_diagnosis.iterations,
          durationSeconds: message.knowledge.deep_diagnosis.duration_seconds,
          matchedSkills: message.knowledge.deep_diagnosis.matched_skills || [],
          tools: message.knowledge.deep_diagnosis.tools || [],
          warnings: message.knowledge.deep_diagnosis.warnings || [],
        }
      : undefined,
  } : undefined,
});

const AssistantWidget = () => {
  const [open, setOpen] = useState(false);
  const [launcherEdgeHidden, setLauncherEdgeHidden] = useState<boolean>(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return localStorage.getItem('assistant_launcher_edge_hidden') === '1';
  });
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([buildWelcomeMessage()]);
  const [loading, setLoading] = useState(false);
  const [analyzeProblem, setAnalyzeProblem] = useState(false);
  const [deepDiagnosis, setDeepDiagnosis] = useState(false);
  const [runtimeBindings, setRuntimeBindings] = useState<LLMRuntimeBinding[]>([]);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
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

  const refreshSessions = async (preferredSessionId?: string | null) => {
    try {
      const response = await knowledgeApi.listChatSessions();
      const nextSessions = response.sessions || [];
      setSessions(nextSessions);
      if (preferredSessionId) {
        setActiveSessionId(preferredSessionId);
        return;
      }
      if (!activeSessionId && nextSessions.length > 0) {
        setActiveSessionId(nextSessions[0].session_id);
      }
    } catch (error) {
      console.error('获取会话历史失败', error);
    }
  };

  const loadSessionMessages = async (sessionId: string) => {
    setSessionLoading(true);
    try {
      const response = await knowledgeApi.getChatSession(sessionId);
      const historyMessages = response.messages?.map(mapHistoryMessage) || [];
      setMessages(historyMessages.length > 0 ? historyMessages : [buildWelcomeMessage()]);
      setAnalyzeProblem(Boolean(response.session?.analyze_problem));
      setActiveSessionId(sessionId);
    } catch (error) {
      message.error('加载会话失败');
    } finally {
      setSessionLoading(false);
    }
  };

  const handleNewSession = () => {
    streamRef.current?.close();
    streamRef.current = null;
    setActiveSessionId(null);
    setMessages([buildWelcomeMessage()]);
    setAnalyzeProblem(false);
    setDeepDiagnosis(false);
    setLoading(false);
  };

  useEffect(() => {
    if (!analyzeProblem) {
      setDeepDiagnosis(false);
    }
  }, [analyzeProblem]);

  useEffect(() => {
    if (!open) {
      return;
    }
    void refreshSessions();
  }, [open]);

  useEffect(() => {
    if (!open || !activeSessionId || loading) {
      return;
    }
    void loadSessionMessages(activeSessionId);
  }, [activeSessionId, open, loading]);

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

    if (analyzeProblem && deepDiagnosis) {
      try {
        const result = await knowledgeApi.deepDiagnose(currentInput, activeSessionId || undefined) as DeepDiagnosisChatResult;
        if (result.session_id) {
          setActiveSessionId(result.session_id);
        }

        setMessages((prev) =>
          prev.map((item) =>
            item.id === assistantMessage.id
              ? {
                  ...item,
                  loading: false,
                  content: result.answer || '诊断完成，已生成过程明细。',
                  extra: {
                    intent: result.intent?.intent
                      ? {
                          intent: result.intent.intent,
                          entities: result.intent.entities || {},
                          confidence: result.intent.confidence || 'LOW',
                        }
                      : undefined,
                    knowledge: result.knowledge?.knowledge_report,
                    mode: result.mode || 'deep_analysis',
                    runtimeTopology: null,
                    deepDiagnosis: {
                      status: result.deep_diagnosis?.status,
                      iterations: result.deep_diagnosis?.iterations,
                      durationSeconds: result.deep_diagnosis?.duration_seconds,
                      matchedSkills: result.deep_diagnosis?.matched_skills || [],
                      tools: result.deep_diagnosis?.tools || [],
                      warnings: result.deep_diagnosis?.warnings || [],
                    },
                  },
                }
              : item
          )
        );
        void refreshSessions(result.session_id || activeSessionId);
      } catch (error) {
        const detail = error instanceof Error ? error.message : '深度诊断请求失败';
        setMessages((prev) =>
          prev.map((item) =>
            item.id === assistantMessage.id
              ? {
                  ...item,
                  loading: false,
                  content: `抱歉，深度诊断执行失败：${detail}`,
                }
              : item
          )
        );
      } finally {
        setLoading(false);
        streamRef.current = null;
      }
      return;
    }

    try {
      streamRef.current?.close();
      const token = localStorage.getItem('token');
      const controller = new AbortController();
      streamRef.current = { close: () => controller.abort() } as EventSource;

      const response = await fetch('/api/knowledge/qa/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: currentInput,
          analyze_problem: analyzeProblem,
          session_id: activeSessionId,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error('stream request failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      const handlePayload = (payload: {
        type: 'meta' | 'delta' | 'done';
        session_id?: string;
        content?: string;
        mode?: string;
        intent?: { intent: string; entities: Record<string, string>; confidence: string };
        knowledge?: { knowledge_report?: string } | null;
        runtime_topology?: RuntimeTopologySnapshot | null;
      }) => {
        if (payload.session_id) {
          setActiveSessionId(payload.session_id);
        }

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
          streamRef.current = null;
          void refreshSessions(payload.session_id || activeSessionId);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const dataLine = event
            .split('\n')
            .find((line) => line.startsWith('data: '));
          if (!dataLine) {
            continue;
          }
          handlePayload(JSON.parse(dataLine.slice(6)));
        }
      }
    } catch (error) {
      try {
        const response = await knowledgeApi.chat(currentInput, analyzeProblem, activeSessionId || undefined);
        const typed = response as {
          answer?: string;
          session_id?: string;
          intent?: { intent: string; entities: Record<string, string>; confidence: string };
          knowledge?: { knowledge_report?: string };
          mode?: string;
          runtime_topology?: RuntimeTopologySnapshot | null;
        };
        if (typed.session_id) {
          setActiveSessionId(typed.session_id);
        }
        const updatedMessage: Message = {
          id: assistantMessage.id,
          type: 'assistant',
          content: typed.answer || '抱歉，我无法回答这个问题。',
          loading: false,
          extra: {
            intent: typed.intent,
            knowledge: typed.knowledge?.knowledge_report,
            mode: typed.mode,
            runtimeTopology: typed.runtime_topology || null,
          },
        };
        setMessages((prev) => prev.map((item) => (item.id === assistantMessage.id ? updatedMessage : item)));
        void refreshSessions(typed.session_id || activeSessionId);
      } catch {
        const errorMessage: Message = {
          id: assistantMessage.id,
          type: 'assistant',
          content: '抱歉，查询过程中出现错误，请稍后重试。',
          loading: false,
        };
        setMessages((prev) => prev.map((item) => (item.id === assistantMessage.id ? errorMessage : item)));
      } finally {
        setLoading(false);
        streamRef.current = null;
      }
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

  const hideLauncherToEdge = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setLauncherEdgeHidden(true);
    localStorage.setItem('assistant_launcher_edge_hidden', '1');
  };

  const restoreLauncherFromEdge = () => {
    setLauncherEdgeHidden(false);
    localStorage.setItem('assistant_launcher_edge_hidden', '0');
  };

  return (
    <>
      <style>{markdownMessageStyle}</style>
      {!open && !launcherEdgeHidden && (
        <button
          type="button"
          className="assistant-launcher-bubble"
          aria-label="打开AIOps助手"
          onClick={() => setOpen(true)}
          style={{
            position: 'fixed',
            right: 24,
            bottom: 24,
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            minWidth: 188,
            padding: '12px 16px 12px 12px',
            border: 'none',
            borderRadius: '22px 22px 6px 22px',
            cursor: 'pointer',
            color: '#fff',
            background: 'linear-gradient(135deg, #1677ff 0%, #7c3aed 100%)',
            boxShadow: '0 14px 32px rgba(22,119,255,0.3)',
          }}
        >
          <span
            className="assistant-launcher-orb"
            style={{
              width: 44,
              height: 44,
              borderRadius: 14,
              background: 'rgba(255,255,255,0.18)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.22)',
              flexShrink: 0,
            }}
          >
            <RobotOutlined style={{ fontSize: 24 }} />
          </span>
          <span
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              lineHeight: 1.2,
              textAlign: 'left',
            }}
          >
            <span style={{ fontSize: 15, fontWeight: 700 }}>问问 AIOps</span>
            <span style={{ marginTop: 3, fontSize: 11, opacity: 0.82 }}>智能问答 / 故障分析</span>
          </span>
          <span
            style={{
              position: 'absolute',
              right: 18,
              top: 10,
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#52c41a',
              boxShadow: '0 0 0 3px rgba(82,196,26,0.18)',
            }}
          />
          <button
            type="button"
            title="贴边隐藏"
            onClick={hideLauncherToEdge}
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              width: 22,
              height: 22,
              borderRadius: 999,
              border: 'none',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255,255,255,0.24)',
              color: '#fff',
            }}
          >
            <DoubleRightOutlined style={{ fontSize: 11 }} />
          </button>
        </button>
      )}

      {!open && launcherEdgeHidden && (
        <button
          type="button"
          onClick={restoreLauncherFromEdge}
          title="还原助手"
          style={{
            position: 'fixed',
            right: 0,
            bottom: 24,
            zIndex: 1100,
            border: 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '10px 10px 10px 8px',
            borderRadius: '14px 0 0 14px',
            color: '#fff',
            background: 'linear-gradient(135deg, #1677ff 0%, #7c3aed 100%)',
            boxShadow: '0 10px 24px rgba(22,119,255,0.28)',
          }}
        >
          <RobotOutlined style={{ fontSize: 14 }} />
          <DoubleLeftOutlined style={{ fontSize: 10 }} />
        </button>
      )}

      {open && (
        <Card
          title={
            <div
              onMouseDown={handleDragStart}
              style={{
                cursor: dragging ? 'grabbing' : 'grab',
                userSelect: 'none',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, #1677ff 0%, #7c3aed 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 6px 18px rgba(22,119,255,0.28)',
                  color: '#fff',
                  fontWeight: 700,
                  fontSize: 15,
                  flexShrink: 0,
                }}
              >
                AI
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                <span
                  style={{
                    fontSize: 17,
                    fontWeight: 700,
                    background: 'linear-gradient(135deg, #1677ff 0%, #7c3aed 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                  }}
                >
                  AIOps助手
                </span>
                <span style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>
                  智能问答与运维分析
                </span>
              </div>
            </div>
          }
          extra={
            <Button
              type="text"
              onClick={() => setOpen(false)}
              style={{
                borderRadius: 999,
                paddingInline: 10,
                height: 32,
                background: 'linear-gradient(135deg, #f5f5f5 0%, #e6f4ff 100%)',
                border: '1px solid #d9d9d9',
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span style={{ fontSize: 12, fontWeight: 500 }}>收起</span>
              <DownOutlined style={{ fontSize: 11, color: '#1677ff' }} />
            </Button>
          }
          style={{
            position: 'fixed',
            right: position.right,
            bottom: position.bottom,
            width: 'min(920px, calc(100vw - 32px))',
            height: 'min(860px, calc(100vh - 32px))',
            maxWidth: 'calc(100vw - 32px)',
            maxHeight: 'calc(100vh - 32px)',
            zIndex: 1100,
            boxShadow: '0 12px 36px rgba(0,0,0,0.18)',
            borderRadius: 12,
            overflow: 'hidden',
          }}
          bodyStyle={{
            padding: 0,
            height: 'calc(100% - 57px)',
            display: 'flex',
          }}
        >
          <div
            style={{
              width: 'clamp(220px, 28%, 260px)',
              minWidth: 220,
              borderRight: '1px solid #f0f0f0',
              padding: 16,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              background: '#fafafa',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <Text strong>历史会话</Text>
              <Button size="small" onClick={handleNewSession}>新会话</Button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
              {sessions.length > 0 ? (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  {sessions.map((session) => (
                    <Button
                      key={session.session_id}
                      type={activeSessionId === session.session_id ? 'primary' : 'default'}
                      onClick={() => setActiveSessionId(session.session_id)}
                      style={{
                        width: '100%',
                        height: 'auto',
                        minHeight: 56,
                        textAlign: 'left',
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'flex-start',
                        padding: '8px 10px',
                      }}
                    >
                      <div style={{ width: '100%', overflow: 'hidden' }}>
                        <div style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {session.title}
                        </div>
                        <div style={{ fontSize: 12, opacity: 0.75, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {session.last_message || '暂无消息'}
                        </div>
                      </div>
                    </Button>
                  ))}
                </Space>
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  暂无历史会话，点击“新会话”后开始提问。
                </Text>
              )}
            </div>
          </div>

          <div
            style={{
              flex: 1,
              padding: 16,
              display: 'flex',
              flexDirection: 'column',
              minWidth: 0,
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
                    ? `当前使用 ${activeRuntimeBinding.providerName} / ${activeRuntimeBinding.model}${activeRuntimeBinding.source === 'env' ? '（未绑定场景模型，使用环境变量 fallback）' : ''}${analyzeProblem && deepDiagnosis ? '（已启用深度诊断）' : ''}`
                    : '暂未读取到模型绑定信息'
              }
            />

            <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                默认通用问答；打开分析后可选快速分析或深度诊断。
              </Text>
              <Space size={8}>
                <Text strong style={{ fontSize: 12 }}>分析问题</Text>
                <Switch checked={analyzeProblem} onChange={setAnalyzeProblem} />
                {analyzeProblem && (
                  <>
                    <Text strong style={{ fontSize: 12 }}>深度诊断</Text>
                    <Switch checked={deepDiagnosis} onChange={setDeepDiagnosis} />
                  </>
                )}
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
              {sessionLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 48 }}>
                  <Spin />
                </div>
              ) : (
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
                                  <Tag color={item.extra.mode === 'analysis' ? 'red' : item.extra.mode === 'deep_analysis' ? 'volcano' : 'cyan'}>
                                    {item.extra.mode === 'analysis' ? '分析问题' : item.extra.mode === 'deep_analysis' ? '深度诊断' : '通用问答'}
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
                          {item.extra?.deepDiagnosis && (
                            <div style={{ marginTop: 10 }}>
                              <Divider style={{ margin: '8px 0' }} />
                              <Text type="secondary" style={{ fontSize: 12 }}>多Agent过程：</Text>
                              <div style={{ marginTop: 6 }}>
                                <Space size={[4, 6]} wrap>
                                  {item.extra.deepDiagnosis.status && <Tag color="blue">状态: {item.extra.deepDiagnosis.status}</Tag>}
                                  {typeof item.extra.deepDiagnosis.iterations === 'number' && <Tag>迭代: {item.extra.deepDiagnosis.iterations}</Tag>}
                                  {typeof item.extra.deepDiagnosis.durationSeconds === 'number' && <Tag>耗时: {item.extra.deepDiagnosis.durationSeconds.toFixed(2)}s</Tag>}
                                </Space>
                              </div>
                              {item.extra.deepDiagnosis.matchedSkills && item.extra.deepDiagnosis.matchedSkills.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  <Text type="secondary" style={{ fontSize: 12 }}>命中技能：</Text>
                                  <div style={{ marginTop: 4 }}>
                                    <Space size={[4, 6]} wrap>
                                      {item.extra.deepDiagnosis.matchedSkills.slice(0, 8).map((skill) => (
                                        <Tag key={skill} color="geekblue">{skill}</Tag>
                                      ))}
                                    </Space>
                                  </div>
                                </div>
                              )}
                              {item.extra.deepDiagnosis.tools && item.extra.deepDiagnosis.tools.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  <Text type="secondary" style={{ fontSize: 12 }}>执行工具：</Text>
                                  <div style={{ marginTop: 4 }}>
                                    <Space size={[4, 6]} wrap>
                                      {item.extra.deepDiagnosis.tools.slice(0, 10).map((tool) => (
                                        <Tag key={tool}>{tool}</Tag>
                                      ))}
                                    </Space>
                                  </div>
                                </div>
                              )}
                              {item.extra.deepDiagnosis.warnings && item.extra.deepDiagnosis.warnings.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  <Text type="secondary" style={{ fontSize: 12 }}>降级提示：</Text>
                                  <Paragraph style={{ margin: '4px 0 0', fontSize: 12 }} ellipsis={{ rows: 3, expandable: true }}>
                                    {item.extra.deepDiagnosis.warnings.join('；')}
                                  </Paragraph>
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                  )}
                />
              )}
            </div>

            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={analyzeProblem ? (deepDiagnosis ? '输入问题，执行多Agent深度诊断...' : '输入要分析的运维问题...') : '输入你的问题，和助手直接对话...'}
                autoSize={{ minRows: 1, maxRows: 4 }}
                style={{ flex: 1 }}
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
          </div>
        </Card>
      )}
    </>
  );
};

export default AssistantWidget;
