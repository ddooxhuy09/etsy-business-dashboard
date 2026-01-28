import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined, DashboardOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';

const { Title, Text } = Typography;

export default function Login() {
  const [loading, setLoading] = useState(false);
  const { signIn } = useAuth();
  const navigate = useNavigate();

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const data = await signIn(values.email, values.password);
      // Đợi session được persist vào localStorage trước khi redirect
      if (data?.session?.access_token) {
        // Verify session is available
        await new Promise(resolve => setTimeout(resolve, 100));
        const { data: { session: verifySession } } = await supabase.auth.getSession();
        if (verifySession?.access_token) {
          message.success('Đăng nhập thành công!');
          navigate('/');
        } else {
          message.error('Session chưa sẵn sàng. Vui lòng thử lại.');
        }
      } else {
        message.error('Không nhận được session từ Supabase. Vui lòng thử lại.');
      }
    } catch (error) {
      message.error(error.message || 'Đăng nhập thất bại. Vui lòng kiểm tra email và mật khẩu.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: '20px',
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%', textAlign: 'center' }}>
          <Space>
            <DashboardOutlined style={{ fontSize: 32, color: '#1890ff' }} />
            <Title level={2} style={{ margin: 0 }}>
              Etsy Dashboard
            </Title>
          </Space>
          <Text type="secondary">Đăng nhập để truy cập dashboard</Text>

          <Form
            name="login"
            onFinish={onFinish}
            autoComplete="off"
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="email"
              rules={[
                { required: true, message: 'Vui lòng nhập email!' },
                { type: 'email', message: 'Email không hợp lệ!' },
              ]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="Email"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: 'Vui lòng nhập mật khẩu!' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Mật khẩu"
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                style={{ height: 40 }}
              >
                Đăng nhập
              </Button>
            </Form.Item>
            <Form.Item style={{ marginBottom: 0, textAlign: 'center' }}>
              <Link to="/forgot-password">Quên mật khẩu?</Link>
            </Form.Item>
          </Form>
        </Space>
      </Card>
    </div>
  );
}
