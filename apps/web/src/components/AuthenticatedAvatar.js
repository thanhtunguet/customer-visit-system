import { jsx as _jsx } from 'react/jsx-runtime';
import { Avatar, Spin } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import { useAuthenticatedAvatar } from '../hooks/useAuthenticatedAvatar';
export const AuthenticatedAvatar = ({
  src,
  size = 40,
  className,
  alt,
  icon = _jsx(UserOutlined, {}),
}) => {
  const { blobUrl, loading } = useAuthenticatedAvatar(src);
  if (loading) {
    return _jsx('div', {
      className: `flex items-center justify-center ${className}`,
      style: { width: size, height: size },
      children: _jsx(Spin, { size: 'small' }),
    });
  }
  return _jsx(Avatar, {
    size: size,
    src: blobUrl || undefined,
    icon: !blobUrl ? icon : undefined,
    className: className,
    alt: alt,
  });
};
