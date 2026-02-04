import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { Form, Input, Radio } from 'antd';
import { CameraType } from '../types/api';
import { WebcamDeviceSelector } from './WebcamDeviceSelector';
import { apiClient } from '../services/api';
export const CameraForm = ({ form: _form, selectedSite }) => {
    const [webcams, setWebcams] = useState([]);
    const [webcamsLoading, setWebcamsLoading] = useState(false);
    const [webcamSource, setWebcamSource] = useState('none');
    const [manualInputMode, setManualInputMode] = useState(false);
    const loadWebcams = async () => {
        if (!selectedSite)
            return;
        try {
            setWebcamsLoading(true);
            const response = await apiClient.getWebcams(selectedSite);
            setWebcams(response.devices);
            setWebcamSource(response.source);
            setManualInputMode(response.manual_input_required);
        }
        finally {
            setWebcamsLoading(false);
        }
    };
    return (_jsxs(_Fragment, { children: [_jsx(Form.Item, { name: "name", label: "Camera Name", rules: [{ required: true, message: 'Please input camera name!' }], children: _jsx(Input, { placeholder: "e.g. Entrance Camera" }) }), _jsx(Form.Item, { name: "camera_type", label: "Camera Type", rules: [{ required: true, message: 'Please select camera type!' }], children: _jsxs(Radio.Group, { onChange: async (e) => {
                        if (e.target.value === CameraType.WEBCAM) {
                            await loadWebcams();
                        }
                    }, children: [_jsx(Radio, { value: CameraType.RTSP, children: "RTSP Camera" }), _jsx(Radio, { value: CameraType.WEBCAM, children: "Webcam" })] }) }), _jsx(Form.Item, { noStyle: true, shouldUpdate: true, children: ({ getFieldValue }) => {
                    const cameraType = getFieldValue('camera_type');
                    if (cameraType === CameraType.RTSP) {
                        return (_jsx(Form.Item, { name: "rtsp_url", label: "RTSP URL", rules: [{ required: true, message: 'Please input RTSP URL!' }], children: _jsx(Input, { placeholder: "e.g. rtsp://192.168.1.100:554/stream" }) }));
                    }
                    if (cameraType === CameraType.WEBCAM) {
                        return (_jsx(Form.Item, { name: "device_index", label: "Webcam Device", tooltip: "Select the physical webcam device. Device index matches system enumeration.", rules: [{ required: true, message: 'Please select or enter a webcam device index!' }], children: _jsx(WebcamDeviceSelector, { webcams: webcams, webcamsLoading: webcamsLoading, webcamSource: webcamSource, manualInputMode: manualInputMode, onManualInputModeChange: setManualInputMode, onDropdownVisibleChange: async (open) => {
                                    if (open && webcams.length === 0) {
                                        await loadWebcams();
                                    }
                                } }) }));
                    }
                    return null;
                } })] }));
};
