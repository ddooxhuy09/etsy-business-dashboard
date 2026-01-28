import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, MailOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text } = Typography;

export default function ForgotPassword() {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const { resetPasswordForEmail } = useAuth();

  const onFinish = async (values) => {
    setLoading(true);
    try {
      await resetPasswordForEmail(values.email);
      setSent(true);
      message.success('Đã gửi link đặt lại mật khẩu. Vui lòng kiểm tra email.');
    } catch (error) {
      message.error(error.message || 'Gửi email thất bại. Vui lòng thử lại.');
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
          <MailOutlined style={{ fontSize: 40, color: '#1890ff' }} />
          <Title level={2} style={{ margin: 0 }}>
            Quên mật khẩu
          </Title>
          <Text type="secondary">
            Nhập email đăng ký. Chúng tôi sẽ gửi link đặt lại mật khẩu.
          </Text>

          {sent ? (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Text>Kiểm tra hộp thư (và thư mục spam) rồi bấm link để đặt lại mật khẩu.</Text>
              <Link to="/login">
                <Button type="primary" block>
                  Về trang đăng nhập
                </Button>
              </Link>
            </Space>
          ) : (
            <Form
              name="forgot"
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
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                  style={{ height: 40 }}
                >
                  Gửi link đặt lại mật khẩu
                </Button>
              </Form.Item>
              <Form.Item style={{ marginBottom: 0, textAlign: 'center' }}>
                <Link to="/login">Quay lại đăng nhập</Link>
              </Form.Item>
            </Form>
          )}
        </Space>
      </Card>
    </div>
  );
}
