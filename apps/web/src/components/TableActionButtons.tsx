import { DeleteOutlined, EditOutlined, EyeOutlined } from '@ant-design/icons';
import { Button, Popconfirm, PopconfirmProps, Tooltip } from 'antd';
import React from 'react';

interface ActionButtonProps {
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
}

interface ViewActionProps extends ActionButtonProps {
  tooltip?: string;
}

interface EditActionProps extends ActionButtonProps {
  tooltip?: string;
}

interface DeleteActionProps extends Omit<PopconfirmProps, 'children'> {
  onConfirm: () => void;
  disabled?: boolean;
  loading?: boolean;
  tooltip?: string;
}

export const ViewAction: React.FC<ViewActionProps> = ({
  onClick,
  disabled = false,
  loading = false,
  tooltip = 'View details',
}) => (
  <Tooltip title={tooltip}>
    <Button
      type="text"
      icon={<EyeOutlined />}
      onClick={onClick}
      disabled={disabled}
      loading={loading}
      size="small"
    />
  </Tooltip>
);

export const EditAction: React.FC<EditActionProps> = ({
  onClick,
  disabled = false,
  loading = false,
  tooltip = 'Edit',
}) => (
  <Tooltip title={tooltip}>
    <Button
      type="text"
      icon={<EditOutlined />}
      onClick={onClick}
      disabled={disabled}
      loading={loading}
      size="small"
    />
  </Tooltip>
);

export const DeleteAction: React.FC<DeleteActionProps> = ({
  onConfirm,
  disabled = false,
  loading = false,
  tooltip = 'Delete',
  title = 'Are you sure?',
  description,
  okText = 'Yes',
  cancelText = 'No',
  ...popconfirmProps
}) => (
  <Tooltip title={tooltip}>
    <Popconfirm
      title={title}
      description={description}
      onConfirm={onConfirm}
      okText={okText}
      cancelText={cancelText}
      {...popconfirmProps}
    >
      <Button
        type="text"
        icon={<DeleteOutlined />}
        disabled={disabled}
        loading={loading}
        size="small"
        danger
      />
    </Popconfirm>
  </Tooltip>
);
