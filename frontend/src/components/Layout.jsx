import React, { useState } from 'react';
import { Layout as AntLayout, Menu, Button, Space, Dropdown, Tooltip } from 'antd';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import {
  BarChartOutlined,
  ShoppingOutlined,
  DollarOutlined,
  FileTextOutlined,
  AppstoreOutlined,
  BankOutlined,
  LogoutOutlined,
  KeyOutlined,
  UserOutlined,
  DatabaseOutlined,
  UploadOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { useCurrency } from '../contexts/CurrencyContext';

const { Header, Sider, Content } = AntLayout;

const navItems = [
  { key: '/', icon: <DatabaseOutlined />, label: 'Data' },
  { key: '/charts', icon: <BarChartOutlined />, label: 'Charts' },
  { key: '/product-cost', icon: <ShoppingOutlined />, label: 'Product Cost' },
  { key: '/profit-loss', icon: <DollarOutlined />, label: 'Profit & Loss' },
  { key: '/product-catalog', icon: <AppstoreOutlined />, label: 'Product Catalog' },
  { key: '/bank-account', icon: <BankOutlined />, label: 'Bank Account' },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, signOut } = useAuth();
  const { currency, toggle } = useCurrency();

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: collapsed ? 14 : 18,
            fontWeight: 600,
          }}
        >
          {collapsed ? '📊' : 'Etsy Dashboard'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          mode="inline"
          items={navItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header style={{ padding: '0 24px', background: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 16, fontWeight: 500 }}>Etsy Business Dashboard</div>
          <Space size={12}>
            <Tooltip title={`Switch to ${currency === 'USD' ? 'VND (₫)' : 'USD ($)'}`}>
              <Button
                icon={<SwapOutlined />}
                onClick={toggle}
                style={{
                  fontWeight: 600,
                  minWidth: 72,
                  borderColor: currency === 'USD' ? '#1890ff' : '#52c41a',
                  color: currency === 'USD' ? '#1890ff' : '#52c41a',
                }}
              >
                {currency === 'USD' ? '$ USD' : '₫ VND'}
              </Button>
            </Tooltip>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'change-password',
                  icon: <KeyOutlined />,
                  label: 'Đổi mật khẩu',
                  onClick: () => navigate('/change-password'),
                },
                { type: 'divider' },
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: 'Đăng xuất',
                  danger: true,
                  onClick: signOut,
                },
              ],
            }}
            trigger={['click']}
          >
            <Button type="text" icon={<UserOutlined />} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: '#666' }}>{user?.email}</span>
            </Button>
          </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, background: '#fff' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
