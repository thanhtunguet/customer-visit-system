import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Space, Select, Alert } from 'antd';
import { UserOutlined, LockOutlined, ShopOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import { LoginRequest } from '../types/api';

const { Title, Text } = Typography;

export const LoginForm: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>('tenant_admin');

  const handleSubmit = async (values: LoginRequest) => {
    setLoading(true);
    setError(null);

    try {
      // For system admin, don't require tenant_id
      const loginData = selectedRole === 'system_admin' 
        ? { ...values, tenant_id: undefined } 
        : values;
      
      await apiClient.login(loginData);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-lg">
        <div className="text-center mb-8">
          <Title level={2} className="text-blue-600 mb-2">
            Customer Visits System
          </Title>
          <Text type="secondary">
            Sign in to your account
          </Text>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            className="mb-4"
          />
        )}

        <Form
          form={form}
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
          initialValues={{
            role: 'tenant_admin',
            tenant_id: 't-dev'
          }}
        >
          {selectedRole !== 'system_admin' && (
            <Form.Item
              name="tenant_id"
              label="Tenant ID"
              rules={[{ required: true, message: 'Please input tenant ID!' }]}
            >
              <Input
                prefix={<ShopOutlined />}
                placeholder="Enter tenant ID"
              />
            </Form.Item>
          )}

          <Form.Item
            name="role"
            label="Role"
            rules={[{ required: true, message: 'Please select role!' }]}
          >
            <Select 
              placeholder="Select your role"
              onChange={(value) => {
                setSelectedRole(value);
                // Clear tenant_id when switching to system admin
                if (value === 'system_admin') {
                  form.setFieldValue('tenant_id', undefined);
                }
              }}
            >
              <Select.Option value="system_admin">System Admin</Select.Option>
              <Select.Option value="tenant_admin">Tenant Admin</Select.Option>
              <Select.Option value="site_manager">Site Manager</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item className="mb-0">
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              className="bg-blue-600"
            >
              Sign In
            </Button>
          </Form.Item>
        </Form>

        <div className="mt-6 text-center">
          <Space direction="vertical" size="small">
            <Text type="secondary" className="text-sm">
              Demo Credentials:
            </Text>
            <Text code className="text-xs">
              admin / password / t-dev / tenant_admin
            </Text>
          </Space>
        </div>
      </Card>
    </div>
  );
};