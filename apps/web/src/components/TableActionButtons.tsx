import React from 'react';
import { Button, Space, Tooltip, Popconfirm, PopconfirmProps } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';

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
  tooltip = "View details"
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
  tooltip = "Edit"
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
  tooltip = "Delete",
  title = "Are you sure?",
  description,
  okText = "Yes",
  cancelText = "No",
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

interface TableActionsProps {
  children: React.ReactNode;
  fixed?: boolean;
  width?: number;
}

interface ColumnConfig {
  title: string;
  key: string;
  width: number;
  fixed?: 'right' | 'left';
  render: () => React.ReactNode;
}

export const TableActions = ({ 
  children, 
  fixed = true,
  width = 120
}: TableActionsProps): ColumnConfig => {
  return {
    title: 'Actions',
    key: 'actions',
    width,
    ...(fixed && { fixed: 'right' as const }),
    render: () => (
      <Space size="small">
        {children}
      </Space>
    ),
  };
};

// Higher-order component for creating action columns
export const createActionColumn = (actions: React.ReactNode, options?: { width?: number; fixed?: boolean }) => ({
  title: 'Actions',
  key: 'actions',
  width: options?.width || 120,
  ...(options?.fixed !== false && { fixed: 'right' as const }),
  render: () => (
    <Space size="small">
      {actions}
    </Space>
  ),
});