import { useEffect, useState } from 'react';
import { Card, Typography, Upload, Button, Alert, Space, message, Statistic, Row, Col } from 'antd';
import { InboxOutlined, UploadOutlined, FileTextOutlined, PlayCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';

import { logsApi, wsUrl } from '../services/api';
import type { LogStats } from '../types';

const { Title, Paragraph, Text } = Typography;

const LogUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  const fetchData = async () => {
    setLoadingStats(true);
    try {
      const statsData = await logsApi.getStats();
      setStats(statsData);
      message.success('日志统计已刷新');
    } catch (error) {
      message.error('刷新数据失败');
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, []);

  useEffect(() => {
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [ws]);

  const startSimulation = () => {
    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      websocket.send('start');
      setSimulating(true);
      message.success('开始模拟日志流');
    };

    websocket.onmessage = () => {
      setStats((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          total_logs: prev.total_logs + 1,
          anomaly_count: prev.anomaly_count,
          anomaly_rate: prev.total_logs + 1 > 0 ? prev.anomaly_count / (prev.total_logs + 1) : 0,
        };
      });
    };

    websocket.onerror = () => {
      message.error('WebSocket连接失败');
      setSimulating(false);
    };

    websocket.onclose = () => {
      setSimulating(false);
      setWs(null);
    };

    setWs(websocket);
  };

  const stopSimulation = () => {
    if (ws) {
      ws.send('stop');
      ws.close();
      setWs(null);
    }
    setSimulating(false);
    message.info('停止模拟');
  };

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.log,.txt',
    showUploadList: false,
    multiple: false,
    beforeUpload: async (file) => {
      setUploading(true);
      try {
        const result = await logsApi.uploadFile(file);
        message.success(result.message || `上传成功: ${result.filename}`);
      } catch (error) {
        message.error('上传失败，请稍后重试');
      } finally {
        setUploading(false);
      }
      return false;
    },
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="日志上传"
        description="支持上传 `.log` 或 `.txt` 文件；同时可在这里启动模拟日志流或刷新统计数据。上传完成后，可前往“日志查询”查看内容并继续分析。"
      />

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="今日日志总数" value={stats?.total_logs || 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="异常数量" value={stats?.anomaly_count || 0} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={loadingStats}>
            <Statistic title="异常率" value={stats ? (stats.anomaly_rate * 100).toFixed(2) : 0} suffix="%" />
          </Card>
        </Col>
      </Row>

      <Card>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div>
            <Title level={4} style={{ marginBottom: 8 }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              上传日志文件
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              建议上传单个服务或单次故障期间采集的日志，便于后续检索和诊断。
            </Paragraph>
          </div>

          <Upload.Dragger {...uploadProps} disabled={uploading}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽日志文件到这里上传</p>
            <p className="ant-upload-hint">
              仅支持 `.log`、`.txt`，一次上传一个文件
            </p>
          </Upload.Dragger>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <Text type="secondary">上传后系统会自动入库，随后可在“日志查询”页面进行检索。</Text>
            <Upload {...uploadProps} disabled={uploading}>
              <Button icon={<UploadOutlined />} loading={uploading} type="primary">
              选择文件上传
              </Button>
            </Upload>
          </div>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Button
              type={simulating ? 'default' : 'primary'}
              icon={simulating ? <StopOutlined /> : <PlayCircleOutlined />}
              onClick={simulating ? stopSimulation : startSimulation}
              danger={simulating}
            >
              {simulating ? '停止模拟' : '开始模拟'}
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchData()} loading={loadingStats}>
              刷新数据
            </Button>
          </div>
        </Space>
      </Card>
    </Space>
  );
};

export default LogUpload;
