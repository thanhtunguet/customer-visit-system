import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useCallback } from 'react';
import { App } from 'antd';
import { Table, Button, Space, Tag, Popconfirm, Modal, Form, Input, Select, DatePicker, Typography, Card, Alert, Tooltip, Switch, } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, KeyOutlined, CopyOutlined, } from '@ant-design/icons';
import dayjs from 'dayjs';
import { apiClient } from '../services/api';
const { Option } = Select;
const { Text } = Typography;
const ApiKeys = () => {
    const { message } = App.useApp();
    const [apiKeys, setApiKeys] = useState([]);
    const [loading, setLoading] = useState(false);
    const [createModalVisible, setCreateModalVisible] = useState(false);
    const [editModalVisible, setEditModalVisible] = useState(false);
    const [keyDisplayModalVisible, setKeyDisplayModalVisible] = useState(false);
    const [selectedApiKey, setSelectedApiKey] = useState(null);
    const [newApiKeyData, setNewApiKeyData] = useState(null);
    const [showApiKey, setShowApiKey] = useState(false);
    const [createForm] = Form.useForm();
    const [editForm] = Form.useForm();
    const loadApiKeys = useCallback(async () => {
        setLoading(true);
        try {
            const data = await apiClient.getApiKeys();
            setApiKeys(data);
        }
        catch (error) {
            const axiosError = error;
            console.error('API Keys load error:', axiosError.response?.data || axiosError.message);
            if (axiosError.response?.status === 400) {
                message.error('Please switch to a tenant view to manage API keys');
            }
            else {
                message.error('Failed to load API keys: ' +
                    (error.response?.data?.detail || error.message));
            }
        }
        finally {
            setLoading(false);
        }
    }, [message]);
    useEffect(() => {
        // Add a small delay to ensure tenant context is properly set
        const timer = setTimeout(() => {
            loadApiKeys();
        }, 100);
        return () => clearTimeout(timer);
    }, [loadApiKeys]);
    const handleCreateApiKey = async (values) => {
        try {
            // Convert dayjs to ISO string if expires_at is provided
            const payload = {
                ...values,
                expires_at: values.expires_at
                    ? values.expires_at.toISOString()
                    : undefined,
            };
            console.log('Creating API key with payload:', payload);
            const newApiKey = await apiClient.createApiKey(payload);
            setNewApiKeyData(newApiKey);
            setCreateModalVisible(false);
            setKeyDisplayModalVisible(true);
            createForm.resetFields();
            message.success('API key created successfully!');
            loadApiKeys();
        }
        catch (error) {
            console.error('API key creation error:', error);
            const axiosError = error;
            const errorMessage = axiosError.response?.data?.detail ||
                axiosError.message ||
                'Unknown error';
            message.error('Failed to create API key: ' + errorMessage);
        }
    };
    const handleUpdateApiKey = async (values) => {
        if (!selectedApiKey)
            return;
        try {
            const payload = {
                ...values,
                expires_at: values.expires_at
                    ? values.expires_at.toISOString()
                    : undefined,
            };
            await apiClient.updateApiKey(selectedApiKey.key_id, payload);
            setEditModalVisible(false);
            setSelectedApiKey(null);
            editForm.resetFields();
            message.success('API key updated successfully!');
            loadApiKeys();
        }
        catch (error) {
            const err = error;
            message.error('Failed to update API key: ' + err.message);
        }
    };
    const handleDeleteApiKey = async (keyId) => {
        try {
            await apiClient.deleteApiKey(keyId);
            message.success('API key deleted successfully!');
            loadApiKeys();
        }
        catch (error) {
            const err = error;
            message.error('Failed to delete API key: ' + err.message);
        }
    };
    const copyToClipboard = (text) => {
        navigator.clipboard
            .writeText(text)
            .then(() => {
            message.success('Copied to clipboard!');
        })
            .catch(() => {
            message.error('Failed to copy to clipboard');
        });
    };
    const formatLastUsed = (lastUsed) => {
        if (!lastUsed)
            return 'Never';
        return dayjs(lastUsed).format('MMM D, YYYY HH:mm');
    };
    const isExpired = (expiresAt) => {
        if (!expiresAt)
            return false;
        return dayjs(expiresAt).isBefore(dayjs());
    };
    const getStatusTag = (apiKey) => {
        if (!apiKey.is_active) {
            return _jsx(Tag, { color: "red", children: "Inactive" });
        }
        if (isExpired(apiKey.expires_at)) {
            return _jsx(Tag, { color: "orange", children: "Expired" });
        }
        return _jsx(Tag, { color: "green", children: "Active" });
    };
    const columns = [
        {
            title: 'Name',
            dataIndex: 'name',
            key: 'name',
            render: (text, _record) => (_jsxs(Space, { children: [_jsx(KeyOutlined, {}), _jsx("strong", { children: text })] })),
        },
        {
            title: 'Role',
            dataIndex: 'role',
            key: 'role',
            render: (role) => (_jsx(Tag, { color: role === 'worker' ? 'blue' : 'purple', children: role.toUpperCase() })),
        },
        {
            title: 'Status',
            key: 'status',
            render: (_, record) => getStatusTag(record),
        },
        {
            title: 'Last Used',
            dataIndex: 'last_used',
            key: 'last_used',
            render: (lastUsed) => (_jsx(Text, { type: lastUsed ? undefined : 'secondary', children: formatLastUsed(lastUsed) })),
        },
        {
            title: 'Expires',
            dataIndex: 'expires_at',
            key: 'expires_at',
            render: (expiresAt) => {
                if (!expiresAt)
                    return _jsx(Text, { type: "secondary", children: "Never" });
                const expired = isExpired(expiresAt);
                return (_jsx(Text, { type: expired ? 'danger' : undefined, children: dayjs(expiresAt).format('MMM D, YYYY') }));
            },
        },
        {
            title: 'Created',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (createdAt) => dayjs(createdAt).format('MMM D, YYYY'),
        },
        {
            title: 'Actions',
            key: 'actions',
            render: (_, record) => (_jsxs(Space, { children: [_jsx(Tooltip, { title: "Edit API Key", children: _jsx(Button, { type: "text", icon: _jsx(EditOutlined, {}), onClick: () => {
                                setSelectedApiKey(record);
                                editForm.setFieldsValue({
                                    name: record.name,
                                    is_active: record.is_active,
                                    expires_at: record.expires_at
                                        ? dayjs(record.expires_at)
                                        : undefined,
                                });
                                setEditModalVisible(true);
                            } }) }, "edit"), _jsx(Tooltip, { title: "Delete API Key", children: _jsx(Popconfirm, { title: "Delete API Key", description: "Are you sure you want to delete this API key? This action cannot be undone.", onConfirm: () => handleDeleteApiKey(record.key_id), okText: "Yes", cancelText: "No", children: _jsx(Button, { type: "text", danger: true, icon: _jsx(DeleteOutlined, {}) }) }) }, "delete")] })),
        },
    ];
    return (_jsxs("div", { children: [_jsxs(Card, { children: [apiKeys.length === 0 && !loading && (_jsx(Alert, { message: "No API Keys Found", description: "If you're a system administrator, please switch to a tenant view to manage API keys. Only tenant administrators and system admins in tenant context can manage API keys.", type: "info", showIcon: true, style: { marginBottom: 16 } })), _jsxs("div", { style: {
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: 16,
                        }, children: [_jsxs("div", { children: [_jsx("h2", { children: "API Key Management" }), _jsx("p", { children: "Manage API keys for worker authentication and system integration." })] }), _jsx(Button, { type: "primary", icon: _jsx(PlusOutlined, {}), onClick: () => setCreateModalVisible(true), children: "Create API Key" })] }), _jsx(Table, { columns: columns, dataSource: apiKeys, rowKey: "key_id", loading: loading, pagination: {
                            pageSize: 10,
                            showSizeChanger: true,
                            showQuickJumper: true,
                            showTotal: (total) => `Total ${total} API keys`,
                        } })] }), _jsx(Modal, { title: "Create New API Key", open: createModalVisible, onCancel: () => {
                    setCreateModalVisible(false);
                    createForm.resetFields();
                }, footer: null, children: _jsxs(Form, { form: createForm, layout: "vertical", onFinish: handleCreateApiKey, children: [_jsx(Form.Item, { name: "name", label: "API Key Name", rules: [{ required: true, message: 'Please enter API key name' }], children: _jsx(Input, { placeholder: "e.g., Production Worker Key" }) }), _jsx(Form.Item, { name: "role", label: "Role", initialValue: "worker", children: _jsx(Select, { children: _jsx(Option, { value: "worker", children: "Worker" }) }) }), _jsx(Form.Item, { name: "expires_at", label: "Expiration Date (Optional)", children: _jsx(DatePicker, { style: { width: '100%' }, placeholder: "Select expiration date", disabledDate: (current) => current && current < dayjs().endOf('day') }) }), _jsx(Form.Item, { children: _jsxs(Space, { children: [_jsx(Button, { type: "primary", htmlType: "submit", children: "Create API Key" }, "create"), _jsx(Button, { onClick: () => {
                                            setCreateModalVisible(false);
                                            createForm.resetFields();
                                        }, children: "Cancel" }, "cancel")] }) })] }) }), _jsx(Modal, { title: "Edit API Key", open: editModalVisible, onCancel: () => {
                    setEditModalVisible(false);
                    setSelectedApiKey(null);
                    editForm.resetFields();
                }, footer: null, children: _jsxs(Form, { form: editForm, layout: "vertical", onFinish: handleUpdateApiKey, children: [_jsx(Form.Item, { name: "name", label: "API Key Name", rules: [{ required: true, message: 'Please enter API key name' }], children: _jsx(Input, { placeholder: "e.g., Production Worker Key" }) }), _jsx(Form.Item, { name: "is_active", label: "Status", valuePropName: "checked", children: _jsx(Switch, { checkedChildren: "Active", unCheckedChildren: "Inactive" }) }), _jsx(Form.Item, { name: "expires_at", label: "Expiration Date", children: _jsx(DatePicker, { style: { width: '100%' }, placeholder: "Select expiration date", disabledDate: (current) => current && current < dayjs().endOf('day') }) }), _jsx(Form.Item, { children: _jsxs(Space, { children: [_jsx(Button, { type: "primary", htmlType: "submit", children: "Update API Key" }, "update"), _jsx(Button, { onClick: () => {
                                            setEditModalVisible(false);
                                            setSelectedApiKey(null);
                                            editForm.resetFields();
                                        }, children: "Cancel" }, "cancel")] }) })] }) }), _jsx(Modal, { title: "API Key Created Successfully!", open: keyDisplayModalVisible, onCancel: () => {
                    setKeyDisplayModalVisible(false);
                    setNewApiKeyData(null);
                    setShowApiKey(false);
                }, footer: [
                    _jsx(Button, { onClick: () => {
                            setKeyDisplayModalVisible(false);
                            setNewApiKeyData(null);
                            setShowApiKey(false);
                        }, children: "Close" }, "close"),
                ], closable: false, maskClosable: false, children: newApiKeyData && (_jsxs("div", { children: [_jsx(Alert, { message: "Important: Save this API key now!", description: "This is the only time you'll be able to see the complete API key. Store it in a secure location.", type: "warning", showIcon: true, style: { marginBottom: 16 } }), _jsxs("div", { style: { marginBottom: 16 }, children: [_jsx("strong", { children: "API Key Name:" }), " ", newApiKeyData.name] }), _jsxs("div", { style: { marginBottom: 16 }, children: [_jsx("strong", { children: "Role:" }), ' ', _jsx(Tag, { color: "blue", children: newApiKeyData.role.toUpperCase() })] }), _jsxs("div", { style: { marginBottom: 16 }, children: [_jsx("strong", { children: "API Key:" }), _jsxs("div", { style: {
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 8,
                                        marginTop: 8,
                                        padding: 12,
                                        backgroundColor: '#f5f5f5',
                                        borderRadius: 6,
                                        border: '1px solid #d9d9d9',
                                    }, children: [_jsx(Input.Password, { value: newApiKeyData.api_key, readOnly: true, visibilityToggle: {
                                                visible: showApiKey,
                                                onVisibleChange: setShowApiKey,
                                            }, style: { flex: 1 } }), _jsx(Button, { icon: _jsx(CopyOutlined, {}), onClick: () => copyToClipboard(newApiKeyData.api_key), title: "Copy to clipboard" })] })] }), newApiKeyData.expires_at && (_jsxs("div", { children: [_jsx("strong", { children: "Expires:" }), ' ', dayjs(newApiKeyData.expires_at).format('MMMM D, YYYY')] }))] })) })] }));
};
export { ApiKeys };
export default ApiKeys;
