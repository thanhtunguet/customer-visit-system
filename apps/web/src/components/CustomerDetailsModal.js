import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Tabs,
  Descriptions,
  Tag,
  Spin,
  Alert,
  Button,
  Space,
  Typography,
} from 'antd';
import {
  UserOutlined,
  PictureOutlined,
  EditOutlined,
  PhoneOutlined,
  MailOutlined,
} from '@ant-design/icons';
import { apiClient } from '../services/api';
import { CustomerFaceGallery } from './CustomerFaceGallery';
import dayjs from 'dayjs';
const { Title, Text } = Typography;
export const CustomerDetailsModal = ({
  visible,
  customerId,
  onClose,
  onEdit,
}) => {
  const [loading, setLoading] = useState(false);
  const [customerData, setCustomerData] = useState(null);
  const [galleryStats, setGalleryStats] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('details');
  const loadCustomerData = useCallback(async () => {
    if (!customerId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getCustomer(customerId);
      setCustomerData(data);
    } catch (err) {
      setError(
        err?.response?.data?.detail || 'Failed to load customer details'
      );
      setCustomerData(null);
    } finally {
      setLoading(false);
    }
  }, [customerId]);
  const loadGalleryStats = useCallback(async () => {
    if (!customerId) return;
    try {
      const stats = await apiClient.get(
        `/customers/${customerId}/face-gallery-stats`
      );
      setGalleryStats(stats);
    } catch (err) {
      console.warn('Failed to load gallery stats:', err);
      // Don't show error for stats, it's optional
    }
  }, [customerId]);
  useEffect(() => {
    if (visible && customerId) {
      loadCustomerData();
      loadGalleryStats();
    }
  }, [visible, customerId, loadCustomerData, loadGalleryStats]);
  const handleClose = () => {
    setCustomerData(null);
    setGalleryStats(null);
    setError(null);
    setActiveTab('details');
    onClose();
  };
  const handleEdit = () => {
    if (customerData && onEdit) {
      onEdit(customerData.customer_id);
    }
  };
  const handleGalleryChange = () => {
    // Reload gallery stats when images change
    loadGalleryStats();
  };
  const renderGenderTag = (gender) => {
    if (!gender || gender === 'unknown') {
      return _jsx(Tag, { children: 'Unknown' });
    }
    const color =
      gender === 'male' ? 'blue' : gender === 'female' ? 'pink' : 'gray';
    return _jsx(Tag, {
      color: color,
      children: gender.charAt(0).toUpperCase() + gender.slice(1),
    });
  };
  const tabItems = [
    {
      key: 'details',
      label: _jsxs(Space, {
        children: [_jsx(UserOutlined, {}), 'Customer Details'],
      }),
      children:
        customerData &&
        _jsxs('div', {
          className: 'space-y-4',
          children: [
            _jsxs('div', {
              className: 'flex items-center justify-between',
              children: [
                _jsx(Title, {
                  level: 4,
                  className: 'mb-0',
                  children:
                    customerData.name ||
                    `Customer #${customerData.customer_id}`,
                }),
                onEdit &&
                  _jsx(Button, {
                    icon: _jsx(EditOutlined, {}),
                    onClick: handleEdit,
                    children: 'Edit Customer',
                  }),
              ],
            }),
            _jsxs(Descriptions, {
              column: 1,
              bordered: true,
              size: 'small',
              children: [
                _jsx(Descriptions.Item, {
                  label: 'Customer ID',
                  children: _jsxs('span', {
                    className: 'font-mono',
                    children: ['#', customerData.customer_id],
                  }),
                }),
                _jsx(Descriptions.Item, {
                  label: 'Name',
                  children: customerData.name
                    ? _jsx('span', {
                        className: 'font-medium',
                        children: customerData.name,
                      })
                    : _jsx('span', {
                        className: 'text-gray-400 italic',
                        children: 'No name provided',
                      }),
                }),
                _jsx(Descriptions.Item, {
                  label: 'Gender',
                  children: renderGenderTag(customerData.gender),
                }),
                _jsx(Descriptions.Item, {
                  label: 'Age Range',
                  children:
                    customerData.estimated_age_range ||
                    _jsx('span', {
                      className: 'text-gray-400',
                      children: 'Unknown',
                    }),
                }),
                _jsx(Descriptions.Item, {
                  label: 'Contact',
                  children: _jsxs(Space, {
                    direction: 'vertical',
                    size: 'small',
                    children: [
                      customerData.phone &&
                        _jsxs(Space, {
                          children: [
                            _jsx(PhoneOutlined, {}),
                            _jsx(Text, {
                              copyable: { text: customerData.phone },
                              children: customerData.phone,
                            }),
                          ],
                        }),
                      customerData.email &&
                        _jsxs(Space, {
                          children: [
                            _jsx(MailOutlined, {}),
                            _jsx(Text, {
                              copyable: { text: customerData.email },
                              children: customerData.email,
                            }),
                          ],
                        }),
                      !customerData.phone &&
                        !customerData.email &&
                        _jsx('span', {
                          className: 'text-gray-400',
                          children: 'No contact information',
                        }),
                    ],
                  }),
                }),
                _jsx(Descriptions.Item, {
                  label: 'Visit Statistics',
                  children: _jsxs(Space, {
                    direction: 'vertical',
                    size: 'small',
                    children: [
                      _jsxs('div', {
                        children: [
                          _jsx(Text, {
                            strong: true,
                            children: 'Total Visits:',
                          }),
                          ' ',
                          customerData.visit_count,
                        ],
                      }),
                      _jsxs('div', {
                        children: [
                          _jsx(Text, { strong: true, children: 'First Seen:' }),
                          ' ',
                          ' ',
                          dayjs(customerData.first_seen).format(
                            'MMMM D, YYYY [at] h:mm A'
                          ),
                        ],
                      }),
                      customerData.last_seen &&
                        _jsxs('div', {
                          children: [
                            _jsx(Text, {
                              strong: true,
                              children: 'Last Seen:',
                            }),
                            ' ',
                            ' ',
                            dayjs(customerData.last_seen).format(
                              'MMMM D, YYYY [at] h:mm A'
                            ),
                          ],
                        }),
                    ],
                  }),
                }),
                _jsx(Descriptions.Item, {
                  label: 'Recognition Status',
                  children:
                    galleryStats && galleryStats.total_images > 0
                      ? _jsxs(Tag, {
                          color: 'green',
                          children: [
                            'Enrolled (',
                            galleryStats.total_images,
                            ' faces)',
                          ],
                        })
                      : _jsx(Tag, {
                          color: 'orange',
                          children: 'Limited Recognition Data',
                        }),
                }),
                galleryStats &&
                  galleryStats.total_images > 0 &&
                  _jsx(Descriptions.Item, {
                    label: 'Face Gallery Stats',
                    children: _jsxs(Space, {
                      direction: 'vertical',
                      size: 'small',
                      children: [
                        _jsxs('div', {
                          children: [
                            _jsx(Text, { strong: true, children: 'Images:' }),
                            ' ',
                            galleryStats.total_images,
                            ' / ',
                            galleryStats.gallery_limit,
                          ],
                        }),
                        _jsxs('div', {
                          children: [
                            _jsx(Text, {
                              strong: true,
                              children: 'Avg Confidence:',
                            }),
                            ' ',
                            (galleryStats.avg_confidence * 100).toFixed(1),
                            '%',
                          ],
                        }),
                        _jsxs('div', {
                          children: [
                            _jsx(Text, {
                              strong: true,
                              children: 'Best Match:',
                            }),
                            ' ',
                            (galleryStats.max_confidence * 100).toFixed(1),
                            '%',
                          ],
                        }),
                        galleryStats.first_image_date &&
                          _jsxs('div', {
                            children: [
                              _jsx(Text, {
                                strong: true,
                                children: 'First Image:',
                              }),
                              ' ',
                              ' ',
                              dayjs(galleryStats.first_image_date).format(
                                'MMM D, YYYY'
                              ),
                            ],
                          }),
                      ],
                    }),
                  }),
              ],
            }),
            (!galleryStats || galleryStats.total_images === 0) &&
              _jsx(Alert, {
                message: 'Limited Face Recognition Data',
                description:
                  'This customer has few or no face images saved. Face images are automatically captured during visits to improve recognition accuracy.',
                type: 'info',
                showIcon: true,
              }),
          ],
        }),
    },
    {
      key: 'faces',
      label: _jsxs(Space, {
        children: [
          _jsx(PictureOutlined, {}),
          'Face Gallery (',
          galleryStats?.total_images || 0,
          ')',
        ],
      }),
      children:
        customerData &&
        _jsx(CustomerFaceGallery, {
          customerId: customerData.customer_id,
          customerName: customerData.name,
          onImagesChange: handleGalleryChange,
        }),
    },
  ];
  return _jsxs(Modal, {
    title: customerData
      ? `Customer Details - ${customerData.name || `#${customerData.customer_id}`}`
      : 'Customer Details',
    open: visible,
    onCancel: handleClose,
    width: 900,
    footer: null,
    destroyOnHidden: true,
    centered: true,
    children: [
      loading &&
        _jsx('div', {
          className: 'flex justify-center items-center py-12',
          children: _jsx(Spin, { size: 'large' }),
        }),
      error &&
        _jsx(Alert, {
          message: 'Error Loading Customer Details',
          description: error,
          type: 'error',
          showIcon: true,
          action: _jsx(Button, {
            size: 'small',
            onClick: loadCustomerData,
            children: 'Retry',
          }),
        }),
      customerData &&
        !loading &&
        _jsx(Tabs, {
          activeKey: activeTab,
          onChange: setActiveTab,
          items: tabItems,
          size: 'small',
        }),
      !customerData &&
        !loading &&
        !error &&
        _jsx('div', {
          className: 'text-center py-12 text-gray-400',
          children: 'No customer selected',
        }),
    ],
  });
};
