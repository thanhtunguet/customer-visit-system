import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Select } from 'antd';
import { UserOutlined, LockOutlined, ShopOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import { LoginRequest, UserRole } from '../types/api';

const { Title, Text } = Typography;

interface ApiError {
  response?: {
    status?: number;
    data?: {
      detail?: string | Array<{
        loc: string[];
        msg: string;
      }>;
    };
  };
  message?: string;
}

export const LoginForm: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [selectedRole, setSelectedRole] = useState<UserRole>(UserRole.TENANT_ADMIN);

  const handleSubmit = async (values: LoginRequest) => {
    setLoading(true);
    setFieldErrors({});

    try {
      // For system admin, don't require tenant_id
      const loginData = selectedRole === UserRole.SYSTEM_ADMIN 
        ? { ...values, tenant_id: undefined } 
        : values;
      
      await apiClient.login(loginData);
      navigate('/dashboard');
    } catch (err: unknown) {
      console.log('Login error:', err);
      console.log('Error response:', err.response);
      console.log('Error status:', err.response?.status);
      console.log('Error data:', err.response?.data);
      
      const errorData = (err as ApiError)?.response?.data;
      const status = (err as ApiError)?.response?.status;
      
      // Handle different error scenarios
      if (status === 401) {
        // Unauthorized - invalid credentials
        setFieldErrors({
          username: 'Invalid username or password',
          password: 'Invalid username or password'
        });
      } else if (status === 422) {
        // Validation error - check if it's field-specific
        if (errorData?.detail) {
          const errors: Record<string, string> = {};
          
          if (Array.isArray(errorData.detail)) {
            // Handle validation errors array
            errorData.detail.forEach((error) => {
              if (error.loc && error.msg) {
                const field = error.loc[error.loc.length - 1]; // Get last part of location
                errors[field] = error.msg;
              }
            });
          } else if (typeof errorData.detail === 'string') {
            // Handle string detail
            if (errorData.detail.includes('tenant')) {
              errors.tenant_id = 'Invalid tenant ID';
            } else if (errorData.detail.includes('role') || errorData.detail.includes('permission')) {
              errors.role = 'Invalid role or insufficient permissions';
            } else {
              errors.username = errorData.detail;
            }
          }
          
          // If no specific field errors, show general error on username field
          if (Object.keys(errors).length === 0) {
            errors.username = errorData.detail;
          }
          
          setFieldErrors(errors);
        } else {
          setFieldErrors({ username: 'Validation error. Please check your input.' });
        }
      } else if (errorData?.detail) {
        // Other errors with detail message
        setFieldErrors({ username: errorData.detail });
      } else {
        // Generic error
        setFieldErrors({ username: 'Login failed. Please try again.' });
      }
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



        <Form
          form={form}
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
          initialValues={{
            role: UserRole.TENANT_ADMIN,
            tenant_id: 't-dev'
          }}
        >
        <Form.Item
            name="role"
            label="Role"
            rules={[{ required: true, message: 'Please select role!' }]}
            validateStatus={fieldErrors.role ? 'error' : ''}
            help={fieldErrors.role}
          >
            <Select 
              placeholder="Select your role"
              onChange={(value) => {
                setSelectedRole(value);
                // Clear tenant_id when switching to system admin
                if (value === UserRole.SYSTEM_ADMIN) {
                  form.setFieldValue('tenant_id', undefined);
                }
              }}
            >
              <Select.Option value={UserRole.SYSTEM_ADMIN}>System Admin</Select.Option>
              <Select.Option value={UserRole.TENANT_ADMIN}>Tenant Admin</Select.Option>
              <Select.Option value={UserRole.SITE_MANAGER}>Site Manager</Select.Option>
            </Select>
          </Form.Item>
          
          {selectedRole !== UserRole.SYSTEM_ADMIN && (
            <Form.Item
              name="tenant_id"
              label="Tenant ID"
              rules={[{ required: true, message: 'Please input tenant ID!' }]}
              validateStatus={fieldErrors.tenant_id ? 'error' : ''}
              help={fieldErrors.tenant_id}
            >
              <Input
                prefix={<ShopOutlined />}
                placeholder="Enter tenant ID"
              />
            </Form.Item>
          )}

          <Form.Item
            name="username"
            label="Username"
            rules={[{ required: true, message: 'Please input your username!' }]}
            validateStatus={fieldErrors.username ? 'error' : ''}
            help={fieldErrors.username}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="Enter username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="Password"
            rules={[{ required: true, message: 'Please input your password!' }]}
            validateStatus={fieldErrors.password ? 'error' : ''}
            help={fieldErrors.password}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Enter password"
            />
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

        
      </Card>
    </div>
  );
};
