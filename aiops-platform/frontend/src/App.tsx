import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Dropdown, Avatar, Space, Spin } from 'antd';
import type { MenuProps } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  BugOutlined,
  AlertOutlined,
  ApiOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
} from '@ant-design/icons';

import Dashboard from './pages/Dashboard';
import LogList from './pages/LogList';
import LogUpload from './pages/LogUpload';
import LogAnomalyAnalysis from './pages/LogAnomalyAnalysis';
import LogSettings from './pages/LogSettings';
import Diagnose from './pages/Diagnose';
import AlertCenter from './pages/AlertCenter';
import AlertAnalysis from './pages/AlertAnalysis';
import AlertSecuritySettings from './pages/AlertSecuritySettings';
import KnowledgeGraph from './pages/KnowledgeGraph';
import ModelHub from './pages/ModelHub';
import Login from './pages/Login';
import Register from './pages/Register';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import AssistantWidget from './components/AssistantWidget';

const { Header, Content, Sider } = Layout;

interface MenuChildItem {
  key: string;
  label: string;
  path: string;
  permission?: string | null;
  adminOnly?: boolean;
}

interface MenuItemConfig {
  key: string;
  icon: React.ReactNode;
  label: string;
  path?: string;
  permission?: string | null;
  adminOnly?: boolean;
  children?: MenuChildItem[];
}

const menuItems: MenuItemConfig[] = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘', path: '/', permission: null },
  {
    key: '/logs-group',
    icon: <FileTextOutlined />,
    label: '日志中心',
    permission: 'logs:view',
    children: [
      { key: '/logs', label: '日志查询', path: '/logs', permission: 'logs:view' },
      { key: '/logs/upload', label: '日志上传', path: '/logs/upload', permission: 'logs:view' },
      { key: '/logs/anomaly-analysis', label: '异常分析', path: '/logs/anomaly-analysis', permission: 'logs:view' },
      { key: '/logs/settings', label: '日志配置', path: '/logs/settings', adminOnly: true },
    ],
  },
  {
    key: '/alerts-group',
    icon: <AlertOutlined />,
    label: '告警中心',
    permission: 'diagnose:view',
    children: [
      { key: '/alerts', label: '告警事件', path: '/alerts', permission: 'diagnose:view' },
      { key: '/alerts/analyze', label: '手工分析', path: '/alerts/analyze', permission: 'diagnose:view' },
      { key: '/alerts/settings', label: '安全配置', path: '/alerts/settings', adminOnly: true },
    ],
  },
  { key: '/diagnose', icon: <BugOutlined />, label: '故障诊断', path: '/diagnose', permission: 'diagnose:view' },
  { key: '/knowledge', icon: <ApiOutlined />, label: '知识图谱', path: '/knowledge', permission: 'knowledge:view' },
  { key: '/models', icon: <SettingOutlined />, label: '模型管理', path: '/models', permission: null, adminOnly: true },
];

const AppContent = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>([]);
  const { user, loading, logout, isAdmin, hasPermission } = useAuth();
  const isLoginPage = location.pathname === '/login';
  const isRegisterPage = location.pathname === '/register';

  useEffect(() => {
    if (collapsed) {
      setOpenKeys([]);
      return;
    }
    if (location.pathname.startsWith('/logs')) {
      setOpenKeys(['/logs-group']);
      return;
    }
    if (location.pathname.startsWith('/alerts')) {
      setOpenKeys(['/alerts-group']);
    }
  }, [location.pathname, collapsed]);

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

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const filteredMenuItems: MenuItemConfig[] = menuItems
    .map((item) => {
      const children = item.children;
      if (children) {
        const filteredChildren = children.filter((child) => {
          if (child.adminOnly && !isAdmin) return false;
          if (child.permission && !hasPermission(child.permission) && !isAdmin) return false;
          return true;
        });
        if (filteredChildren.length === 0) return null;
        return { ...item, children: filteredChildren };
      }
      if (item.adminOnly && !isAdmin) return null;
      if (item.permission && !hasPermission(item.permission) && !isAdmin) return null;
      return item;
    })
    .filter((item): item is MenuItemConfig => item !== null);

  const menuRenderItems: Required<MenuProps>['items'] = filteredMenuItems.map((item) => {
    if (item.children) {
      return {
        key: item.key,
        icon: item.icon,
        label: item.label,
        children: item.children.map((child) => ({
          key: child.key,
          label: <Link to={child.path}>{child.label}</Link>,
        })),
      };
    }
    return {
      key: item.key,
      icon: item.icon,
      label: <Link to={item.path || '/'}>{item.label}</Link>,
    };
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
          openKeys={openKeys}
          onOpenChange={(keys) => setOpenKeys(keys as string[])}
          mode="inline"
          items={menuRenderItems}
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
              <Route path="/logs/upload" element={
                <PrivateRoute requiredPermission="logs:view">
                  <LogUpload />
                </PrivateRoute>
              } />
              <Route path="/logs/anomaly-analysis" element={
                <PrivateRoute requiredPermission="logs:view">
                  <LogAnomalyAnalysis />
                </PrivateRoute>
              } />
              <Route path="/logs/settings" element={
                <PrivateRoute requireAdmin>
                  <LogSettings />
                </PrivateRoute>
              } />
              <Route path="/diagnose" element={
                <PrivateRoute requiredPermission="diagnose:view">
                  <Diagnose />
                </PrivateRoute>
              } />
              <Route path="/alerts" element={
                <PrivateRoute requiredPermission="diagnose:view">
                  <AlertCenter />
                </PrivateRoute>
              } />
              <Route path="/alerts/analyze" element={
                <PrivateRoute requiredPermission="diagnose:view">
                  <AlertAnalysis />
                </PrivateRoute>
              } />
              <Route path="/alerts/settings" element={
                <PrivateRoute requireAdmin>
                  <AlertSecuritySettings />
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
