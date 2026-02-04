import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Typography, Space, Alert, Tag, Select, } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { StaffDetailsModal } from '../components/StaffDetailsModal';
import { ViewAction, EditAction, DeleteAction } from '../components/TableActionButtons';
import dayjs from 'dayjs';
const { Title } = Typography;
export const StaffPage = () => {
    const [staff, setStaff] = useState([]);
    const [sites, setSites] = useState([]);
    const [loading, setLoading] = useState(true);
    const [modalVisible, setModalVisible] = useState(false);
    const [detailsModalVisible, setDetailsModalVisible] = useState(false);
    const [selectedStaffId, setSelectedStaffId] = useState(null);
    const [editingStaff, setEditingStaff] = useState(null);
    const [form] = Form.useForm();
    const [error, setError] = useState(null);
    useEffect(() => {
        loadData();
    }, []);
    const loadData = async () => {
        try {
            setLoading(true);
            setError(null);
            const [staffData, sitesData] = await Promise.all([
                apiClient.getStaff(),
                apiClient.getSites()
            ]);
            setStaff(staffData);
            setSites(sitesData);
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to load data');
        }
        finally {
            setLoading(false);
        }
    };
    const handleCreateStaff = async (values) => {
        try {
            if (editingStaff) {
                await apiClient.updateStaff(editingStaff.staff_id, values);
            }
            else {
                await apiClient.createStaff(values);
            }
            setModalVisible(false);
            setEditingStaff(null);
            form.resetFields();
            await loadData();
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to save staff member');
        }
    };
    const handleViewDetails = (staffMember) => {
        setSelectedStaffId(staffMember.staff_id);
        setDetailsModalVisible(true);
    };
    const handleEditStaff = (staffMember) => {
        setEditingStaff(staffMember);
        form.setFieldsValue({
            name: staffMember.name,
            site_id: staffMember.site_id,
        });
        setModalVisible(true);
    };
    const handleEditFromDetails = (staffId) => {
        const staffMember = staff.find(s => s.staff_id === staffId);
        if (staffMember) {
            setDetailsModalVisible(false);
            handleEditStaff(staffMember);
        }
    };
    const handleDeleteStaff = async (staffMember) => {
        try {
            await apiClient.deleteStaff(staffMember.staff_id);
            await loadData();
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to delete staff member');
        }
    };
    const columns = [
        {
            title: 'ID',
            dataIndex: 'staff_id',
            key: 'staff_id',
            width: 80,
            render: (id) => (_jsxs("span", { className: "font-mono text-gray-600", children: ["#", id] })),
        },
        {
            title: 'Name',
            dataIndex: 'name',
            key: 'name',
            render: (text, record) => (_jsx(Button, { type: "link", className: "p-0 h-auto font-medium text-left", onClick: () => handleViewDetails(record), children: text })),
        },
        {
            title: 'Site',
            dataIndex: 'site_id',
            key: 'site_id',
            render: (siteId) => {
                if (!siteId)
                    return _jsx("span", { className: "text-gray-400", children: "All Sites" });
                const site = sites.find(s => s.site_id === siteId);
                return site ? site.name : siteId;
            },
        },
        {
            title: 'Status',
            dataIndex: 'is_active',
            key: 'is_active',
            render: (isActive) => (_jsx(Tag, { color: isActive ? 'green' : 'red', children: isActive ? 'Active' : 'Inactive' })),
        },
        {
            title: 'Created',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (date) => (_jsx("span", { className: "text-gray-600", children: dayjs(date).format('MMM D, YYYY') })),
        },
        {
            title: 'Actions',
            key: 'actions',
            width: 120,
            fixed: 'right',
            render: (_, staffMember) => (_jsxs(Space, { size: "small", children: [_jsx(ViewAction, { onClick: () => handleViewDetails(staffMember), tooltip: "View details & manage face images" }), _jsx(EditAction, { onClick: () => handleEditStaff(staffMember), tooltip: "Edit staff member" }), _jsx(DeleteAction, { onConfirm: () => handleDeleteStaff(staffMember), title: "Delete Staff Member", description: "Are you sure you want to delete this staff member? This will also remove their face recognition data.", tooltip: "Delete staff member" })] })),
        },
    ];
    if (error && staff.length === 0) {
        return (_jsx(Alert, { message: "Error Loading Staff", description: error, type: "error", showIcon: true, action: _jsx(Button, { onClick: loadData, children: "Retry" }) }));
    }
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx(Title, { level: 2, className: "mb-0", children: "Staff Management" }), _jsx(Button, { type: "primary", icon: _jsx(PlusOutlined, {}), onClick: () => {
                            setEditingStaff(null);
                            form.resetFields();
                            setModalVisible(true);
                        }, className: "bg-blue-600", children: "Add Staff Member" })] }), error && (_jsx(Alert, { message: error, type: "error", closable: true, onClose: () => setError(null) })), _jsx("div", { className: "bg-white rounded-lg shadow", children: _jsx(Table, { columns: columns, dataSource: staff, rowKey: "staff_id", loading: loading, pagination: {
                        total: staff.length,
                        pageSize: 10,
                        showSizeChanger: true,
                        showQuickJumper: true,
                        showTotal: (total) => `Total ${total} staff members`,
                    } }) }), _jsx(Modal, { title: editingStaff ? "Edit Staff Member" : "Add New Staff Member", open: modalVisible, onCancel: () => {
                    setModalVisible(false);
                    setEditingStaff(null);
                    form.resetFields();
                }, onOk: () => form.submit(), confirmLoading: loading, children: _jsxs(Form, { form: form, layout: "vertical", onFinish: handleCreateStaff, children: [_jsx(Form.Item, { name: "name", label: "Full Name", rules: [{ required: true, message: 'Please input staff name!' }], children: _jsx(Input, { placeholder: "e.g. John Doe" }) }), _jsx(Form.Item, { name: "site_id", label: "Assigned Site", children: _jsx(Select, { placeholder: "Select a site (optional)", allowClear: true, options: sites.map(site => ({
                                    value: site.site_id,
                                    label: site.name
                                })) }) })] }) }), _jsx(StaffDetailsModal, { visible: detailsModalVisible, staffId: selectedStaffId, onClose: () => {
                    setDetailsModalVisible(false);
                    setSelectedStaffId(null);
                }, onEdit: handleEditFromDetails })] }));
};
