import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Row, Col, Button, Popconfirm, Spin, Alert, Space, Tag, Tooltip, App, } from 'antd';
import { DeleteOutlined, PictureOutlined, EyeOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import dayjs from 'dayjs';
// const { Text } = Typography;
// SVG placeholder for missing images
const IMAGE_PLACEHOLDER = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+PC9zdmc+';
export const CustomerFaceGallery = ({ customerId, customerName: _customerName, onImagesChange }) => {
    const [images, setImages] = useState([]);
    const [loading, setLoading] = useState(false);
    const { message, modal } = App.useApp();
    const [deleting, setDeleting] = useState(false);
    const [error, setError] = useState(null);
    const [selectedImages, setSelectedImages] = useState(new Set());
    const [lastSelectedIndex, setLastSelectedIndex] = useState(null);
    const [imageUrls, setImageUrls] = useState({});
    // Ref to track if user is holding Shift/Ctrl/Cmd
    const isMultiSelectRef = useRef(false);
    const loadImages = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            // Clear cached image URLs to force refresh
            setImageUrls({});
            const response = await apiClient.getCustomerFaceImages(customerId);
            setImages(response.images || []);
            // Load image URLs for each image
            response.images?.forEach(image => {
                loadImageUrl(image.image_id, image.image_path);
            });
        }
        catch (err) {
            setError(err?.response?.data?.detail || 'Failed to load face images');
        }
        finally {
            setLoading(false);
        }
    }, [customerId]);
    useEffect(() => {
        loadImages();
    }, [loadImages]);
    useEffect(() => {
        // Listen for keyboard events for multi-select
        const handleKeyDown = (e) => {
            if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Meta') {
                isMultiSelectRef.current = true;
            }
        };
        const handleKeyUp = (e) => {
            if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Meta') {
                isMultiSelectRef.current = false;
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        window.addEventListener('keyup', handleKeyUp);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            window.removeEventListener('keyup', handleKeyUp);
        };
    }, []);
    const loadImageUrl = async (imageId, imagePath) => {
        try {
            const url = await apiClient.getImageUrl(imagePath);
            setImageUrls(prev => ({ ...prev, [imageId]: url }));
        }
        catch (error) {
            console.error('Failed to load image:', error);
            setImageUrls(prev => ({ ...prev, [imageId]: IMAGE_PLACEHOLDER }));
        }
    };
    const handleImageClick = useCallback((imageId, index, event) => {
        const isCtrlOrCmd = event.ctrlKey || event.metaKey;
        const isShift = event.shiftKey;
        if (isShift && lastSelectedIndex !== null) {
            // Shift+click: select range
            const start = Math.min(lastSelectedIndex, index);
            const end = Math.max(lastSelectedIndex, index);
            const newSelected = new Set(selectedImages);
            for (let i = start; i <= end; i++) {
                if (images[i]) {
                    newSelected.add(images[i].image_id);
                }
            }
            setSelectedImages(newSelected);
        }
        else if (isCtrlOrCmd) {
            // Ctrl/Cmd+click: toggle individual selection
            const newSelected = new Set(selectedImages);
            if (newSelected.has(imageId)) {
                newSelected.delete(imageId);
            }
            else {
                newSelected.add(imageId);
            }
            setSelectedImages(newSelected);
            setLastSelectedIndex(index);
        }
        else {
            // Normal click: select only this image
            setSelectedImages(new Set([imageId]));
            setLastSelectedIndex(index);
        }
    }, [selectedImages, lastSelectedIndex, images]);
    const handleDeleteSelected = async () => {
        if (selectedImages.size === 0)
            return;
        try {
            setDeleting(true);
            const imageIds = Array.from(selectedImages);
            const response = await apiClient.deleteCustomerFaceImagesBatch(customerId, imageIds);
            // Log response for debugging
            console.log('Delete response:', response);
            message.success(`Successfully deleted ${response.deleted_count} face image${response.deleted_count > 1 ? 's' : ''}`);
            // Clear selection and cached URLs
            setSelectedImages(new Set());
            setLastSelectedIndex(null);
            // Clear cached image URLs for deleted images
            setImageUrls(prev => {
                const updated = { ...prev };
                imageIds.forEach(id => delete updated[id]);
                return updated;
            });
            // Force reload images
            await loadImages();
            if (onImagesChange) {
                onImagesChange();
            }
        }
        catch (err) {
            message.error(err?.response?.data?.detail || 'Failed to delete images');
        }
        finally {
            setDeleting(false);
        }
    };
    const handleSelectAll = () => {
        if (selectedImages.size === images.length) {
            // Deselect all
            setSelectedImages(new Set());
        }
        else {
            // Select all
            setSelectedImages(new Set(images.map(img => img.image_id)));
        }
    };
    const handleViewImage = (image, event) => {
        event.stopPropagation();
        const imageUrl = imageUrls[image.image_id];
        if (imageUrl && imageUrl !== IMAGE_PLACEHOLDER) {
            window.open(imageUrl, '_blank');
        }
        else {
            message.warning('Image is still loading, please try again in a moment');
        }
    };
    const getImageTooltip = (image) => (_jsxs("div", { className: "space-y-2 max-w-xs text-white", children: [_jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "font-medium text-gray-200", children: "Image ID:" }), _jsxs("span", { className: "text-white", children: ["#", image.image_id] })] }), _jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "font-medium text-gray-200", children: "Confidence:" }), _jsxs("span", { className: `px-2 py-0.5 rounded text-xs font-medium ${image.confidence_score > 0.8 ? 'bg-green-600 text-white' : 'bg-orange-600 text-white'}`, children: [(image.confidence_score * 100).toFixed(1), "%"] })] }), image.quality_score && (_jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "font-medium text-gray-200", children: "Quality:" }), _jsxs("span", { className: `px-2 py-0.5 rounded text-xs font-medium ${image.quality_score > 0.8 ? 'bg-green-600 text-white' : 'bg-orange-600 text-white'}`, children: [(image.quality_score * 100).toFixed(1), "%"] })] })), _jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "font-medium text-gray-200", children: "Captured:" }), _jsx("span", { className: "text-xs text-gray-300", children: dayjs(image.created_at).format('MMM D, YYYY HH:mm') })] }), image.visit_id && (_jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "font-medium text-gray-200", children: "Visit ID:" }), _jsx("span", { className: "text-xs font-mono text-gray-300", children: image.visit_id.slice(-8) })] })), image.face_bbox && image.face_bbox.length >= 4 && (_jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "font-medium text-gray-200", children: "Face Size:" }), _jsxs("span", { className: "text-xs text-gray-300", children: [Math.round(image.face_bbox[2]), "\u00D7", Math.round(image.face_bbox[3]), "px"] })] }))] }));
    const renderImage = (image, index) => {
        const isSelected = selectedImages.has(image.image_id);
        return (_jsx(Col, { xs: 24, sm: 12, md: 8, lg: 6, children: _jsx(Card, { hoverable: true, className: `transition-all cursor-pointer ${isSelected
                    ? 'ring-2 ring-blue-500 ring-offset-2 bg-blue-50'
                    : 'hover:shadow-lg'}`, onClick: (e) => handleImageClick(image.image_id, index, e), cover: _jsxs("div", { className: "relative overflow-hidden h-48", children: [_jsx("img", { src: imageUrls[image.image_id] || IMAGE_PLACEHOLDER, alt: `Customer face ${image.image_id}`, className: "w-full h-full object-cover", onError: (e) => {
                                const target = e.target;
                                target.src = IMAGE_PLACEHOLDER;
                            } }), isSelected && (_jsx("div", { className: "absolute inset-0 bg-blue-500 bg-opacity-20 flex items-center justify-center", children: _jsx("div", { className: "bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center", children: "\u2713" }) })), _jsx("div", { className: "absolute top-2 right-2", children: _jsxs(Tag, { color: "blue", className: "text-xs", children: ["#", image.image_id] }) })] }), actions: [
                    _jsx(Tooltip, { title: getImageTooltip(image), children: _jsx(InfoCircleOutlined, { onClick: (e) => {
                                e.stopPropagation();
                            }, className: "text-blue-500 hover:text-blue-600" }) }, "details"),
                    _jsx(Tooltip, { title: "View image in new tab", children: _jsx(EyeOutlined, { onClick: (e) => handleViewImage(image, e), className: "text-green-500 hover:text-green-600" }) }, "view")
                ] }) }, image.image_id));
    };
    if (loading) {
        return (_jsx("div", { className: "flex justify-center items-center py-12", children: _jsx(Spin, { size: "large" }) }));
    }
    if (error) {
        return (_jsx(Alert, { message: "Error Loading Face Images", description: error, type: "error", showIcon: true, action: _jsx(Button, { size: "small", onClick: loadImages, children: "Retry" }) }));
    }
    return (_jsx(_Fragment, { children: _jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center space-x-4", children: [_jsxs(Space, { children: [_jsx(PictureOutlined, {}), _jsxs("span", { className: "font-medium", children: ["Face Gallery (", images.length, " images)"] })] }), images.length > 0 && (_jsxs("div", { className: "flex items-center space-x-2", children: [_jsx(Button, { size: "small", onClick: handleSelectAll, type: selectedImages.size === images.length ? "default" : "link", children: selectedImages.size === images.length ? 'Deselect All' : 'Select All' }), selectedImages.size > 0 && (_jsxs(Tag, { color: "blue", children: [selectedImages.size, " selected"] }))] }))] }), selectedImages.size > 0 && (_jsx(Popconfirm, { title: `Delete ${selectedImages.size} face image${selectedImages.size > 1 ? 's' : ''}?`, description: "This action cannot be undone.", onConfirm: handleDeleteSelected, okText: "Delete", cancelText: "Cancel", okButtonProps: { danger: true }, children: _jsxs(Button, { danger: true, icon: _jsx(DeleteOutlined, {}), loading: deleting, size: "small", children: ["Delete Selected (", selectedImages.size, ")"] }) })), selectedImages.size > 0 && (_jsx(Button, { size: "small", onClick: () => {
                                modal.confirm({
                                    title: `Reassign ${selectedImages.size} image(s)`,
                                    content: (_jsxs("div", { className: "space-y-2 mt-4", children: [_jsx("div", { children: "New customer ID" }), _jsx("input", { id: "reassign-input", className: "w-full border rounded px-2 py-1", placeholder: "Enter customer id" })] })),
                                    okText: 'Reassign',
                                    onOk: async () => {
                                        const input = document.getElementById('reassign-input');
                                        const targetId = parseInt(input?.value || '', 10);
                                        if (!targetId || selectedImages.size === 0)
                                            return;
                                        try {
                                            for (const imgId of Array.from(selectedImages)) {
                                                await apiClient.reassignFaceImage(imgId, targetId);
                                            }
                                            message.success('Images reassigned');
                                            setSelectedImages(new Set());
                                            await loadImages();
                                            onImagesChange?.();
                                        }
                                        catch (e) {
                                            message.error(e?.response?.data?.detail || 'Failed to reassign images');
                                        }
                                    }
                                });
                            }, children: "Reassign Selected\u2026" }))] }), images.length > 1 && (_jsx(Alert, { message: "Multi-Selection Help", description: "Click to select \u2022 Ctrl/\u2318+Click to add to selection \u2022 Shift+Click to select range", type: "info", showIcon: true, className: "text-sm" })), images.length === 0 ? (_jsxs("div", { className: "text-center py-12", children: [_jsx(PictureOutlined, { className: "text-4xl text-gray-400 mb-4" }), _jsxs("div", { className: "text-gray-500", children: [_jsx("div", { className: "font-medium", children: "No face images yet" }), _jsx("div", { className: "text-sm mt-1", children: "Face images will be automatically captured and saved when this customer visits." })] })] })) : (_jsx(Row, { gutter: [16, 16], children: images.map(renderImage) }))] }) }));
};
