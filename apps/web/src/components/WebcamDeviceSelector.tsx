import React from 'react';
import { Select, Input, Alert, Button } from 'antd';
import { WebcamInfo } from '../types/api';

interface WebcamDeviceSelectorProps {
  webcams: WebcamInfo[];
  webcamsLoading: boolean;
  webcamSource: 'workers' | 'none';
  manualInputMode: boolean;
  onManualInputModeChange: (manual: boolean) => void;
  onDropdownVisibleChange: (open: boolean) => void;
  value?: number;
  onChange?: (value: number) => void;
}

export const WebcamDeviceSelector: React.FC<WebcamDeviceSelectorProps> = ({
  webcams,
  webcamsLoading,
  webcamSource,
  manualInputMode,
  onManualInputModeChange,
  onDropdownVisibleChange,
  value,
  onChange,
}) => {
  if (manualInputMode || webcamSource === 'none') {
    return (
      <div className="space-y-3">
        <Alert
          message="Manual Input Required"
          description="No workers are currently available to enumerate webcam devices. Please enter the device index manually (usually 0, 1, 2, etc.)."
          type="warning"
          showIcon
          style={{ marginBottom: 8 }}
        />
        <Input
          type="number"
          min={0}
          max={10}
          placeholder="Enter device index (e.g. 0, 1, 2)"
          addonBefore="Device Index"
          value={value}
          onChange={(e) => onChange?.(parseInt(e.target.value))}
        />
        <div className="text-sm text-gray-600">
          <strong>Common device indices:</strong>
          <ul className="mt-1 ml-4 list-disc">
            <li>
              <code>0</code> - First webcam (built-in camera)
            </li>
            <li>
              <code>1</code> - Second webcam (external USB camera)
            </li>
            <li>
              <code>2</code> - Third webcam
            </li>
          </ul>
        </div>
        {webcamSource === 'workers' && (
          <div className="text-right">
            <Button
              type="link"
              size="small"
              onClick={() => onManualInputModeChange(false)}
            >
              ← Back to device selection
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <Select
        loading={webcamsLoading}
        placeholder={
          webcamsLoading
            ? 'Loading webcams from workers...'
            : 'Select a webcam device'
        }
        showSearch
        value={value}
        onChange={onChange}
        filterOption={(input, option) =>
          option?.label
            ?.toString()
            .toLowerCase()
            .indexOf(input.toLowerCase()) >= 0
        }
        onDropdownVisibleChange={onDropdownVisibleChange}
        dropdownRender={(menu) => (
          <div>
            {menu}
            <div style={{ padding: 8, borderTop: '1px solid #f0f0f0' }}>
              <Button
                type="link"
                size="small"
                onClick={() => onManualInputModeChange(true)}
                style={{ padding: 0 }}
              >
                Can't find your device? Enter manually
              </Button>
            </div>
          </div>
        )}
        options={webcams.map((w) => ({
          value: w.device_index,
          disabled: !w.is_working || w.in_use,
          label:
            `${w.in_use ? '🔒 ' : ''}Device ${w.device_index}${w.width && w.height ? ` (${w.width}x${w.height})` : ''}${w.fps ? ` ${Math.round(w.fps)}fps` : ''}${!w.is_working ? ' [Not Working]' : ''}`.trim(),
        }))}
      />
      {webcamSource === 'workers' && (
        <div className="text-xs text-green-600 mt-2">
          ✓ Device list loaded from workers. Workers are available for camera
          streaming.
        </div>
      )}
    </div>
  );
};
