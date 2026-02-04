import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useCallback } from 'react';
import { Modal, Tabs, Descriptions, Tag, Spin, Alert, Button, Space, Typography } from 'antd';
import { UserOutlined, PictureOutlined, ExperimentOutlined, EditOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { StaffFaceGallery } from './StaffFaceGallery';
import { FaceRecognitionTest } from './FaceRecognitionTest';
import dayjs from 'dayjs';
const { Title } = Typography;
export const StaffDetailsModal = ({ visible, staffId, onClose, onEdit }) => {
    const [loading, setLoading] = useState(false);
    const [staffData, setStaffData] = useState(null);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('details');
    const loadStaffData = useCallback(async () => {
        if (!staffId)
            return;
        try {
            setLoading(true);
            setError(null);
            const data = await apiClient.getStaffWithFaces(staffId);
            setStaffData(data);
        }
        catch (err) {
            const axiosError = err;
            setError(axiosError.response?.data?.detail || 'Failed to load staff details');
            setStaffData(null);
        }
        finally {
            setLoading(false);
        }
    }, [staffId]);
    useEffect(() => {
        if (visible && staffId) {
            loadStaffData();
        }
    }, [visible, staffId, loadStaffData]);
    const handleClose = () => {
        setStaffData(null);
        setError(null);
        setActiveTab('details');
        onClose();
    };
    const handleEdit = () => {
        if (staffData && onEdit) {
            onEdit(staffData.staff_id);
        }
    };
    const tabItems = [
        {
            key: 'details',
            label: (_jsxs(Space, { children: [_jsx(UserOutlined, {}), "Staff Details"] })),
            children: staffData && (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx(Title, { level: 4, className: "mb-0", children: staffData.name }), onEdit && (_jsx(Button, { icon: _jsx(EditOutlined, {}), onClick: handleEdit, children: "Edit Staff" }))] }), _jsxs(Descriptions, { column: 1, bordered: true, size: "small", children: [_jsx(Descriptions.Item, { label: "Staff ID", children: _jsx("span", { className: "font-mono", children: staffData.staff_id }) }), _jsx(Descriptions.Item, { label: "Name", children: _jsx("span", { className: "font-medium", children: staffData.name }) }), _jsx(Descriptions.Item, { label: "Site Assignment", children: staffData.site_id || (_jsx("span", { className: "text-gray-400", children: "All Sites" })) }), _jsx(Descriptions.Item, { label: "Status", children: _jsx(Tag, { color: staffData.is_active ? 'green' : 'red', children: staffData.is_active ? 'Active' : 'Inactive' }) }), _jsx(Descriptions.Item, { label: "Face Images", children: _jsxs(Space, { children: [_jsxs("span", { children: [staffData.face_images.length, " images"] }), staffData.face_images.some(img => img.is_primary) && (_jsx(Tag, { color: "gold", className: "text-xs", children: "Has Primary" })), staffData.face_images.length === 0 && (_jsx(Tag, { color: "orange", className: "text-xs", children: "No Face Data" }))] }) }), _jsx(Descriptions.Item, { label: "Created", children: dayjs(staffData.created_at).format('MMMM D, YYYY [at] h:mm A') }), _jsx(Descriptions.Item, { label: "Recognition Status", children: staffData.face_images.length > 0 ? (_jsx(Tag, { color: "green", children: "Enrolled" })) : (_jsx(Tag, { color: "orange", children: "Not Enrolled" })) })] }), staffData.face_images.length === 0 && (_jsx(Alert, { message: "Customer Recognition Not Enabled", description: "This staff member has no face images uploaded. Upload face images in the Face Gallery tab to enable face recognition.", type: "warning", showIcon: true }))] }))
        },
        {
            key: 'faces',
            label: (_jsxs(Space, { children: [_jsx(PictureOutlined, {}), "Face Gallery (", staffData?.face_images.length || 0, ")"] })),
            children: staffData && (_jsx(StaffFaceGallery, { staffId: staffData.staff_id, staffName: staffData.name, faceImages: staffData.face_images, onImagesChange: loadStaffData }))
        },
        {
            key: 'test',
            label: (_jsxs(Space, { children: [_jsx(ExperimentOutlined, {}), "Recognition Test"] })),
            disabled: !staffData?.face_images.length,
            children: staffData && staffData.face_images.length > 0 && (_jsx(FaceRecognitionTest, { staffId: staffData.staff_id, staffName: staffData.name }))
        }
    ];
    return (_jsxs(Modal, { title: staffData ? `Staff Details - ${staffData.name}` : 'Staff Details', open: visible, onCancel: handleClose, width: 900, footer: null, destroyOnHidden: true, centered: true, children: [loading && (_jsx("div", { className: "flex justify-center items-center py-12", children: _jsx(Spin, { size: "large" }) })), error && (_jsx(Alert, { message: "Error Loading Staff Details", description: error, type: "error", showIcon: true, action: _jsx(Button, { size: "small", onClick: loadStaffData, children: "Retry" }) })), staffData && !loading && (_jsx(Tabs, { activeKey: activeTab, onChange: setActiveTab, items: tabItems, size: "small" })), !staffData && !loading && !error && (_jsx("div", { className: "text-center py-12 text-gray-400", children: "No staff selected" }))] }));
};
