import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useRef, useCallback } from 'react';
import { Upload, Button, Modal, Card, Image, Tag, Space, Popconfirm, Spin, Alert, Tooltip, Badge, Progress, Select, App } from 'antd';
import { UploadOutlined, DeleteOutlined, ReloadOutlined, EyeOutlined, StarOutlined, StarFilled, CameraOutlined, SwitcherOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
const LandmarksOverlay = ({ landmarks, imageWidth, imageHeight, naturalWidth, naturalHeight, showConnections = false }) => {
    const scaleX = imageWidth / naturalWidth;
    const scaleY = imageHeight / naturalHeight;
    return (_jsxs("svg", { style: {
            position: 'absolute',
            left: 0,
            top: 0,
            width: imageWidth,
            height: imageHeight,
            pointerEvents: 'none'
        }, viewBox: `0 0 ${imageWidth} ${imageHeight}`, children: [landmarks.map(([x, y], idx) => {
                const scaledX = x * scaleX;
                const scaledY = y * scaleY;
                return (_jsx("circle", { cx: scaledX, cy: scaledY, r: showConnections ? 3 : 2, fill: "rgba(34, 197, 94, 0.8)", stroke: "white", strokeWidth: 1 }, idx));
            }), showConnections && landmarks.length === 5 && (_jsxs("g", { stroke: "rgba(34, 197, 94, 0.6)", strokeWidth: 1, fill: "none", children: [_jsx("line", { x1: landmarks[0][0] * scaleX, y1: landmarks[0][1] * scaleY, x2: landmarks[1][0] * scaleX, y2: landmarks[1][1] * scaleY }), _jsx("line", { x1: landmarks[2][0] * scaleX, y1: landmarks[2][1] * scaleY, x2: landmarks[3][0] * scaleX, y2: landmarks[3][1] * scaleY }), _jsx("line", { x1: landmarks[2][0] * scaleX, y1: landmarks[2][1] * scaleY, x2: landmarks[4][0] * scaleX, y2: landmarks[4][1] * scaleY })] }))] }));
};
export const StaffFaceGallery = ({ staffId, staffName, faceImages, onImagesChange }) => {
    const [uploading, setUploading] = useState(false);
    const { message } = App.useApp();
    const [uploadProgress, setUploadProgress] = useState(null);
    const [uploadController, setUploadController] = useState(null);
    const [recalculatingId, setRecalculatingId] = useState(null);
    const [recalculatingAll, setRecalculatingAll] = useState(false);
    const [previewVisible, setPreviewVisible] = useState(false);
    const [previewImage, setPreviewImage] = useState('');
    const [previewTitle, setPreviewTitle] = useState('');
    const [previewLandmarks, setPreviewLandmarks] = useState(null);
    const [renderSize, setRenderSize] = useState({
        width: 0,
        height: 0,
        naturalWidth: 0,
        naturalHeight: 0,
    });
    const [thumbnailSizes, setThumbnailSizes] = useState({});
    const [cameraModalVisible, setCameraModalVisible] = useState(false);
    const [cameraStream, setCameraStream] = useState(null);
    const [availableCameras, setAvailableCameras] = useState([]);
    const [selectedCameraId, setSelectedCameraId] = useState('');
    const [capturingPhoto, setCapturingPhoto] = useState(false);
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    // Convert image path to full URL
    const getImageUrl = (imagePath) => {
        const baseUrl = import.meta.env?.VITE_API_URL || 'http://localhost:8080';
        const token = localStorage.getItem('access_token');
        const url = new URL(`${baseUrl}/v1/files/${imagePath}`);
        if (token) {
            url.searchParams.set('access_token', token);
        }
        return url.toString();
    };
    // Handle single file upload
    const handleUpload = async (file, isPrimary = false) => {
        try {
            setUploading(true);
            // Convert file to base64
            const base64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            await apiClient.uploadStaffFaceImage(staffId, base64, isPrimary);
            message.success('Face image uploaded successfully');
            onImagesChange();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to upload image');
        }
        finally {
            setUploading(false);
        }
    };
    // Handle multiple files upload with chunked processing
    const handleMultipleUpload = async (files) => {
        if (files.length === 0)
            return;
        const CHUNK_SIZE = 3; // Process 3 images at a time to avoid timeout
        const MAX_RETRIES = 2;
        const controller = new AbortController();
        try {
            setUploading(true);
            setUploadController(controller);
            setUploadProgress({ current: 0, total: files.length, canCancel: true });
            let successCount = 0;
            let errorCount = 0;
            const failedFiles = [];
            // Process files in chunks
            for (let chunkStart = 0; chunkStart < files.length; chunkStart += CHUNK_SIZE) {
                const chunk = files.slice(chunkStart, Math.min(chunkStart + CHUNK_SIZE, files.length));
                // Convert chunk to base64 with progress tracking
                const chunkPromises = chunk.map(async (file, index) => {
                    const globalIndex = chunkStart + index;
                    setUploadProgress({
                        current: globalIndex,
                        total: files.length,
                        currentFileName: file.name
                    });
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve({
                            data: reader.result,
                            name: file.name,
                            originalFile: file
                        });
                        reader.onerror = reject;
                        reader.readAsDataURL(file);
                    });
                });
                const chunkData = await Promise.all(chunkPromises);
                // Try bulk upload for this chunk first, then fall back to individual
                let chunkProcessed = false;
                if (chunkData.length > 1) {
                    try {
                        const bulkData = chunkData.map((img, index) => ({
                            image_data: img.data,
                            is_primary: faceImages.length === 0 && chunkStart === 0 && index === 0
                        }));
                        const bulkResult = await apiClient.uploadMultipleStaffFaceImages(staffId, bulkData.map(d => d.image_data));
                        // Check if bulk upload actually succeeded by verifying response
                        if (bulkResult && Array.isArray(bulkResult) && bulkResult.length > 0) {
                            successCount += bulkResult.length;
                            chunkProcessed = true;
                            console.log(`Bulk upload succeeded for ${bulkResult.length} out of ${chunkData.length} images`);
                            // If bulk upload was partial, we need to track which ones failed
                            if (bulkResult.length < chunkData.length) {
                                const failedCount = chunkData.length - bulkResult.length;
                                errorCount += failedCount;
                                for (let i = bulkResult.length; i < chunkData.length; i++) {
                                    failedFiles.push(`${chunkData[i].name} (bulk upload partial failure)`);
                                }
                            }
                        }
                        else {
                            console.warn('Bulk upload returned invalid or empty response, falling back to individual uploads');
                        }
                    }
                    catch (bulkError) {
                        console.warn('Bulk upload failed for chunk, falling back to individual uploads:', bulkError);
                        // Don't set chunkProcessed = true here, so we fall back to individual processing
                    }
                }
                // If bulk upload failed completely or we have only one image, process individually
                if (!chunkProcessed) {
                    for (let i = 0; i < chunkData.length; i++) {
                        const img = chunkData[i];
                        let uploaded = false;
                        // Retry logic for individual uploads with exponential backoff
                        for (let attempt = 0; attempt < MAX_RETRIES && !uploaded; attempt++) {
                            try {
                                setUploadProgress({
                                    current: chunkStart + i,
                                    total: files.length,
                                    currentFileName: `${img.name}${attempt > 0 ? ` (retry ${attempt})` : ''}`
                                });
                                const isPrimary = faceImages.length === 0 && chunkStart === 0 && i === 0;
                                await apiClient.uploadStaffFaceImage(staffId, img.data, isPrimary);
                                successCount++;
                                uploaded = true;
                            }
                            catch (error) {
                                const axiosError = error;
                                const isTimeoutError = axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout');
                                const isServerError = (axiosError.response?.status ?? 0) >= 500;
                                console.warn(`Upload attempt ${attempt + 1} failed for ${img.name}:`, error);
                                if (attempt === MAX_RETRIES - 1) {
                                    errorCount++;
                                    failedFiles.push(`${img.name}${isTimeoutError ? ' (timeout)' : isServerError ? ' (server error)' : ''}`);
                                }
                                else {
                                    // Exponential backoff: 1s, 2s, 4s...
                                    const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
                                    await new Promise(resolve => setTimeout(resolve, delay));
                                }
                            }
                        }
                    }
                }
                // Small delay between chunks to prevent overwhelming the server
                if (chunkStart + CHUNK_SIZE < files.length) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }
            // Show final results
            if (successCount > 0 && errorCount === 0) {
                message.success(`All ${successCount} face images uploaded successfully`);
            }
            else if (successCount > 0) {
                message.warning(`${successCount} images uploaded successfully, ${errorCount} failed${failedFiles.length > 0 ? `: ${failedFiles.join(', ')}` : ''}`);
            }
            else {
                message.error(`Failed to upload all images${failedFiles.length > 0 ? `: ${failedFiles.join(', ')}` : ''}`);
            }
            onImagesChange();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to upload images');
        }
        finally {
            setUploading(false);
            setUploadProgress(null);
            setUploadController(null);
        }
    };
    // Cancel upload function
    const cancelUpload = () => {
        if (uploadController) {
            uploadController.abort();
            setUploading(false);
            setUploadProgress(null);
            setUploadController(null);
            message.info('Upload cancelled by user');
        }
    };
    // Get available cameras
    const getAvailableCameras = useCallback(async () => {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const cameras = devices.filter(device => device.kind === 'videoinput');
            setAvailableCameras(cameras);
            if (cameras.length > 0 && !selectedCameraId) {
                setSelectedCameraId(cameras[0].deviceId);
            }
            return cameras;
        }
        catch (error) {
            console.error('Error getting cameras:', error);
            message.error('Failed to access camera devices');
            return [];
        }
    }, [selectedCameraId, message]);
    // Start camera stream
    const startCamera = useCallback(async (deviceId) => {
        try {
            // Stop existing stream first
            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop());
            }
            const constraints = {
                video: {
                    deviceId: deviceId ? { exact: deviceId } : undefined,
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: deviceId ? undefined : 'user'
                },
                audio: false
            };
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            setCameraStream(stream);
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
            return stream;
        }
        catch (error) {
            console.error('Error starting camera:', error);
            message.error('Failed to start camera. Please check camera permissions.');
            return null;
        }
    }, [cameraStream, message]);
    // Stop camera stream
    const stopCamera = useCallback(() => {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            setCameraStream(null);
        }
        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }
    }, [cameraStream]);
    // Open camera modal
    const openCameraModal = async () => {
        setCameraModalVisible(true);
        await getAvailableCameras();
        await startCamera(selectedCameraId);
    };
    // Close camera modal
    const closeCameraModal = () => {
        stopCamera();
        setCameraModalVisible(false);
        setCapturingPhoto(false);
    };
    // Switch camera
    const switchCamera = async (deviceId) => {
        setSelectedCameraId(deviceId);
        await startCamera(deviceId);
    };
    // Capture photo from webcam
    const capturePhoto = async (isPrimary = false) => {
        if (!videoRef.current || !canvasRef.current) {
            message.error('Camera not ready');
            return;
        }
        try {
            setCapturingPhoto(true);
            const video = videoRef.current;
            const canvas = canvasRef.current;
            const ctx = canvas.getContext('2d');
            if (!ctx) {
                throw new Error('Failed to get canvas context');
            }
            // Set canvas size to match video
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            // Draw video frame to canvas
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            // Convert canvas to base64
            const base64 = canvas.toDataURL('image/jpeg', 0.8);
            // Upload the captured image
            await apiClient.uploadStaffFaceImage(staffId, base64, isPrimary);
            message.success('Photo captured and uploaded successfully');
            onImagesChange();
            closeCameraModal();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to capture photo');
        }
        finally {
            setCapturingPhoto(false);
        }
    };
    // Handle image deletion
    const handleDelete = async (imageId) => {
        try {
            await apiClient.deleteStaffFaceImage(staffId, imageId);
            message.success('Face image deleted successfully');
            onImagesChange();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to delete image');
        }
    };
    // Handle recalculation
    const handleRecalculate = async (imageId) => {
        try {
            setRecalculatingId(imageId);
            const result = await apiClient.recalculateFaceEmbedding(staffId, imageId);
            message.success(`${result.message} (Confidence: ${(result.processing_info.confidence * 100).toFixed(1)}%)`);
            onImagesChange();
        }
        catch (error) {
            const axiosError = error;
            message.error(axiosError.response?.data?.detail || 'Failed to recalculate embedding');
        }
        finally {
            setRecalculatingId(null);
        }
    };
    // Handle recalculating all face images
    const handleRecalculateAll = async () => {
        if (faceImages.length === 0) {
            message.info('No face images to recalculate');
            return;
        }
        try {
            setRecalculatingAll(true);
            let successCount = 0;
            let failureCount = 0;
            const errors = [];
            // Process each image sequentially to avoid overwhelming the server
            for (const image of faceImages) {
                try {
                    await apiClient.recalculateFaceEmbedding(staffId, image.image_id);
                    successCount++;
                    // Show progress for each successful recalculation
                    message.info(`Recalculated ${image.image_id.slice(0, 8)}... (${successCount}/${faceImages.length})`);
                }
                catch (error) {
                    const axiosError = error;
                    failureCount++;
                    const errorMsg = axiosError.response?.data?.detail || 'Failed to recalculate';
                    errors.push(`${image.image_id.slice(0, 8)}: ${errorMsg}`);
                }
                // Small delay between requests to prevent rate limiting
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            // Show final results
            if (successCount === faceImages.length) {
                message.success(`Successfully recalculated all ${successCount} face images`);
            }
            else if (successCount > 0) {
                message.warning(`Recalculated ${successCount} images successfully, ${failureCount} failed. ${errors.length > 0 ? `Errors: ${errors.join(', ')}` : ''}`);
            }
            else {
                message.error(`Failed to recalculate all images. ${errors.length > 0 ? `Errors: ${errors.join(', ')}` : ''}`);
            }
            // Refresh the image list
            onImagesChange();
        }
        catch (error) {
            console.error('Failed to recalculate face images:', error);
            message.error('Failed to recalculate face images');
        }
        finally {
            setRecalculatingAll(false);
        }
    };
    // Handle image preview
    const handlePreview = (image) => {
        setPreviewImage(getImageUrl(image.image_path));
        setPreviewTitle(`${staffName} - Image ${image.image_id.slice(0, 8)}`);
        setPreviewLandmarks(image.face_landmarks ?? null);
        setPreviewVisible(true);
    };
    // const primaryImage = faceImages.find(img => img.is_primary);
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("h3", { className: "text-lg font-medium", children: ["Face Images (", faceImages.length, ")"] }), _jsxs(Space, { children: [_jsx(Upload, { accept: "image/*", multiple: true, showUploadList: false, beforeUpload: (file, fileList) => {
                                    if (fileList.length > 1) {
                                        // Handle multiple files
                                        handleMultipleUpload(fileList);
                                    }
                                    else {
                                        // Handle single file
                                        handleUpload(file, faceImages.length === 0);
                                    }
                                    return false; // Prevent default upload
                                }, disabled: uploading, children: _jsx(Button, { type: "primary", icon: _jsx(UploadOutlined, {}), loading: uploading, children: "Add Images" }) }), faceImages.length === 0 && (_jsx(Upload, { accept: "image/*", showUploadList: false, beforeUpload: (file) => {
                                    handleUpload(file, true);
                                    return false; // Prevent default upload
                                }, disabled: uploading, children: _jsx(Button, { icon: _jsx(StarOutlined, {}), loading: uploading, children: "Add Primary Image" }) })), _jsx(Button, { icon: _jsx(CameraOutlined, {}), onClick: openCameraModal, disabled: uploading, children: "Take Photo" }), faceImages.length > 0 && (_jsx(Tooltip, { title: "Recalculate facial landmarks and embeddings for all images to improve accuracy", children: _jsx(Popconfirm, { title: "Recalculate All Face Images", description: `This will recalculate facial landmarks and embeddings for all ${faceImages.length} images. This may take a while. Continue?`, onConfirm: handleRecalculateAll, okText: "Yes, Recalculate All", cancelText: "Cancel", okButtonProps: { danger: true }, children: _jsxs(Button, { icon: _jsx(ReloadOutlined, {}), loading: recalculatingAll, disabled: uploading || recalculatingId !== null, children: ["Recalculate All (", faceImages.length, ")"] }) }) }))] })] }), uploadProgress && (_jsxs("div", { className: "bg-blue-50 border border-blue-200 rounded-lg p-4", children: [_jsxs("div", { className: "flex items-center justify-between mb-2", children: [_jsxs("span", { className: "text-sm font-medium text-blue-900", children: ["Uploading Images (", uploadProgress.current + 1, " of ", uploadProgress.total, ")"] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsxs("span", { className: "text-xs text-blue-700", children: [Math.round(((uploadProgress.current + 1) / uploadProgress.total) * 100), "%"] }), uploadProgress.canCancel && (_jsx(Button, { size: "small", danger: true, onClick: cancelUpload, className: "text-xs px-2 py-1", children: "Cancel" }))] })] }), _jsx(Progress, { percent: Math.round(((uploadProgress.current + 1) / uploadProgress.total) * 100), status: "active", strokeColor: "#3b82f6", className: "mb-2" }), uploadProgress.currentFileName && (_jsxs("div", { className: "text-xs text-blue-600 truncate", children: ["Processing: ", uploadProgress.currentFileName] }))] })), recalculatingAll && (_jsxs("div", { className: "bg-orange-50 border border-orange-200 rounded-lg p-4", children: [_jsxs("div", { className: "flex items-center justify-between mb-2", children: [_jsx("span", { className: "text-sm font-medium text-orange-900", children: "Recalculating Face Images and Embeddings..." }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Spin, { size: "small" }), _jsxs("span", { className: "text-xs text-orange-700", children: ["Processing ", faceImages.length, " images"] })] })] }), _jsx("div", { className: "text-xs text-orange-600", children: "This process will update facial landmarks and regenerate embeddings for better accuracy. Please wait..." })] })), faceImages.length === 0 ? (_jsx(Alert, { message: "No face images", description: "Upload face images to enable face recognition for this staff member.", type: "info", showIcon: true })) : (_jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", children: faceImages.map((image) => (_jsx(Card, { size: "small", cover: _jsxs("div", { className: "relative", children: [_jsx(Image, { src: getImageUrl(image.image_path), alt: `Face image ${image.image_id.slice(0, 8)}`, className: "object-cover", height: 200, preview: false, onClick: () => handlePreview(image), style: { cursor: 'pointer' }, onLoad: (e) => {
                                    const img = e.currentTarget;
                                    setThumbnailSizes(prev => ({
                                        ...prev,
                                        [image.image_id]: {
                                            width: img.clientWidth,
                                            height: img.clientHeight,
                                            naturalWidth: img.naturalWidth,
                                            naturalHeight: img.naturalHeight,
                                        }
                                    }));
                                } }), image.face_landmarks && thumbnailSizes[image.image_id] && (_jsx(LandmarksOverlay, { landmarks: image.face_landmarks, imageWidth: thumbnailSizes[image.image_id].width, imageHeight: thumbnailSizes[image.image_id].height, naturalWidth: thumbnailSizes[image.image_id].naturalWidth, naturalHeight: thumbnailSizes[image.image_id].naturalHeight, showConnections: false })), image.is_primary && (_jsx(Badge, { count: _jsx(StarFilled, { className: "text-yellow-500" }), className: "absolute top-2 right-2" }))] }), actions: [
                        _jsx(Tooltip, { title: "View Image", children: _jsx(Button, { type: "text", icon: _jsx(EyeOutlined, {}), onClick: () => handlePreview(image) }) }, "view"),
                        _jsx(Tooltip, { title: "Recalculate Landmarks & Embedding", children: _jsx(Button, { type: "text", icon: _jsx(ReloadOutlined, {}), loading: recalculatingId === image.image_id, disabled: recalculatingAll || uploading, onClick: () => handleRecalculate(image.image_id) }) }, "recalc"),
                        _jsx(Popconfirm, { title: "Delete Face Image", description: "Are you sure you want to delete this face image?", onConfirm: () => handleDelete(image.image_id), okText: "Yes", cancelText: "No", children: _jsx(Tooltip, { title: "Delete Image", children: _jsx(Button, { type: "text", danger: true, icon: _jsx(DeleteOutlined, {}) }) }) }, "delete")
                    ], children: _jsxs("div", { className: "space-y-2", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("span", { className: "text-xs text-gray-500 font-mono", children: [image.image_id.slice(0, 8), "..."] }), image.is_primary && (_jsx(Tag, { color: "gold", children: "Primary" }))] }), _jsxs("div", { className: "text-xs text-gray-400", children: ["Uploaded: ", new Date(image.created_at).toLocaleDateString()] }), image.face_landmarks && (_jsxs("div", { className: "text-xs text-green-600", children: ["\u2713 Landmarks detected (", image.face_landmarks.length, " points)"] }))] }) }, image.image_id))) })), _jsxs(Modal, { open: cameraModalVisible, title: "Take Photo", onCancel: closeCameraModal, width: 800, centered: true, footer: [
                    _jsxs(Space, { className: "w-full justify-center", children: [availableCameras.length > 1 && (_jsx(Select, { value: selectedCameraId, onChange: switchCamera, style: { width: 200 }, placeholder: "Select Camera", disabled: capturingPhoto, children: availableCameras.map((camera, index) => (_jsx(Select.Option, { value: camera.deviceId, children: camera.label || `Camera ${index + 1}` }, camera.deviceId))) })), _jsx(Button, { icon: _jsx(SwitcherOutlined, {}), onClick: () => {
                                    const currentIndex = availableCameras.findIndex(cam => cam.deviceId === selectedCameraId);
                                    const nextIndex = (currentIndex + 1) % availableCameras.length;
                                    if (availableCameras[nextIndex]) {
                                        switchCamera(availableCameras[nextIndex].deviceId);
                                    }
                                }, disabled: capturingPhoto || availableCameras.length <= 1, title: "Switch Camera", children: "Switch" }), _jsx(Button, { type: "primary", icon: _jsx(CameraOutlined, {}), onClick: () => capturePhoto(faceImages.length === 0), loading: capturingPhoto, size: "large", children: faceImages.length === 0 ? 'Capture Primary Photo' : 'Capture Photo' }), _jsx(Button, { onClick: closeCameraModal, disabled: capturingPhoto, children: "Cancel" })] }, "camera-controls")
                ], children: [_jsxs("div", { className: "flex flex-col items-center space-y-4", children: [_jsxs("div", { className: "relative bg-black rounded-lg overflow-hidden", style: { width: '640px', height: '480px' }, children: [_jsx("video", { ref: videoRef, autoPlay: true, playsInline: true, muted: true, className: "w-full h-full object-cover", style: { transform: 'scaleX(-1)' } }), !cameraStream && (_jsx("div", { className: "absolute inset-0 flex items-center justify-center bg-gray-800 text-white", children: _jsxs("div", { className: "text-center", children: [_jsx(Spin, { size: "large" }), _jsx("p", { className: "mt-2", children: "Starting camera..." })] }) })), capturingPhoto && (_jsx("div", { className: "absolute inset-0 flex items-center justify-center bg-black bg-opacity-50", children: _jsxs("div", { className: "text-white text-center", children: [_jsx(Spin, { size: "large" }), _jsx("p", { className: "mt-2", children: "Capturing and processing..." })] }) }))] }), _jsxs("div", { className: "text-sm text-gray-600 text-center", children: [_jsx("p", { children: "Position your face in the center of the frame" }), _jsx("p", { children: "Make sure you have good lighting and look directly at the camera" })] })] }), _jsx("canvas", { ref: canvasRef, style: { display: 'none' } })] }), _jsx(Modal, { open: previewVisible, title: previewTitle, footer: null, onCancel: () => setPreviewVisible(false), width: "auto", centered: true, children: _jsxs("div", { className: "relative inline-block", style: { maxWidth: '100%', maxHeight: '70vh' }, children: [_jsx("img", { src: previewImage, alt: "Preview", style: {
                                display: 'block',
                                maxWidth: '100%',
                                maxHeight: '70vh',
                            }, onLoad: (e) => {
                                const img = e.currentTarget;
                                setRenderSize({
                                    width: img.clientWidth,
                                    height: img.clientHeight,
                                    naturalWidth: img.naturalWidth,
                                    naturalHeight: img.naturalHeight,
                                });
                            } }), previewLandmarks && renderSize.width > 0 && renderSize.height > 0 && (_jsx(LandmarksOverlay, { landmarks: previewLandmarks, imageWidth: renderSize.width, imageHeight: renderSize.height, naturalWidth: renderSize.naturalWidth, naturalHeight: renderSize.naturalHeight, showConnections: true }))] }) })] }));
};
