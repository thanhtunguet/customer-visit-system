import React from 'react';
import { Avatar, Spin } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import { useAuthenticatedAvatar } from '../hooks/useAuthenticatedAvatar';

interface AuthenticatedAvatarProps {
  src?: string;
  size?: number;
  className?: string;
  alt?: string;
  icon?: React.ReactNode;
}

export const AuthenticatedAvatar: React.FC<AuthenticatedAvatarProps> = ({
  src,
  size = 40,
  className,
  alt,
  icon = <UserOutlined />,
}) => {
  const { blobUrl, loading } = useAuthenticatedAvatar(src);

  if (loading) {
    return (
      <div 
        className={`flex items-center justify-center ${className}`}
        style={{ width: size, height: size }}
      >
        <Spin size="small" />
      </div>
    );
  }

  return (
    <Avatar
      size={size}
      src={blobUrl || undefined}
      icon={!blobUrl ? icon : undefined}
      className={className}
      alt={alt}
    />
  );
};
