import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Upload, Button, Card, Progress, Alert, Table, Space, Typography, Tag, Image, Divider, } from 'antd';
import { UploadOutlined, CheckCircleOutlined, CloseCircleOutlined, ExperimentOutlined, } from '@ant-design/icons';
import { apiClient } from '../services/api';
const { Title, Text } = Typography;
export const FaceRecognitionTest = ({ staffId, staffName, }) => {
    const [testImage, setTestImage] = useState(null);
    const [testImageUrl, setTestImageUrl] = useState(null);
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState(null);
    const [error, setError] = useState(null);
    // Handle test image upload
    const handleImageUpload = async (file) => {
        try {
            // Convert to base64
            const base64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            setTestImage(base64);
            setTestImageUrl(URL.createObjectURL(file));
            setTestResult(null);
            setError(null);
        }
        catch (error) {
            setError('Failed to process image');
        }
    };
    // Run recognition test
    const runTest = async () => {
        if (!testImage)
            return;
        try {
            setTesting(true);
            setError(null);
            const result = await apiClient.testFaceRecognition(staffId, testImage);
            setTestResult(result);
        }
        catch (error) {
            setError(error?.response?.data?.detail || 'Recognition test failed');
            setTestResult(null);
        }
        finally {
            setTesting(false);
        }
    };
    // Clear test
    const clearTest = () => {
        setTestImage(null);
        setTestImageUrl(null);
        setTestResult(null);
        setError(null);
    };
    const getSimilarityColor = (similarity) => {
        if (similarity >= 0.9)
            return 'success';
        if (similarity >= 0.7)
            return 'active';
        return 'exception';
    };
    const getSimilarityTagColor = (similarity) => {
        if (similarity >= 0.9)
            return 'success';
        if (similarity >= 0.7)
            return 'warning';
        return 'error';
    };
    const getSimilarityText = (similarity) => {
        if (similarity >= 0.9)
            return 'Excellent Match';
        if (similarity >= 0.7)
            return 'Good Match';
        if (similarity >= 0.5)
            return 'Weak Match';
        return 'No Match';
    };
    const columns = [
        {
            title: 'Rank',
            dataIndex: 'rank',
            key: 'rank',
            width: 60,
            render: (_, __, index) => (_jsx("div", { className: `w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${index === 0
                    ? 'bg-gold text-white'
                    : index === 1
                        ? 'bg-gray-400 text-white'
                        : index === 2
                            ? 'bg-orange-400 text-white'
                            : 'bg-gray-200 text-gray-600'}`, children: index + 1 })),
        },
        {
            title: 'Staff Name',
            dataIndex: 'staff_name',
            key: 'staff_name',
            render: (name, record) => (_jsxs(Space, { children: [_jsx("span", { className: "font-medium", children: name }), record.staff_id === staffId && (_jsx(Tag, { color: "blue", className: "text-xs", children: "Target" }))] })),
        },
        {
            title: 'Staff ID',
            dataIndex: 'staff_id',
            key: 'staff_id',
            render: (id) => (_jsx("span", { className: "font-mono text-sm text-gray-600", children: id })),
        },
        {
            title: 'Similarity',
            dataIndex: 'similarity',
            key: 'similarity',
            render: (similarity) => (_jsxs(Space, { direction: "vertical", size: "small", className: "w-full", children: [_jsx(Progress, { percent: similarity * 100, size: "small", status: getSimilarityColor(similarity), showInfo: false }), _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("span", { className: "text-xs font-mono", children: [(similarity * 100).toFixed(1), "%"] }), _jsx(Tag, { color: getSimilarityTagColor(similarity), className: "text-xs", children: getSimilarityText(similarity) })] })] })),
        },
    ];
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs(Title, { level: 4, className: "mb-0", children: [_jsx(ExperimentOutlined, { className: "mr-2" }), "Customer Recognition Test"] }), testImage && _jsx(Button, { onClick: clearTest, children: "Clear Test" })] }), _jsx(Alert, { message: "Test Recognition Accuracy", description: `Upload a photo to test how well the system can recognize ${staffName}. The system will compare against all enrolled staff members.`, type: "info", showIcon: true }), _jsx(Card, { children: _jsx("div", { className: "text-center space-y-2", children: !testImageUrl ? (_jsxs(Upload.Dragger, { accept: "image/*", showUploadList: false, beforeUpload: (file) => {
                            handleImageUpload(file);
                            return false;
                        }, className: "rounded-lg p-6", children: [_jsx("p", { className: "ant-upload-drag-icon", children: _jsx(UploadOutlined, { className: "text-4xl text-gray-400" }) }), _jsx("p", { className: "ant-upload-text", children: "Click or drag a test image here" }), _jsx("p", { className: "ant-upload-hint", children: "Supports JPG, PNG, GIF formats. Best results with clear face photos." })] })) : (_jsxs("div", { className: "space-y-4", children: [_jsx("div", { className: "flex justify-center", children: _jsx(Image, { src: testImageUrl, alt: "Test image", style: { maxWidth: 300, maxHeight: 300 }, className: "rounded-lg shadow-md" }) }), _jsx(Button, { type: "primary", icon: _jsx(ExperimentOutlined, {}), loading: testing, onClick: runTest, size: "large", children: "Run Recognition Test" })] })) }) }), error && (_jsx(Alert, { message: "Test Failed", description: error, type: "error", showIcon: true, closable: true, onClose: () => setError(null) })), testResult && (_jsxs("div", { className: "space-y-4", children: [_jsx(Divider, { children: "Recognition Results" }), _jsx(Card, { size: "small", children: _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 text-center", children: [_jsxs("div", { children: [_jsx("div", { className: "text-2xl font-bold text-blue-600", children: testResult.processing_info.test_face_detected ? (_jsx(CheckCircleOutlined, {})) : (_jsx(CloseCircleOutlined, {})) }), _jsx("div", { className: "text-sm text-gray-600", children: "Face Detection" }), _jsx("div", { className: "text-xs text-gray-400", children: testResult.processing_info.test_face_detected
                                                ? 'Success'
                                                : 'Failed' })] }), _jsxs("div", { children: [_jsxs("div", { className: "text-2xl font-bold text-green-600", children: [(testResult.processing_info.test_confidence * 100).toFixed(1), "%"] }), _jsx("div", { className: "text-sm text-gray-600", children: "Detection Confidence" }), _jsx("div", { className: "text-xs text-gray-400", children: "Face quality score" })] }), _jsxs("div", { children: [_jsx("div", { className: "text-2xl font-bold text-purple-600", children: testResult.processing_info.total_staff_compared }), _jsx("div", { className: "text-sm text-gray-600", children: "Staff Compared" }), _jsx("div", { className: "text-xs text-gray-400", children: "Total enrolled faces" })] })] }) }), testResult.best_match && (_jsx(Card, { size: "small", children: _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { children: [_jsx(Text, { strong: true, className: "text-green-600", children: "Best Match Found" }), _jsx("div", { className: "mt-1", children: _jsxs(Space, { children: [_jsx("span", { className: "font-medium", children: testResult.best_match.staff_name }), _jsxs(Tag, { color: "blue", children: ["ID: ", testResult.best_match.staff_id] }), testResult.best_match.staff_id === staffId && (_jsx(Tag, { color: "success", children: "\u2713 Correct Match" }))] }) })] }), _jsxs("div", { className: "text-right", children: [_jsxs("div", { className: "text-2xl font-bold text-green-600", children: [(testResult.best_match.similarity * 100).toFixed(1), "%"] }), _jsx("div", { className: "text-sm text-gray-600", children: "Similarity" })] })] }) })), _jsx(Card, { title: "All Recognition Results", size: "small", children: _jsx(Table, { columns: columns, dataSource: testResult.matches, rowKey: (record) => `${record.staff_id}-${record.image_id || 'primary'}`, pagination: false, size: "small" }) }), testResult.matches.length > 0 && (_jsx(Card, { title: "Analysis", size: "small", children: _jsxs("div", { className: "space-y-2 text-sm", children: [testResult.best_match?.staff_id === staffId ? (_jsxs("div", { className: "flex items-center space-x-2 text-green-600", children: [_jsx(CheckCircleOutlined, {}), _jsxs("span", { children: ["Recognition successful! The system correctly identified", ' ', staffName, "."] })] })) : (_jsxs("div", { className: "flex items-center space-x-2 text-red-600", children: [_jsx(CloseCircleOutlined, {}), _jsx("span", { children: "Recognition failed. The system identified a different person or no one above the confidence threshold." })] })), _jsxs("div", { className: "text-gray-600", children: [_jsx("strong", { children: "Recommendations:" }), testResult.processing_info.test_confidence < 0.8 && (_jsxs("span", { children: [' ', "Try using a clearer image with better lighting and a direct face view."] })), testResult.best_match &&
                                            testResult.best_match.similarity < 0.7 && (_jsxs("span", { children: [' ', "Consider adding more face images to improve recognition accuracy."] }))] })] }) }))] }))] }));
};
