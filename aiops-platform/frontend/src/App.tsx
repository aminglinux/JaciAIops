import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Dropdown, Avatar, Space, Spin } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  BugOutlined,
  ApiOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
} from '@ant-design/icons';

import Dashboard from './pages/Dashboard';
import LogList from './pages/LogList';
import Diagnose from './pages/Diagnose';
import KnowledgeGraph from './pages/KnowledgeGraph';
import ModelHub from './pages/ModelHub';
import Login from './pages/Login';
import Register from './pages/Register';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import AssistantWidget from './components/AssistantWidget';

const { Header, Content, Sider } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘', path: '/', permission: null },
  { key: '/logs', icon: <FileTextOutlined />, label: '日志列表', path: '/logs', permission: 'logs:view' },
  { key: '/diagnose', icon: <BugOutlined />, label: '故障诊断', path: '/diagnose', permission: 'diagnose:view' },
  { key: '/knowledge', icon: <ApiOutlined />, label: '知识图谱', path: '/knowledge', permission: 'knowledge:view' },
  { key: '/models', icon: <SettingOutlined />, label: '模型管理', path: '/models', permission: null, adminOnly: true },
];

const AppContent = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const { user, loading, logout, isAdmin, hasPermission } = useAuth();
  const isLoginPage = location.pathname === '/login';
  const isRegisterPage = location.pathname === '/register';

  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isLoginPage) {
    return <Login />;
  }

  if (isRegisterPage) {
    return <Register />;
  }

  const filteredMenuItems = menuItems.filter(item => {
    if (item.adminOnly && !isAdmin) return false;
    if (item.permission && !hasPermission(item.permission) && !isAdmin) return false;
    return true;
  });

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: `角色: ${user?.roles?.join(', ') || '用户'}`,
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 32, margin: 16, background: 'rgba(255, 255, 255, 0.2)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: '#fff', fontWeight: 'bold', fontSize: collapsed ? 12 : 16 }}>
            {collapsed ? 'AI' : 'AIOps'}
          </span>
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          mode="inline"
          items={filteredMenuItems.map(item => ({
            key: item.key,
            icon: item.icon,
            label: <Link to={item.path}>{item.label}</Link>,
          }))}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 24px', background: '#fff', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 500 }}>
            AIOps 智能运维平台
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {user?.scope && user.scope.length > 0 && (
              <span style={{ color: '#666', fontSize: 12 }}>
                负责系统: {user.scope.join(', ')}
              </span>
            )}
            <Dropdown
              menu={{
                items: userMenuItems,
                onClick: ({ key }) => {
                  if (key === 'logout') {
                    logout();
                    navigate('/login');
                  }
                },
              }}
            >
              <Space style={{ cursor: 'pointer' }}>
                <Avatar icon={<UserOutlined />} style={{ backgroundColor: isAdmin ? '#f56a00' : '#1890ff' }} />
                <span>{user?.username}</span>
                {isAdmin && <span style={{ color: '#f56a00', fontSize: 12 }}>[管理员]</span>}
              </Space>
            </Dropdown>
          </div>
        </Header>
        <Content style={{ margin: '16px' }}>
          <div style={{ padding: 24, background: '#fff', borderRadius: 8, minHeight: 'calc(100vh - 112px)' }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/logs" element={
                <PrivateRoute requiredPermission="logs:view">
                  <LogList />
                </PrivateRoute>
              } />
              <Route path="/diagnose" element={
                <PrivateRoute requiredPermission="diagnose:view">
                  <Diagnose />
                </PrivateRoute>
              } />
              <Route path="/knowledge" element={
                <PrivateRoute requiredPermission="knowledge:view">
                  <KnowledgeGraph />
                </PrivateRoute>
              } />
              <Route path="/qa" element={<Navigate to="/" replace />} />
              <Route path="/models" element={
                <PrivateRoute requireAdmin>
                  <ModelHub />
                </PrivateRoute>
              } />
            </Routes>
          </div>
        </Content>
        {(isAdmin || hasPermission('qa:view')) && <AssistantWidget />}
      </Layout>
    </Layout>
  );
};

const App = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/*" element={<AppContent />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
