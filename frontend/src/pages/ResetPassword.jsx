import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabase';

const { Title, Text } = Typography;

export default function ResetPassword() {
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { updatePassword } = useAuth();

  useEffect(() => {
    const check = async () => {
      const hash = window.location.hash;
      const type = searchParams.get('type') || (hash && new URLSearchParams(hash.slice(1)).get('type'));
      for (let i = 0; i < 5; i++) {
        const { data: { session } } = await supabase.auth.getSession();
        if (type === 'recovery' || session) {
          setReady(true);
          return;
        }
        if (i < 4) await new Promise((r) => setTimeout(r, 150));
      }
      setInvalid(true);
    };
    check();
  }, [searchParams]);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      await updatePassword(values.newPassword);
      message.success('Đặt lại mật khẩu thành công. Đang chuyển tới trang chủ...');
      navigate('/', { replace: true });
    } catch (error) {
      message.error(error.message || 'Đặt lại mật khẩu thất bại.');
    } finally {
      setLoading(false);
    }
  };

  if (invalid) {
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
        <Card style={{ maxWidth: 400, width: '100%', textAlign: 'center' }}>
          <Title level={4}>Link không hợp lệ hoặc đã hết hạn</Title>
          <Text type="secondary">Vui lòng yêu cầu đặt lại mật khẩu mới từ trang quên mật khẩu.</Text>
          <div style={{ marginTop: 16 }}>
            <Link to="/forgot-password">
              <Button type="primary">Quên mật khẩu</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  if (!ready) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}
      >
        <Text>Đang tải...</Text>
      </div>
    );
  }

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
          <LockOutlined style={{ fontSize: 40, color: '#1890ff' }} />
          <Title level={2} style={{ margin: 0 }}>
            Đặt lại mật khẩu
          </Title>
          <Text type="secondary">Nhập mật khẩu mới cho tài khoản của bạn.</Text>

          <Form
            name="reset"
            onFinish={onFinish}
            autoComplete="off"
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="newPassword"
              rules={[
                { required: true, message: 'Vui lòng nhập mật khẩu mới!' },
                { min: 6, message: 'Mật khẩu tối thiểu 6 ký tự!' },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Mật khẩu mới"
              />
            </Form.Item>
            <Form.Item
              name="confirm"
              dependencies={['newPassword']}
              rules={[
                { required: true, message: 'Vui lòng xác nhận mật khẩu!' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('newPassword') === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error('Xác nhận mật khẩu không khớp!'));
                  },
                }),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Xác nhận mật khẩu mới"
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
                Đặt lại mật khẩu
              </Button>
            </Form.Item>
          </Form>
        </Space>
      </Card>
    </div>
  );
}
