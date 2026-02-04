import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useCallback } from 'react';
import { Table, Button, Space, Tag, Popconfirm, Modal, Form, Input, Select, Switch, Tooltip, Card, Typography, App } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, KeyOutlined, StopOutlined, PlayCircleOutlined, UsergroupAddOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { UserRole } from '../types/api';
const { Option } = Select;
const { Title } = Typography;
export const Users = () => {
    const { message } = App.useApp();
    const [users, setUsers] = useState([]);
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(false);
    const [createModalVisible, setCreateModalVisible] = useState(false);
    const [editModalVisible, setEditModalVisible] = useState(false);
    const [passwordModalVisible, setPasswordModalVisible] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);
    const [createForm] = Form.useForm();
    const [editForm] = Form.useForm();
    const [passwordForm] = Form.useForm();
    const loadUsers = useCallback(async () => {
        setLoading(true);
        try {
            const data = await apiClient.getUsers();
            setUsers(data);
        }
        catch (error) {
            message.error('Failed to load users');
            console.error(error);
        }
        finally {
            setLoading(false);
        }
    }, [message]);
    const loadTenants = useCallback(async () => {
        try {
            const data = await apiClient.getTenants();
            setTenants(data);
        }
        catch (error) {
            console.error('Failed to load tenants:', error);
        }
    }, []);
    useEffect(() => {
        loadUsers();
        loadTenants();
    }, [loadUsers, loadTenants]);
    const handleCreateUser = async (values) => {
        try {
            await apiClient.createUser(values);
            message.success('User created successfully');
            setCreateModalVisible(false);
            createForm.resetFields();
            loadUsers();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to create user');
        }
    };
    const handleEditUser = async (values) => {
        if (!selectedUser)
            return;
        try {
            await apiClient.updateUser(selectedUser.user_id, values);
            message.success('User updated successfully');
            setEditModalVisible(false);
            editForm.resetFields();
            setSelectedUser(null);
            loadUsers();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to update user');
        }
    };
    const handleChangePassword = async (values) => {
        if (!selectedUser)
            return;
        try {
            await apiClient.changeUserPassword(selectedUser.user_id, values);
            message.success('Password changed successfully');
            setPasswordModalVisible(false);
            passwordForm.resetFields();
            setSelectedUser(null);
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to change password');
        }
    };
    const handleToggleStatus = async (user) => {
        try {
            await apiClient.toggleUserStatus(user.user_id);
            message.success(`User ${user.is_active ? 'disabled' : 'enabled'} successfully`);
            loadUsers();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to toggle user status');
        }
    };
    const handleDeleteUser = async (user) => {
        try {
            await apiClient.deleteUser(user.user_id);
            message.success('User deleted successfully');
            loadUsers();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to delete user');
        }
    };
    const showEditModal = (user) => {
        setSelectedUser(user);
        editForm.setFieldsValue({
            username: user.username,
            email: user.email,
            first_name: user.first_name,
            last_name: user.last_name,
            role: user.role,
            tenant_id: user.tenant_id,
            is_active: user.is_active
        });
        setEditModalVisible(true);
    };
    const showPasswordModal = (user) => {
        setSelectedUser(user);
        setPasswordModalVisible(true);
    };
    const getRoleColor = (role) => {
        switch (role) {
            case UserRole.SYSTEM_ADMIN: return 'red';
            case UserRole.TENANT_ADMIN: return 'orange';
            case UserRole.SITE_MANAGER: return 'blue';
            case UserRole.WORKER: return 'green';
            default: return 'default';
        }
    };
    const getRoleLabel = (role) => {
        switch (role) {
            case UserRole.SYSTEM_ADMIN: return 'System Admin';
            case UserRole.TENANT_ADMIN: return 'Tenant Admin';
            case UserRole.SITE_MANAGER: return 'Site Manager';
            case UserRole.WORKER: return 'Worker';
            default: return role;
        }
    };
    const getTenantName = (tenantId) => {
        if (!tenantId)
            return 'N/A';
        const tenant = tenants.find(t => t.tenant_id === tenantId);
        return tenant ? tenant.name : tenantId;
    };
    const columns = [
        {
            title: 'Username',
            dataIndex: 'username',
            key: 'username',
            sorter: (a, b) => a.username.localeCompare(b.username),
        },
        {
            title: 'Name',
            key: 'name',
            render: (_, user) => user.full_name,
            sorter: (a, b) => a.full_name.localeCompare(b.full_name),
        },
        {
            title: 'Email',
            dataIndex: 'email',
            key: 'email',
        },
        {
            title: 'Role',
            key: 'role',
            render: (_, user) => (_jsx(Tag, { color: getRoleColor(user.role), children: getRoleLabel(user.role) })),
            sorter: (a, b) => a.role.localeCompare(b.role),
        },
        {
            title: 'Tenant',
            key: 'tenant',
            render: (_, user) => getTenantName(user.tenant_id),
        },
        {
            title: 'Status',
            key: 'status',
            render: (_, user) => (_jsx(Tag, { color: user.is_active ? 'success' : 'error', children: user.is_active ? 'Active' : 'Disabled' })),
            sorter: (a, b) => Number(b.is_active) - Number(a.is_active),
        },
        {
            title: 'Last Login',
            key: 'last_login',
            render: (_, user) => user.last_login
                ? new Date(user.last_login).toLocaleString()
                : 'Never',
            sorter: (a, b) => {
                if (!a.last_login && !b.last_login)
                    return 0;
                if (!a.last_login)
                    return 1;
                if (!b.last_login)
                    return -1;
                return new Date(a.last_login).getTime() - new Date(b.last_login).getTime();
            },
        },
        {
            title: 'Actions',
            key: 'actions',
            render: (_, user) => (_jsxs(Space, { size: "small", children: [_jsx(Tooltip, { title: "Edit User", children: _jsx(Button, { icon: _jsx(EditOutlined, {}), size: "small", onClick: () => showEditModal(user) }) }), _jsx(Tooltip, { title: "Change Password", children: _jsx(Button, { icon: _jsx(KeyOutlined, {}), size: "small", onClick: () => showPasswordModal(user) }) }), _jsx(Tooltip, { title: user.is_active ? 'Disable User' : 'Enable User', children: _jsx(Popconfirm, { title: `Are you sure you want to ${user.is_active ? 'disable' : 'enable'} this user?`, onConfirm: () => handleToggleStatus(user), okText: "Yes", cancelText: "No", children: _jsx(Button, { icon: user.is_active ? _jsx(StopOutlined, {}) : _jsx(PlayCircleOutlined, {}), size: "small", danger: user.is_active }) }) }), _jsx(Tooltip, { title: "Delete User", children: _jsx(Popconfirm, { title: "Are you sure you want to delete this user?", onConfirm: () => handleDeleteUser(user), okText: "Yes", cancelText: "No", children: _jsx(Button, { icon: _jsx(DeleteOutlined, {}), size: "small", danger: true }) }) })] })),
        },
    ];
    return (_jsxs("div", { className: "p-6", children: [_jsxs("div", { className: "flex justify-between items-center mb-6", children: [_jsxs("div", { children: [_jsxs(Title, { level: 2, className: "flex items-center gap-2 mb-0", children: [_jsx(UsergroupAddOutlined, {}), "User Management"] }), _jsx("p", { className: "text-gray-600 mt-1", children: "Manage system users and their access permissions" })] }), _jsx(Button, { type: "primary", icon: _jsx(PlusOutlined, {}), onClick: () => setCreateModalVisible(true), size: "large", children: "Create User" })] }), _jsx(Card, { children: _jsx(Table, { columns: columns, dataSource: users, loading: loading, rowKey: "user_id", pagination: {
                        pageSize: 10,
                        showSizeChanger: true,
                        showQuickJumper: true,
                        showTotal: (total) => `Total ${total} users`,
                    } }) }), _jsx(Modal, { title: "Create New User", open: createModalVisible, onCancel: () => {
                    setCreateModalVisible(false);
                    createForm.resetFields();
                }, footer: null, width: 600, children: _jsxs(Form, { form: createForm, layout: "vertical", onFinish: handleCreateUser, children: [_jsx(Form.Item, { name: "username", label: "Username", rules: [
                                { required: true, message: 'Please enter username' },
                                { min: 3, message: 'Username must be at least 3 characters' }
                            ], children: _jsx(Input, { placeholder: "Enter username" }) }), _jsx(Form.Item, { name: "email", label: "Email", rules: [
                                { required: true, message: 'Please enter email' },
                                { type: 'email', message: 'Please enter a valid email' }
                            ], children: _jsx(Input, { placeholder: "Enter email address" }) }), _jsxs("div", { style: { display: 'flex', gap: 16 }, children: [_jsx(Form.Item, { name: "first_name", label: "First Name", rules: [{ required: true, message: 'Please enter first name' }], style: { flex: 1 }, children: _jsx(Input, { placeholder: "Enter first name" }) }), _jsx(Form.Item, { name: "last_name", label: "Last Name", rules: [{ required: true, message: 'Please enter last name' }], style: { flex: 1 }, children: _jsx(Input, { placeholder: "Enter last name" }) })] }), _jsx(Form.Item, { name: "password", label: "Password", rules: [
                                { required: true, message: 'Please enter password' },
                                { min: 6, message: 'Password must be at least 6 characters' }
                            ], children: _jsx(Input.Password, { placeholder: "Enter password" }) }), _jsx(Form.Item, { name: "role", label: "Role", rules: [{ required: true, message: 'Please select role' }], children: _jsx(Select, { placeholder: "Select user role", children: Object.values(UserRole).map(role => (_jsx(Option, { value: role, children: getRoleLabel(role) }, role))) }) }), _jsx(Form.Item, { name: "tenant_id", label: "Tenant", dependencies: ['role'], rules: [
                                ({ getFieldValue }) => ({
                                    validator(_, value) {
                                        const role = getFieldValue('role');
                                        if (role !== UserRole.SYSTEM_ADMIN && !value) {
                                            return Promise.reject(new Error('Tenant is required for non-system admin users'));
                                        }
                                        return Promise.resolve();
                                    },
                                }),
                            ], children: _jsx(Select, { placeholder: "Select tenant (not required for System Admin)", children: tenants.map(tenant => (_jsx(Option, { value: tenant.tenant_id, children: tenant.name }, tenant.tenant_id))) }) }), _jsx(Form.Item, { name: "is_active", label: "Status", valuePropName: "checked", initialValue: true, children: _jsx(Switch, { checkedChildren: "Active", unCheckedChildren: "Disabled" }) }), _jsx(Form.Item, { style: { marginBottom: 0, textAlign: 'right' }, children: _jsxs(Space, { children: [_jsx(Button, { onClick: () => {
                                            setCreateModalVisible(false);
                                            createForm.resetFields();
                                        }, children: "Cancel" }), _jsx(Button, { type: "primary", htmlType: "submit", children: "Create User" })] }) })] }) }), _jsx(Modal, { title: "Edit User", open: editModalVisible, onCancel: () => {
                    setEditModalVisible(false);
                    editForm.resetFields();
                    setSelectedUser(null);
                }, footer: null, width: 600, children: _jsxs(Form, { form: editForm, layout: "vertical", onFinish: handleEditUser, children: [_jsx(Form.Item, { name: "username", label: "Username", rules: [
                                { required: true, message: 'Please enter username' },
                                { min: 3, message: 'Username must be at least 3 characters' }
                            ], children: _jsx(Input, { placeholder: "Enter username" }) }), _jsx(Form.Item, { name: "email", label: "Email", rules: [
                                { required: true, message: 'Please enter email' },
                                { type: 'email', message: 'Please enter a valid email' }
                            ], children: _jsx(Input, { placeholder: "Enter email address" }) }), _jsxs("div", { style: { display: 'flex', gap: 16 }, children: [_jsx(Form.Item, { name: "first_name", label: "First Name", rules: [{ required: true, message: 'Please enter first name' }], style: { flex: 1 }, children: _jsx(Input, { placeholder: "Enter first name" }) }), _jsx(Form.Item, { name: "last_name", label: "Last Name", rules: [{ required: true, message: 'Please enter last name' }], style: { flex: 1 }, children: _jsx(Input, { placeholder: "Enter last name" }) })] }), _jsx(Form.Item, { name: "role", label: "Role", rules: [{ required: true, message: 'Please select role' }], children: _jsx(Select, { placeholder: "Select user role", children: Object.values(UserRole).map(role => (_jsx(Option, { value: role, children: getRoleLabel(role) }, role))) }) }), _jsx(Form.Item, { name: "tenant_id", label: "Tenant", dependencies: ['role'], rules: [
                                ({ getFieldValue }) => ({
                                    validator(_, value) {
                                        const role = getFieldValue('role');
                                        if (role !== UserRole.SYSTEM_ADMIN && !value) {
                                            return Promise.reject(new Error('Tenant is required for non-system admin users'));
                                        }
                                        return Promise.resolve();
                                    },
                                }),
                            ], children: _jsx(Select, { placeholder: "Select tenant (not required for System Admin)", children: tenants.map(tenant => (_jsx(Option, { value: tenant.tenant_id, children: tenant.name }, tenant.tenant_id))) }) }), _jsx(Form.Item, { name: "is_active", label: "Status", valuePropName: "checked", children: _jsx(Switch, { checkedChildren: "Active", unCheckedChildren: "Disabled" }) }), _jsx(Form.Item, { style: { marginBottom: 0, textAlign: 'right' }, children: _jsxs(Space, { children: [_jsx(Button, { onClick: () => {
                                            setEditModalVisible(false);
                                            editForm.resetFields();
                                            setSelectedUser(null);
                                        }, children: "Cancel" }), _jsx(Button, { type: "primary", htmlType: "submit", children: "Update User" })] }) })] }) }), _jsx(Modal, { title: `Change Password - ${selectedUser?.username}`, open: passwordModalVisible, onCancel: () => {
                    setPasswordModalVisible(false);
                    passwordForm.resetFields();
                    setSelectedUser(null);
                }, footer: null, width: 500, children: _jsxs(Form, { form: passwordForm, layout: "vertical", onFinish: handleChangePassword, children: [_jsx(Form.Item, { name: "new_password", label: "New Password", rules: [
                                { required: true, message: 'Please enter new password' },
                                { min: 6, message: 'Password must be at least 6 characters' }
                            ], children: _jsx(Input.Password, { placeholder: "Enter new password" }) }), _jsx(Form.Item, { name: "confirm_password", label: "Confirm New Password", dependencies: ['new_password'], rules: [
                                { required: true, message: 'Please confirm new password' },
                                ({ getFieldValue }) => ({
                                    validator(_, value) {
                                        if (!value || getFieldValue('new_password') === value) {
                                            return Promise.resolve();
                                        }
                                        return Promise.reject(new Error('Passwords do not match'));
                                    },
                                }),
                            ], children: _jsx(Input.Password, { placeholder: "Confirm new password" }) }), _jsx(Form.Item, { style: { marginBottom: 0, textAlign: 'right' }, children: _jsxs(Space, { children: [_jsx(Button, { onClick: () => {
                                            setPasswordModalVisible(false);
                                            passwordForm.resetFields();
                                            setSelectedUser(null);
                                        }, children: "Cancel" }), _jsx(Button, { type: "primary", htmlType: "submit", children: "Change Password" })] }) })] }) })] }));
};
