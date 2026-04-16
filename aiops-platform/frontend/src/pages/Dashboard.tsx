import { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Spin, message } from 'antd';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';

import { logsApi } from '../services/api';
import type { Log, LogStats } from '../types';

const Dashboard = () => {
  const [stats, setStats] = useState<LogStats | null>(null);
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(false);
  const [trendData] = useState<{ time: string; count: number }[]>([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsData, logsData] = await Promise.all([
        logsApi.getStats(),
        logsApi.getLogs({ limit: 10 }),
      ]);
      setStats(statsData);
      setLogs(logsData);
    } catch (error) {
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (level: string) => {
        const color = { ERROR: 'red', WARN: 'orange', INFO: 'blue', DEBUG: 'gray' }[level] || 'default';
        return <Tag color={color}>{level}</Tag>;
      },
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      className: 'log-content',
    },
    {
      title: '异常',
      dataIndex: 'is_anomaly',
      key: 'is_anomaly',
      width: 80,
      render: (isAnomaly: boolean, record: Log) => 
        isAnomaly ? (
          <Tag color="red" className="anomaly-tag">
            异常 ({record.anomaly_score?.toFixed(2)})
          </Tag>
        ) : (
          <Tag color="green">正常</Tag>
        ),
    },
  ];

  const getTrendOption = () => ({
    title: { text: '异常趋势', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: trendData.map(d => d.time),
    },
    yAxis: { type: 'value' },
    series: [{
      data: trendData.map(d => d.count),
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.3 },
    }],
  });

  const getLevelOption = () => ({
    title: { text: '日志级别分布', left: 'center' },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: stats
        ? Object.entries(stats.level_distribution).map(([name, value]) => ({ name, value }))
        : [],
    }],
  });

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />;
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card>
            <Statistic title="今日日志总数" value={stats?.total_logs || 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic 
              title="异常数量" 
              value={stats?.anomaly_count || 0} 
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic 
              title="异常率" 
              value={stats ? (stats.anomaly_rate * 100).toFixed(2) : 0} 
              suffix="%" 
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={16}>
          <Card>
            <ReactECharts option={getTrendOption()} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <ReactECharts option={getLevelOption()} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      <Card title="最新日志" style={{ marginTop: 16 }}>
        <Table 
          columns={columns} 
          dataSource={logs} 
          rowKey="id" 
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
};

export default Dashboard;
