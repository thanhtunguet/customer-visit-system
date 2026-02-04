import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Typography, Space, Alert, Tag } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { EditAction, DeleteAction } from '../components/TableActionButtons';
import dayjs from 'dayjs';
const { Title } = Typography;
export const Sites = () => {
    const [sites, setSites] = useState([]);
    const [loading, setLoading] = useState(true);
    const [modalVisible, setModalVisible] = useState(false);
    const [form] = Form.useForm();
    const [error, setError] = useState(null);
    const [editingSite, setEditingSite] = useState(null);
    useEffect(() => {
        loadSites();
    }, []);
    const loadSites = async () => {
        try {
            setLoading(true);
            setError(null);
            const sitesData = await apiClient.getSites();
            setSites(sitesData);
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to load sites');
        }
        finally {
            setLoading(false);
        }
    };
    const handleCreateSite = async (values) => {
        try {
            if (editingSite) {
                await apiClient.updateSite(editingSite.site_id, values);
            }
            else {
                await apiClient.createSite(values);
            }
            setModalVisible(false);
            setEditingSite(null);
            form.resetFields();
            await loadSites();
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to save site');
        }
    };
    const handleEditSite = (site) => {
        setEditingSite(site);
        form.setFieldsValue({
            name: site.name,
            location: site.location,
        });
        setModalVisible(true);
    };
    const handleDeleteSite = async (site) => {
        try {
            await apiClient.deleteSite(site.site_id);
            await loadSites();
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to delete site');
        }
    };
    const columns = [
        {
            title: 'ID',
            dataIndex: 'site_id',
            key: 'site_id',
            width: 80,
            render: (id) => (_jsxs("span", { className: "font-mono text-gray-600", children: ["#", id] })),
        },
        {
            title: 'Name',
            dataIndex: 'name',
            key: 'name',
            render: (text) => (_jsx("span", { className: "font-medium", children: text })),
        },
        {
            title: 'Location',
            dataIndex: 'location',
            key: 'location',
            render: (text) => text || _jsx("span", { className: "text-gray-400", children: "-" }),
        },
        {
            title: 'Created',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (date) => (_jsx("span", { className: "text-gray-600", children: dayjs(date).format('MMM D, YYYY') })),
        },
        {
            title: 'Status',
            key: 'status',
            render: () => (_jsx(Tag, { color: "green", children: "Active" })),
        },
        {
            title: 'Actions',
            key: 'actions',
            width: 100,
            fixed: 'right',
            render: (_, site) => (_jsxs(Space, { size: "small", children: [_jsx(EditAction, { onClick: () => handleEditSite(site), tooltip: "Edit site" }), _jsx(DeleteAction, { onConfirm: () => handleDeleteSite(site), title: "Delete Site", description: "Are you sure you want to delete this site? This will also remove all associated cameras and data.", tooltip: "Delete site" })] })),
        },
    ];
    if (error && sites.length === 0) {
        return (_jsx(Alert, { message: "Error Loading Sites", description: error, type: "error", showIcon: true, action: _jsx(Button, { onClick: loadSites, children: "Retry" }) }));
    }
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx(Title, { level: 2, className: "mb-0", children: "Sites" }), _jsx(Button, { type: "primary", icon: _jsx(PlusOutlined, {}), onClick: () => {
                            setEditingSite(null);
                            form.resetFields();
                            setModalVisible(true);
                        }, className: "bg-blue-600", children: "Add Site" })] }), error && (_jsx(Alert, { message: error, type: "error", closable: true, onClose: () => setError(null) })), _jsx("div", { className: "bg-white rounded-lg shadow", children: _jsx(Table, { columns: columns, dataSource: sites, rowKey: "site_id", loading: loading, pagination: {
                        total: sites.length,
                        pageSize: 10,
                        showSizeChanger: true,
                        showQuickJumper: true,
                        showTotal: (total) => `Total ${total} sites`,
                    } }) }), _jsx(Modal, { title: editingSite ? "Edit Site" : "Add New Site", open: modalVisible, onCancel: () => {
                    setModalVisible(false);
                    setEditingSite(null);
                    form.resetFields();
                }, onOk: () => form.submit(), confirmLoading: loading, children: _jsxs(Form, { form: form, layout: "vertical", onFinish: handleCreateSite, children: [_jsx(Form.Item, { name: "name", label: "Site Name", rules: [{ required: true, message: 'Please input site name!' }], children: _jsx(Input, { placeholder: "e.g. Main Office" }) }), _jsx(Form.Item, { name: "location", label: "Location", children: _jsx(Input, { placeholder: "e.g. 123 Main St, City, State" }) })] }) })] }));
};
