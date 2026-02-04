import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Modal, Form, Input, Button, App } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
export const ChangePasswordModal = ({ open, onClose, }) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const { message } = App.useApp();
    const handleSubmit = async (values) => {
        setLoading(true);
        try {
            await apiClient.changeMyPassword({
                current_password: values.current_password,
                new_password: values.new_password,
            });
            message.success('Password changed successfully');
            form.resetFields();
            onClose();
        }
        catch (error) {
            const errorMessage = error?.response?.data?.detail || 'Failed to change password';
            // Handle specific validation errors
            if (errorMessage.includes('Current password is incorrect')) {
                form.setFields([
                    {
                        name: 'current_password',
                        errors: ['Current password is incorrect'],
                    },
                ]);
            }
            else if (errorMessage.includes('Current password is required')) {
                form.setFields([
                    {
                        name: 'current_password',
                        errors: ['Current password is required'],
                    },
                ]);
            }
            else {
                // Generic error message for other cases
                message.error(errorMessage);
            }
        }
        finally {
            setLoading(false);
        }
    };
    const handleCancel = () => {
        form.resetFields();
        onClose();
    };
    // Clear field errors when user starts typing
    const handleFieldChange = (changedFields) => {
        // Clear any manual field errors when user modifies the field
        if (changedFields.current_password !== undefined) {
            form.setFields([
                {
                    name: 'current_password',
                    errors: [],
                },
            ]);
        }
    };
    return (_jsx(Modal, { title: "Change Password", open: open, onCancel: handleCancel, footer: null, destroyOnHidden: true, children: _jsxs(Form, { form: form, layout: "vertical", onFinish: handleSubmit, onValuesChange: handleFieldChange, requiredMark: false, children: [_jsx(Form.Item, { name: "current_password", label: "Current Password", rules: [
                        { required: true, message: 'Please enter your current password' },
                    ], children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "Enter current password", autoComplete: "current-password" }) }), _jsx(Form.Item, { name: "new_password", label: "New Password", help: "Password must be at least 8 characters with uppercase, lowercase, and number", rules: [
                        { required: true, message: 'Please enter your new password' },
                        { min: 8, message: 'Password must be at least 8 characters long' },
                        {
                            pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])/,
                            message: 'Password must contain at least one uppercase letter, one lowercase letter, and one number',
                        },
                    ], children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "Enter new password", autoComplete: "new-password" }) }), _jsx(Form.Item, { name: "confirm_password", label: "Confirm New Password", dependencies: ['new_password'], rules: [
                        { required: true, message: 'Please confirm your new password' },
                        ({ getFieldValue }) => ({
                            validator(_, value) {
                                if (!value || getFieldValue('new_password') === value) {
                                    return Promise.resolve();
                                }
                                return Promise.reject(new Error('Passwords do not match'));
                            },
                        }),
                    ], children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "Confirm new password", autoComplete: "new-password" }) }), _jsx(Form.Item, { className: "mb-0 mt-6", children: _jsxs("div", { className: "flex gap-2 justify-end", children: [_jsx(Button, { onClick: handleCancel, children: "Cancel" }), _jsx(Button, { type: "primary", htmlType: "submit", loading: loading, children: "Change Password" })] }) })] }) }));
};
