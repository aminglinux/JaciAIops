import { useState, useEffect } from 'react';
import { Card, Input, Button, Tag, Steps, Spin, message, Typography, Collapse, Descriptions, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { agentApi } from '../services/api';
import type { AgentTask } from '../types';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

const Diagnose = () => {
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState<AgentTask | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (polling && currentTask && currentTask.status === 'processing') {
      interval = setInterval(async () => {
        try {
          const task = await agentApi.getTaskStatus(currentTask.task_id);
          setCurrentTask(task);
          if (task.status !== 'processing') {
            setPolling(false);
          }
        } catch (error) {
          message.error('获取任务状态失败');
          setPolling(false);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [polling, currentTask]);

  const handleSubmit = async () => {
    if (!input.trim()) {
      message.warning('请输入故障描述');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/multi-agent/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: input }),
      });

      if (!response.ok) {
        throw new Error('请求失败');
      }

      const data = await response.json();
      
      const dynamicExecution = data.stages?.dynamic_execution;
      const executionHistory = dynamicExecution?.execution_history || [];
      
      const diagnosisPlan = executionHistory.find(
        (h: any) => h.tool === 'save_diagnosis_plan'
      )?.result?.plan;
      
      const executionOutputs = executionHistory
        .filter((h: any) => h.tool === 'execute_command')
        .map((h: any) => ({
          command: h.args?.command,
          output: h.result?.output,
          success: h.result?.success,
          target_host: h.result?.target_host,
        }));
      
      const savedOutputs = executionHistory
        .filter((h: any) => h.tool === 'save_execution_output')
        .map((h: any) => h.result);
      
      setCurrentTask({
        task_id: 'multi-agent-' + Date.now(),
        user_input: input,
        status: data.stages?.dynamic_execution?.status === 'completed' ? 'completed' : 'processing',
        intent_data: data.stages?.intent_parsing || null,
        analysis_report: data.stages?.observability_analysis || {
          analysis_report: data.raw_response || '',
          execution_history: executionHistory,
        },
        knowledge_context: data.stages?.knowledge_query || {
          knowledge_report: diagnosisPlan?.reasoning || '',
        },
        decision: data.final_decision || null,
        action_result: data.execution_result || null,
        created_at: data.start_time,
        updated_at: data.end_time,
        warning_cleared: data.warning_cleared || false,
        ansible_playbook: data.stages?.ansible_playbook || null,
        server_status_check: data.stages?.server_status_check || null,
        mode: data.mode,
        iterations: dynamicExecution?.iterations,
        diagnosis_plan: diagnosisPlan,
        execution_outputs: executionOutputs,
        saved_outputs: savedOutputs,
        raw_response: data.raw_response,
      });
      
      message.success('诊断完成');
    } catch (error) {
      message.error('诊断失败');
    } finally {
      setLoading(false);
    }
  };

  const getCurrentStep = () => {
    if (!currentTask) return -1;
    if (currentTask.status === 'pending') return 0;
    if (currentTask.status === 'processing') {
      if (currentTask.intent_data) return 1;
      return 0;
    }
    if (currentTask.status === 'completed') return 4;
    if (currentTask.status === 'failed') return -1;
    return 0;
  };

  const getRiskColor = (risk: string) => {
    const colors: Record<string, string> = { HIGH: 'red', MEDIUM: 'orange', LOW: 'green' };
    return colors[risk] || 'default';
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

  const openIncidentLogs = (sourceType: string = 'local') => {
    const serviceName = currentTask?.intent_data?.entities?.service;
    const params = new URLSearchParams();
    params.set('incident', '1');
    params.set('minutes', '30');
    params.set('source', sourceType);
    if (serviceName) {
      params.set('service', serviceName);
    }
    navigate(`/logs?${params.toString()}`);
  };

  return (
    <div>
      <Card title="故障诊断" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="描述故障现象，例如：订单服务最近响应很慢，经常超时"
            autoSize={{ minRows: 2, maxRows: 4 }}
            style={{ flex: 1 }}
          />
          <Button 
            type="primary" 
            icon={<SendOutlined />} 
            onClick={handleSubmit}
            loading={loading}
            style={{ height: 'auto' }}
          >
            诊断
          </Button>
        </Space.Compact>
      </Card>

      {currentTask && (
        <Card style={{ marginBottom: 16 }}>
          <Steps
            current={getCurrentStep()}
            status={currentTask.status === 'failed' ? 'error' : 'process'}
            items={[
              { title: '意图识别', description: 'Intent Parse Agent' },
              { title: '观测分析', description: 'Observability Agent' },
              { title: '知识检索', description: 'Knowledge Agent' },
              { title: '决策生成', description: 'Master Agent' },
              { title: '执行方案', description: 'Action Agent' },
            ]}
          />
        </Card>
      )}

      {currentTask && currentTask.status === 'completed' && (
        <>
          {currentTask.warning_cleared && (
            <Card style={{ marginBottom: 16, backgroundColor: '#f6ffed', borderColor: '#b7eb8f' }}>
              <div style={{ textAlign: 'center', padding: 20 }}>
                <Title level={3} style={{ color: '#52c41a', marginBottom: 16 }}>✅ 警告已解除</Title>
                <Paragraph style={{ fontSize: 16 }}>
                  {currentTask.decision?.action_plan || '服务器状态检查完成，未发现异常'}
                </Paragraph>
              </div>
            </Card>
          )}
          
          <Collapse defaultActiveKey={['1', '2', '3', '4', '5', '6', '7']}>
            <Panel header="意图识别结果" key="1">
              {currentTask.intent_data && (
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="意图">
                    <Tag color={getIntentColor(currentTask.intent_data.intent)}>
                      {currentTask.intent_data.intent}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    <Tag color={currentTask.intent_data.confidence === 'HIGH' ? 'green' : 'orange'}>
                      {currentTask.intent_data.confidence}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="服务">{currentTask.intent_data.entities.service}</Descriptions.Item>
                  <Descriptions.Item label="症状">{currentTask.intent_data.entities.symptom}</Descriptions.Item>
                  <Descriptions.Item label="时间范围">{currentTask.intent_data.entities.time_range}</Descriptions.Item>
                  <Descriptions.Item label="标准化查询">{currentTask.intent_data.normalized_query}</Descriptions.Item>
                </Descriptions>
              )}
              <div style={{ marginTop: 16 }}>
                <Space wrap>
                  <Button onClick={() => openIncidentLogs('local')}>查看本地故障日志</Button>
                  <Button onClick={() => openIncidentLogs('elasticsearch')}>查看 Elasticsearch 故障日志</Button>
                  <Button onClick={() => openIncidentLogs('loki')}>查看 Loki 故障日志</Button>
                </Space>
              </div>
            </Panel>

            {currentTask.ansible_playbook && (
              <Panel header="生成的 Ansible Playbook" key="6">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="目标主机">{currentTask.ansible_playbook.target_host}</Descriptions.Item>
                  <Descriptions.Item label="症状">{currentTask.ansible_playbook.symptoms?.join(', ')}</Descriptions.Item>
                  <Descriptions.Item label="检查指标">{currentTask.ansible_playbook.metrics?.join(', ')}</Descriptions.Item>
                </Descriptions>
              </Panel>
            )}

            {currentTask.server_status_check && (
              <Panel header="服务器状态检查结果" key="7">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="检查状态">
                    <Tag color={currentTask.server_status_check.success ? 'green' : 'red'}>
                      {currentTask.server_status_check.success ? '成功' : '失败'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="警告状态">
                    <Tag color={currentTask.server_status_check.warning_cleared ? 'green' : 'orange'}>
                      {currentTask.server_status_check.warning_cleared ? '已解除' : '存在异常'}
                    </Tag>
                  </Descriptions.Item>
                  {currentTask.server_status_check.memory_usage !== undefined && (
                    <Descriptions.Item label="内存使用率">
                      <Tag color={currentTask.server_status_check.memory_usage > 80 ? 'red' : currentTask.server_status_check.memory_usage > 60 ? 'orange' : 'green'}>
                        {currentTask.server_status_check.memory_usage}%
                      </Tag>
                    </Descriptions.Item>
                  )}
                  {currentTask.server_status_check.cpu_usage !== undefined && (
                    <Descriptions.Item label="CPU 负载">{currentTask.server_status_check.cpu_usage}</Descriptions.Item>
                  )}
                  {currentTask.server_status_check.disk_usage !== undefined && (
                    <Descriptions.Item label="磁盘使用率">{currentTask.server_status_check.disk_usage}%</Descriptions.Item>
                  )}
                  {currentTask.server_status_check.shm_usage !== undefined && (
                    <Descriptions.Item label="/dev/shm 使用率">
                      <Tag color={currentTask.server_status_check.shm_usage >= 100 ? 'red' : currentTask.server_status_check.shm_usage >= 90 ? 'orange' : 'green'}>
                        {currentTask.server_status_check.shm_usage}%
                      </Tag>
                    </Descriptions.Item>
                  )}
                </Descriptions>
                {currentTask.server_status_check.anomalies && currentTask.server_status_check.anomalies.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <Text strong>发现的异常：</Text>
                    <ul>
                      {currentTask.server_status_check.anomalies.map((anomaly, index) => (
                        <li key={index} style={{ color: '#ff4d4f' }}>{anomaly}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </Panel>
            )}

            {currentTask.mode === 'dynamic' && currentTask.diagnosis_plan && (
              <Panel header={`诊断计划 (${currentTask.iterations} 次迭代)`} key="8">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="计划名称">{currentTask.diagnosis_plan.plan_name}</Descriptions.Item>
                  <Descriptions.Item label="检查类型">
                    <Tag color="blue">{currentTask.diagnosis_plan.check_type}</Tag>
                  </Descriptions.Item>
                </Descriptions>
                <div style={{ marginTop: 16 }}>
                  <Text strong>选择原因：</Text>
                  <Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
                    {currentTask.diagnosis_plan.reasoning}
                  </Paragraph>
                </div>
                <div style={{ marginTop: 16 }}>
                  <Text strong>执行命令：</Text>
                  <ul style={{ marginTop: 8 }}>
                    {currentTask.diagnosis_plan.commands.map((cmd, index) => (
                      <li key={index}>
                        <Tag color="geekblue">{cmd}</Tag>
                      </li>
                    ))}
                  </ul>
                </div>
              </Panel>
            )}

            {currentTask.execution_outputs && currentTask.execution_outputs.length > 0 && (
              <Panel header="命令执行结果" key="9">
                {currentTask.execution_outputs.map((exec, index) => (
                  <Card key={index} size="small" style={{ marginBottom: 16 }} title={
                    <Space>
                      <Tag color={exec.success ? 'green' : 'red'}>
                        {exec.success ? '成功' : '失败'}
                      </Tag>
                      <Text code>{exec.command}</Text>
                    </Space>
                  }>
                    <Paragraph style={{ 
                      whiteSpace: 'pre-wrap', 
                      fontFamily: 'monospace',
                      backgroundColor: '#f5f5f5',
                      padding: 12,
                      borderRadius: 4,
                      maxHeight: 300,
                      overflow: 'auto'
                    }}>
                      {exec.output || '无输出'}
                    </Paragraph>
                  </Card>
                ))}
              </Panel>
            )}

            {currentTask.saved_outputs && currentTask.saved_outputs.length > 0 && (
              <Panel header="保存的中间文件" key="10">
                <div>
                  {currentTask.saved_outputs.map((item: any, index: number) => (
                    <div key={index} style={{ padding: '8px 0', borderBottom: index < currentTask.saved_outputs!.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                      <Space>
                        <Tag color="green">已保存</Tag>
                        <Text code>{item.saved_to}</Text>
                        {item.command && <Text type="secondary">({item.command})</Text>}
                      </Space>
                    </div>
                  ))}
                </div>
              </Panel>
            )}

            <Panel header="观测分析报告" key="2">
              {currentTask.analysis_report && (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <Space wrap>
                      <Button onClick={() => openIncidentLogs('local')}>关联本地故障日志</Button>
                      <Button onClick={() => openIncidentLogs('elasticsearch')}>关联 Elasticsearch 日志</Button>
                      <Button onClick={() => openIncidentLogs('loki')}>关联 Loki 日志</Button>
                    </Space>
                  </div>
                  <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {currentTask.analysis_report.analysis_report}
                  </Paragraph>
                  {currentTask.analysis_report.metrics_summary && (
                    <Descriptions column={4} size="small" title="关键指标">
                      <Descriptions.Item label="P99延迟">{currentTask.analysis_report.metrics_summary.latency_p99}</Descriptions.Item>
                      <Descriptions.Item label="错误率">{currentTask.analysis_report.metrics_summary.error_rate}</Descriptions.Item>
                      <Descriptions.Item label="CPU">{currentTask.analysis_report.metrics_summary.cpu_usage}</Descriptions.Item>
                      <Descriptions.Item label="内存">{currentTask.analysis_report.metrics_summary.memory_usage}</Descriptions.Item>
                    </Descriptions>
                  )}
                </div>
              )}
            </Panel>

            <Panel header="知识库检索" key="3">
              {currentTask.knowledge_context && (
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                  {currentTask.knowledge_context.knowledge_report}
                </Paragraph>
              )}
            </Panel>

            <Panel header="决策结果" key="4">
              {currentTask.decision && (
                <div>
                  {currentTask.decision.is_final ? (
                    <>
                      <Descriptions column={2} size="small">
                        <Descriptions.Item label="问题类型">
                          <Tag color="blue">{currentTask.decision.problem_type}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="风险等级">
                          <Tag color={getRiskColor(currentTask.decision.risk_level)}>
                            {currentTask.decision.risk_level}
                          </Tag>
                        </Descriptions.Item>
                      </Descriptions>
                      <Paragraph style={{ marginTop: 16 }}>
                        <Text strong>根本原因：</Text>{currentTask.decision.root_cause}
                      </Paragraph>
                      <Paragraph>
                        <Text strong>影响范围：</Text>{currentTask.decision.impact}
                      </Paragraph>
                      <Paragraph>
                        <Text strong>建议操作：</Text>{currentTask.decision.recommendation}
                      </Paragraph>
                    </>
                  ) : (
                    <>
                      <Descriptions column={2} size="small">
                        <Descriptions.Item label="根因">{currentTask.decision.root_cause_summary}</Descriptions.Item>
                        <Descriptions.Item label="决策">
                          <Tag color={currentTask.decision.decision === 'EXECUTE_FIX' ? 'orange' : 'blue'}>
                            {currentTask.decision.decision}
                          </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="风险等级">
                          <Tag color={getRiskColor(currentTask.decision.risk_level)}>
                            {currentTask.decision.risk_level}
                          </Tag>
                        </Descriptions.Item>
                      </Descriptions>
                      <Paragraph style={{ marginTop: 16, whiteSpace: 'pre-wrap' }}>
                        <Text strong>执行计划：</Text>{'\n'}{currentTask.decision.action_plan}
                      </Paragraph>
                      <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                        <Text strong>推理过程：</Text>{'\n'}{currentTask.decision.reasoning}
                      </Paragraph>
                    </>
                  )}
                </div>
              )}
            </Panel>

            {currentTask.action_result && (
              <Panel header="执行指令" key="5">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="工具">{currentTask.action_result.tool_name}</Descriptions.Item>
                  <Descriptions.Item label="模板">{currentTask.action_result.template_name}</Descriptions.Item>
                  <Descriptions.Item label="风险评估">
                    <Tag color={getRiskColor(currentTask.action_result.risk_assessment)}>
                      {currentTask.action_result.risk_assessment}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="需要审批">
                    <Tag color={currentTask.action_result.requires_approval ? 'red' : 'green'}>
                      {currentTask.action_result.requires_approval ? '是' : '否'}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>
                <Paragraph style={{ marginTop: 16 }}>
                  <Text strong>执行说明：</Text>{currentTask.action_result.execution_note}
                </Paragraph>
              </Panel>
            )}
          </Collapse>
        </>
      )}

      {currentTask && currentTask.status === 'processing' && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <Paragraph style={{ marginTop: 16 }}>正在分析中，请稍候...</Paragraph>
        </Card>
      )}

    </div>
  );
};

export default Diagnose;
