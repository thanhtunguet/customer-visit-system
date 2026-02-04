import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useCallback } from 'react';
import { Modal, Typography, Button, Table, Space, Alert, Spin, Input, message } from 'antd';
import { MergeOutlined, UserOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { AuthenticatedAvatar } from './AuthenticatedAvatar';
import dayjs from 'dayjs';
const { Title, Text } = Typography;
const { TextArea } = Input;
export const CustomerMergeModal = ({ visible, customer, onClose, onMergeComplete }) => {
    const [loading, setLoading] = useState(false);
    const [merging, setMerging] = useState(false);
    const [similarCustomers, setSimilarCustomers] = useState([]);
    const [selectedCustomer, setSelectedCustomer] = useState(null);
    const [mergeNotes, setMergeNotes] = useState('');
    const loadSimilarCustomers = useCallback(async () => {
        if (!customer)
            return;
        try {
            setLoading(true);
            const result = await apiClient.findSimilarCustomers(customer.customer_id, {
                threshold: 0.85,
                limit: 10
            });
            setSimilarCustomers(result.similar_customers);
        }
        catch (error) {
            message.error('Failed to find similar customers');
            console.error('Error finding similar customers:', error);
        }
        finally {
            setLoading(false);
        }
    }, [customer]);
    useEffect(() => {
        if (visible && customer) {
            loadSimilarCustomers();
            setSelectedCustomer(null);
            setMergeNotes('');
        }
    }, [visible, customer, loadSimilarCustomers]);
    const handleMerge = async () => {
        if (!customer || !selectedCustomer)
            return;
        try {
            setMerging(true);
            const result = await apiClient.mergeCustomers(customer.customer_id, selectedCustomer.customer_id, mergeNotes || undefined);
            message.success(`Successfully merged customers. Combined ${result.merged_visits} visits and ${result.merged_face_images} face images.`);
            onMergeComplete();
            onClose();
        }
        catch (error) {
            message.error(error?.response?.data?.detail || 'Failed to merge customers');
            console.error('Error merging customers:', error);
        }
        finally {
            setMerging(false);
        }
    };
    const columns = [
        {
            title: 'Avatar',
            key: 'avatar',
            width: 60,
            render: () => (_jsx(AuthenticatedAvatar, { size: 40, icon: _jsx(UserOutlined, {}) })),
        },
        {
            title: 'Customer Info',
            key: 'info',
            render: (record) => (_jsxs("div", { children: [_jsx(Text, { strong: true, children: record.name || `Customer ${record.customer_id}` }), _jsx("br", {}), _jsxs(Text, { type: "secondary", style: { fontSize: '12px' }, children: [record.visit_count, " visits \u2022 ", record.gender, " \u2022 ", record.estimated_age_range] })] })),
        },
        {
            title: 'Last Seen',
            key: 'last_seen',
            render: (record) => (_jsx(Text, { type: "secondary", children: record.last_seen ? dayjs(record.last_seen).format('MMM D, YYYY') : 'Unknown' })),
        },
        {
            title: 'Similarity',
            key: 'similarity',
            render: (record) => {
                const similarity = Math.round(record.max_similarity * 100);
                const color = similarity >= 95 ? '#52c41a' : similarity >= 90 ? '#faad14' : '#1890ff';
                return (_jsxs(Text, { style: { color, fontWeight: 'bold' }, children: [similarity, "%"] }));
            },
        },
        {
            title: 'Action',
            key: 'action',
            render: (record) => (_jsx(Button, { type: selectedCustomer?.customer_id === record.customer_id ? 'primary' : 'default', size: "small", onClick: () => setSelectedCustomer(selectedCustomer?.customer_id === record.customer_id ? null : record), children: selectedCustomer?.customer_id === record.customer_id ? 'Selected' : 'Select' })),
        },
    ];
    if (!customer)
        return null;
    return (_jsx(Modal, { title: _jsxs(Space, { children: [_jsx(MergeOutlined, {}), _jsx("span", { children: "Merge Similar Customers" })] }), open: visible, onCancel: onClose, width: 800, footer: [
            _jsx(Button, { onClick: onClose, children: "Cancel" }, "cancel"),
            _jsx(Button, { type: "primary", danger: true, icon: _jsx(MergeOutlined, {}), onClick: handleMerge, loading: merging, disabled: !selectedCustomer, children: "Merge Selected Customer" }, "merge"),
        ], children: _jsxs(Space, { direction: "vertical", style: { width: '100%' }, size: "large", children: [_jsx(Alert, { message: "Customer Merge", description: _jsxs("div", { children: [_jsxs("p", { children: [_jsx("strong", { children: "Primary Customer:" }), " ", customer.name || `Customer ${customer.customer_id}`, " (", customer.visit_count, " visits)"] }), _jsx("p", { children: "The selected customer will be merged into this primary customer. All visits and face images will be transferred, and the selected customer will be marked as merged." })] }), type: "info", showIcon: true }), _jsxs("div", { children: [_jsx(Title, { level: 4, children: "Similar Customers Found" }), loading ? (_jsxs("div", { style: { textAlign: 'center', padding: '40px' }, children: [_jsx(Spin, { size: "large" }), _jsx("p", { children: "Finding similar customers..." })] })) : similarCustomers.length === 0 ? (_jsx(Alert, { message: "No similar customers found", description: "No customers with high similarity scores were found. Try adjusting the similarity threshold or check if the customer has sufficient face images for comparison.", type: "warning", showIcon: true })) : (_jsx(Table, { columns: columns, dataSource: similarCustomers, rowKey: "customer_id", pagination: false, size: "small" }))] }), selectedCustomer && (_jsxs("div", { children: [_jsx(Title, { level: 5, children: "Merge Notes (Optional)" }), _jsx(TextArea, { rows: 3, placeholder: "Add any notes about why these customers are being merged...", value: mergeNotes, onChange: (e) => setMergeNotes(e.target.value) })] })), selectedCustomer && (_jsx(Alert, { message: "Merge Confirmation", description: _jsxs("div", { children: [_jsx("p", { children: _jsx("strong", { children: "This action cannot be undone!" }) }), _jsx("p", { children: "Merging will:" }), _jsxs("ul", { children: [_jsxs("li", { children: ["Transfer all visits from ", _jsx("strong", { children: selectedCustomer.name || `Customer ${selectedCustomer.customer_id}` }), " to ", _jsx("strong", { children: customer.name || `Customer ${customer.customer_id}` })] }), _jsx("li", { children: "Transfer all face images and embeddings" }), _jsx("li", { children: "Update visit counts and date ranges" }), _jsx("li", { children: "Mark the selected customer as merged (soft delete)" })] })] }), type: "warning", showIcon: true }))] }) }));
};
