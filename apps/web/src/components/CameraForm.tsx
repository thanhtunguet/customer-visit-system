import React, { useState } from 'react';
import { Form, Input, Radio } from 'antd';
import { CameraType, WebcamInfo } from '../types/api';
import { WebcamDeviceSelector } from './WebcamDeviceSelector';
import { apiClient } from '../services/api';

interface CameraFormProps {
  form: any;
  selectedSite: number | null;
}

export const CameraForm: React.FC<CameraFormProps> = ({ form: _form, selectedSite }) => {
  const [webcams, setWebcams] = useState<WebcamInfo[]>([]);
  const [webcamsLoading, setWebcamsLoading] = useState(false);
  const [webcamSource, setWebcamSource] = useState<'workers' | 'none'>('none');
  const [manualInputMode, setManualInputMode] = useState(false);

  const loadWebcams = async () => {
    if (!selectedSite) return;
    
    try {
      setWebcamsLoading(true);
      const response = await apiClient.getWebcams(selectedSite);
      setWebcams(response.devices);
      setWebcamSource(response.source);
      setManualInputMode(response.manual_input_required);
    } finally {
      setWebcamsLoading(false);
    }
  };

  return (
    <>
      <Form.Item
        name="name"
        label="Camera Name"
        rules={[{ required: true, message: 'Please input camera name!' }]}
      >
        <Input placeholder="e.g. Entrance Camera" />
      </Form.Item>

      <Form.Item
        name="camera_type"
        label="Camera Type"
        rules={[{ required: true, message: 'Please select camera type!' }]}
      >
        <Radio.Group onChange={async (e) => {
          if (e.target.value === CameraType.WEBCAM) {
            await loadWebcams();
          }
        }}>
          <Radio value={CameraType.RTSP}>RTSP Camera</Radio>
          <Radio value={CameraType.WEBCAM}>Webcam</Radio>
        </Radio.Group>
      </Form.Item>

      <Form.Item
        noStyle
        shouldUpdate={true}
      >
        {({ getFieldValue }) => {
          const cameraType = getFieldValue('camera_type');
          
          if (cameraType === CameraType.RTSP) {
            return (
              <Form.Item
                name="rtsp_url"
                label="RTSP URL"
                rules={[{ required: true, message: 'Please input RTSP URL!' }]}
              >
                <Input placeholder="e.g. rtsp://192.168.1.100:554/stream" />
              </Form.Item>
            );
          }
          
          if (cameraType === CameraType.WEBCAM) {
            return (
              <Form.Item
                name="device_index"
                label="Webcam Device"
                tooltip="Select the physical webcam device. Device index matches system enumeration."
                rules={[{ required: true, message: 'Please select or enter a webcam device index!' }]}
              >
                <WebcamDeviceSelector
                  webcams={webcams}
                  webcamsLoading={webcamsLoading}
                  webcamSource={webcamSource}
                  manualInputMode={manualInputMode}
                  onManualInputModeChange={setManualInputMode}
                  onDropdownVisibleChange={async (open) => {
                    if (open && webcams.length === 0) {
                      await loadWebcams();
                    }
                  }}
                />
              </Form.Item>
            );
          }
          
          return null;
        }}
      </Form.Item>
    </>
  );
};
