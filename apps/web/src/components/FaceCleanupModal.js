import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect, useCallback } from 'react';
import { Modal, Typography, Button, Slider, Alert, Space, Statistic, Row, Col, message, Spin } from 'antd';
import { DeleteOutlined, ClearOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
const { Title, Text } = Typography;
export const FaceCleanupModal = ({ visible, customer, onClose, onCleanupComplete }) => {
    const [loading, setLoading] = useState(false);
    const [cleaning, setCleaning] = useState(false);
    const [stats, setStats] = useState(null);
    const [confidenceThreshold, setConfidenceThreshold] = useState(0.7);
    const [maxToRemove, setMaxToRemove] = useState(10);
    const loadCustomerStats = useCallback(async () => {
        if (!customer)
            return;
        try {
            setLoading(true);
            const result = await apiClient.getCustomerFaceImages(customer.customer_id);
            // Calculate stats from face images
            const images = result.images;
            if (images.length > 0) {
                const confidenceScores = images.map(img => img.confidence_score);
                const qualityScores = images.map(img => img.quality_score);
                const statsData = {
                    customer_id: customer.customer_id,
                    total_images: images.length,
                    avg_confidence: confidenceScores.reduce((a, b) => a + b, 0) / confidenceScores.length,
                    max_confidence: Math.max(...confidenceScores),
                    min_confidence: Math.min(...confidenceScores),
                    avg_quality: qualityScores.reduce((a, b) => a + b, 0) / qualityScores.length,
                    first_image_date: images[images.length - 1]?.created_at,
                    latest_image_date: images[0]?.created_at
                };
                setStats(statsData);
            }
        }
        catch (error) {
            message.error('Failed to load customer statistics');
            console.error('Error loading customer stats:', error);
        }
        finally {
            setLoading(false);
        }
    }, [customer]);
    useEffect(() => {
        if (visible && customer) {
            loadCustomerStats();
        }
    }, [visible, customer, loadCustomerStats]);
    const handleCleanup = async () => {
        if (!customer)
            return;
        try {
            setCleaning(true);
            const result = await apiClient.cleanupLowConfidenceFaces(customer.customer_id, {
                min_confidence: confidenceThreshold,
                max_to_remove: maxToRemove
            });
            message.success(`Successfully removed ${result.removed_count} low-confidence face detections`);
            onCleanupComplete();
            onClose();
        }
        catch (error) {
            message.error(error?.response?.data?.detail || 'Failed to cleanup face detections');
            console.error('Error cleaning up faces:', error);
        }
        finally {
            setCleaning(false);
        }
    };
    const estimateDeletions = () => {
        if (!stats)
            return 0;
        // This is an estimation - in practice you'd need an additional API call to get exact count
        const estimatedLowConfidence = Math.round(stats.total_images * 0.3); // Rough estimate
        return Math.min(estimatedLowConfidence, maxToRemove);
    };
    if (!customer)
        return null;
    return (_jsx(Modal, { title: _jsxs(Space, { children: [_jsx(ClearOutlined, {}), _jsx("span", { children: "Cleanup Low-Quality Face Detections" })] }), open: visible, onCancel: onClose, width: 600, footer: [
            _jsx(Button, { onClick: onClose, children: "Cancel" }, "cancel"),
            _jsx(Button, { type: "primary", danger: true, icon: _jsx(DeleteOutlined, {}), onClick: handleCleanup, loading: cleaning, disabled: !stats || stats.total_images === 0, children: "Remove Low-Quality Detections" }, "cleanup"),
        ], children: _jsxs(Space, { direction: "vertical", style: { width: '100%' }, size: "large", children: [_jsx(Alert, { message: "Face Detection Cleanup", description: _jsxs("div", { children: [_jsxs("p", { children: [_jsx("strong", { children: "Customer:" }), " ", customer.name || `Customer ${customer.customer_id}`] }), _jsx("p", { children: "Remove low-confidence face detections to improve data quality. This will delete both the detection records and associated images." })] }), type: "info", showIcon: true }), loading ? (_jsxs("div", { style: { textAlign: 'center', padding: '40px' }, children: [_jsx(Spin, { size: "large" }), _jsx("p", { children: "Loading customer face statistics..." })] })) : stats ? (_jsxs(_Fragment, { children: [_jsxs("div", { children: [_jsx(Title, { level: 4, children: "Current Face Gallery Statistics" }), _jsxs(Row, { gutter: 16, children: [_jsx(Col, { span: 8, children: _jsx(Statistic, { title: "Total Images", value: stats.total_images, valueStyle: { color: '#1890ff' } }) }), _jsx(Col, { span: 8, children: _jsx(Statistic, { title: "Avg Confidence", value: Math.round(stats.avg_confidence * 100), suffix: "%", valueStyle: { color: stats.avg_confidence >= 0.8 ? '#52c41a' : stats.avg_confidence >= 0.6 ? '#faad14' : '#ff4d4f' } }) }), _jsx(Col, { span: 8, children: _jsx(Statistic, { title: "Min Confidence", value: Math.round(stats.min_confidence * 100), suffix: "%", valueStyle: { color: stats.min_confidence >= 0.7 ? '#52c41a' : '#ff4d4f' } }) })] })] }), _jsxs("div", { children: [_jsx(Title, { level: 5, children: "Cleanup Parameters" }), _jsxs(Space, { direction: "vertical", style: { width: '100%' }, children: [_jsxs("div", { children: [_jsxs(Text, { strong: true, children: ["Confidence Threshold: ", Math.round(confidenceThreshold * 100), "%"] }), _jsx(Slider, { min: 0.3, max: 0.9, step: 0.05, value: confidenceThreshold, onChange: setConfidenceThreshold, marks: {
                                                        0.3: '30%',
                                                        0.5: '50%',
                                                        0.7: '70%',
                                                        0.9: '90%'
                                                    }, tooltip: { formatter: (value) => `${Math.round((value || 0) * 100)}%` } }), _jsx(Text, { type: "secondary", children: "Remove face detections with confidence below this threshold" })] }), _jsxs("div", { children: [_jsxs(Text, { strong: true, children: ["Maximum to Remove: ", maxToRemove] }), _jsx(Slider, { min: 1, max: 50, step: 1, value: maxToRemove, onChange: setMaxToRemove, marks: {
                                                        1: '1',
                                                        10: '10',
                                                        25: '25',
                                                        50: '50'
                                                    } }), _jsx(Text, { type: "secondary", children: "Limit the number of detections removed in one operation" })] })] })] }), _jsx(Alert, { message: "Estimated Impact", description: _jsxs("div", { children: [_jsxs("p", { children: [_jsxs("strong", { children: ["Approximately ", estimateDeletions(), " detections"] }), " will be removed based on current parameters."] }), _jsxs("p", { children: [_jsx("strong", { children: "This action cannot be undone!" }), " Removed detections and their associated images will be permanently deleted."] })] }), type: "warning", showIcon: true })] })) : (_jsx(Alert, { message: "No face images found", description: "This customer has no face images to cleanup.", type: "info", showIcon: true }))] }) }));
};
