import type { ReactNode } from 'react';
import { Space, Tag, Typography } from 'antd';

const { Title, Paragraph, Text } = Typography;

interface AlertSectionHeaderProps {
  title: string;
  description: string;
  tag?: string;
  extra?: ReactNode;
}

const AlertSectionHeader = ({ title, description, tag, extra }: AlertSectionHeaderProps) => {
  return (
    <div
      style={{
        marginBottom: 16,
        padding: '18px 20px',
        borderRadius: 12,
        background: 'linear-gradient(135deg, #f0f7ff 0%, #fafcff 100%)',
        border: '1px solid #d6e4ff',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 16,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ minWidth: 260, flex: 1 }}>
        <Space align="center" size={10} wrap>
          <Title level={4} style={{ margin: 0 }}>
            {title}
          </Title>
          {tag && <Tag color="blue">{tag}</Tag>}
        </Space>
        <Paragraph style={{ margin: '8px 0 0', color: '#595959', maxWidth: 760 }}>
          {description}
        </Paragraph>
      </div>
      {extra && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Text type="secondary">快捷操作</Text>
          {extra}
        </div>
      )}
    </div>
  );
};

export default AlertSectionHeader;
