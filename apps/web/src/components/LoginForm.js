import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Form, Input, Button, Card, Typography, Select } from 'antd';
import { UserOutlined, LockOutlined, ShopOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import { UserRole } from '../types/api';
const { Title, Text } = Typography;
export const LoginForm = () => {
    const [form] = Form.useForm();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [fieldErrors, setFieldErrors] = useState({});
    const [selectedRole, setSelectedRole] = useState(UserRole.TENANT_ADMIN);
    const handleSubmit = async (values) => {
        setLoading(true);
        setFieldErrors({});
        try {
            // For system admin, don't require tenant_id
            const loginData = selectedRole === UserRole.SYSTEM_ADMIN
                ? { ...values, tenant_id: undefined }
                : values;
            await apiClient.login(loginData);
            navigate('/dashboard');
        }
        catch (err) {
            const apiError = err;
            console.log('Login error:', err);
            console.log('Error response:', apiError.response);
            console.log('Error status:', apiError.response?.status);
            console.log('Error data:', apiError.response?.data);
            const errorData = err?.response?.data;
            const status = err?.response?.status;
            // Handle different error scenarios
            if (status === 401) {
                // Unauthorized - invalid credentials
                setFieldErrors({
                    username: 'Invalid username or password',
                    password: 'Invalid username or password'
                });
            }
            else if (status === 422) {
                // Validation error - check if it's field-specific
                if (errorData?.detail) {
                    const errors = {};
                    if (Array.isArray(errorData.detail)) {
                        // Handle validation errors array
                        errorData.detail.forEach((error) => {
                            if (error.loc && error.msg) {
                                const field = error.loc[error.loc.length - 1]; // Get last part of location
                                errors[field] = error.msg;
                            }
                        });
                    }
                    else if (typeof errorData.detail === 'string') {
                        // Handle string detail
                        if (errorData.detail.includes('tenant')) {
                            errors.tenant_id = 'Invalid tenant ID';
                        }
                        else if (errorData.detail.includes('role') || errorData.detail.includes('permission')) {
                            errors.role = 'Invalid role or insufficient permissions';
                        }
                        else {
                            errors.username = typeof errorData.detail === 'string' ? errorData.detail : 'Login error';
                        }
                    }
                    // If no specific field errors, show general error on username field
                    if (Object.keys(errors).length === 0) {
                        errors.username = typeof errorData.detail === 'string' ? errorData.detail : 'Validation error';
                    }
                    setFieldErrors(errors);
                }
                else {
                    setFieldErrors({ username: 'Validation error. Please check your input.' });
                }
            }
            else if (errorData?.detail) {
                // Other errors with detail message
                setFieldErrors({ username: typeof errorData.detail === 'string' ? errorData.detail : 'Login error' });
            }
            else {
                // Generic error
                setFieldErrors({ username: 'Login failed. Please try again.' });
            }
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsx("div", { className: "min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4", children: _jsxs(Card, { className: "w-full max-w-md shadow-lg", children: [_jsxs("div", { className: "text-center mb-8", children: [_jsx(Title, { level: 2, className: "text-blue-600 mb-2", children: "Customer Visits System" }), _jsx(Text, { type: "secondary", children: "Sign in to your account" })] }), _jsxs(Form, { form: form, name: "login", onFinish: handleSubmit, layout: "vertical", size: "large", initialValues: {
                        role: UserRole.TENANT_ADMIN,
                        tenant_id: 't-dev'
                    }, children: [_jsx(Form.Item, { name: "role", label: "Role", rules: [{ required: true, message: 'Please select role!' }], validateStatus: fieldErrors.role ? 'error' : '', help: fieldErrors.role, children: _jsxs(Select, { placeholder: "Select your role", onChange: (value) => {
                                    setSelectedRole(value);
                                    // Clear tenant_id when switching to system admin
                                    if (value === UserRole.SYSTEM_ADMIN) {
                                        form.setFieldValue('tenant_id', undefined);
                                    }
                                }, children: [_jsx(Select.Option, { value: UserRole.SYSTEM_ADMIN, children: "System Admin" }), _jsx(Select.Option, { value: UserRole.TENANT_ADMIN, children: "Tenant Admin" }), _jsx(Select.Option, { value: UserRole.SITE_MANAGER, children: "Site Manager" })] }) }), selectedRole !== UserRole.SYSTEM_ADMIN && (_jsx(Form.Item, { name: "tenant_id", label: "Tenant ID", rules: [{ required: true, message: 'Please input tenant ID!' }], validateStatus: fieldErrors.tenant_id ? 'error' : '', help: fieldErrors.tenant_id, children: _jsx(Input, { prefix: _jsx(ShopOutlined, {}), placeholder: "Enter tenant ID" }) })), _jsx(Form.Item, { name: "username", label: "Username", rules: [{ required: true, message: 'Please input your username!' }], validateStatus: fieldErrors.username ? 'error' : '', help: fieldErrors.username, children: _jsx(Input, { prefix: _jsx(UserOutlined, {}), placeholder: "Enter username" }) }), _jsx(Form.Item, { name: "password", label: "Password", rules: [{ required: true, message: 'Please input your password!' }], validateStatus: fieldErrors.password ? 'error' : '', help: fieldErrors.password, children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "Enter password" }) }), _jsx(Form.Item, { className: "mb-0", children: _jsx(Button, { type: "primary", htmlType: "submit", loading: loading, block: true, className: "bg-blue-600", children: "Sign In" }) })] })] }) }));
};
