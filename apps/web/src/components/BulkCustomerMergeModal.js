import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import { useState, useEffect } from 'react';
import { Modal, Button, Tag, Alert, Select, message } from 'antd';
import { TeamOutlined, UserOutlined, SwapOutlined } from '@ant-design/icons';
import { AuthenticatedAvatar } from './AuthenticatedAvatar';
import dayjs from 'dayjs';
export const BulkCustomerMergeModal = ({
  visible,
  selectedCustomers,
  onClose,
  onMerge,
}) => {
  const [mergeGroups, setMergeGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (visible && selectedCustomers.length >= 2) {
      // Auto-suggest merge groups based on similarity or user selection
      // For now, create a single group with the first customer as primary
      const primary = selectedCustomers[0];
      const secondaries = selectedCustomers.slice(1);
      setMergeGroups([
        {
          primary,
          secondaries,
        },
      ]);
    }
  }, [visible, selectedCustomers]);
  const handleChangePrimary = (groupIndex, newPrimaryId) => {
    setMergeGroups((groups) => {
      const newGroups = [...groups];
      const group = newGroups[groupIndex];
      // Find the new primary customer
      const allCustomers = [group.primary, ...group.secondaries];
      const newPrimary = allCustomers.find(
        (c) => c.customer_id === newPrimaryId
      );
      if (newPrimary) {
        // Create new secondaries list excluding the new primary
        const newSecondaries = allCustomers.filter(
          (c) => c.customer_id !== newPrimaryId
        );
        newGroups[groupIndex] = {
          primary: newPrimary,
          secondaries: newSecondaries,
        };
      }
      return newGroups;
    });
  };
  const handleRemoveFromGroup = (groupIndex, customerId) => {
    setMergeGroups((groups) => {
      const newGroups = [...groups];
      const group = newGroups[groupIndex];
      if (group.primary.customer_id === customerId) {
        // If removing primary and there are secondaries, promote one to primary
        if (group.secondaries.length > 0) {
          newGroups[groupIndex] = {
            primary: group.secondaries[0],
            secondaries: group.secondaries.slice(1),
          };
        } else {
          // Remove the group entirely if it becomes empty
          newGroups.splice(groupIndex, 1);
        }
      } else {
        // Remove from secondaries
        newGroups[groupIndex] = {
          ...group,
          secondaries: group.secondaries.filter(
            (c) => c.customer_id !== customerId
          ),
        };
      }
      return newGroups;
    });
  };
  const handleCreateNewGroup = () => {
    // Get customers not in any group
    const usedCustomerIds = new Set(
      mergeGroups.flatMap((g) => [
        g.primary.customer_id,
        ...g.secondaries.map((s) => s.customer_id),
      ])
    );
    const availableCustomers = selectedCustomers.filter(
      (c) => !usedCustomerIds.has(c.customer_id)
    );
    if (availableCustomers.length >= 2) {
      const newGroup = {
        primary: availableCustomers[0],
        secondaries: availableCustomers.slice(1),
      };
      setMergeGroups((groups) => [...groups, newGroup]);
    }
  };
  const handleMerge = async () => {
    if (mergeGroups.length === 0) {
      message.warning('No merge groups configured');
      return;
    }
    // Validate groups
    const invalidGroups = mergeGroups.filter((g) => g.secondaries.length === 0);
    if (invalidGroups.length > 0) {
      message.warning(
        'All merge groups must have at least one secondary customer'
      );
      return;
    }
    setLoading(true);
    try {
      const mergeOperations = mergeGroups.map((group) => ({
        primary_customer_id: group.primary.customer_id,
        secondary_customer_ids: group.secondaries.map((s) => s.customer_id),
      }));
      await onMerge(mergeOperations);
      onClose();
    } catch (error) {
      console.error('Bulk merge failed:', error);
    } finally {
      setLoading(false);
    }
  };
  const getTotalCustomers = () => selectedCustomers.length;
  const getTotalMergeTargets = () =>
    mergeGroups.reduce((sum, g) => sum + g.secondaries.length, 0);
  const getRemainingCustomers = () =>
    getTotalCustomers() - getTotalMergeTargets();
  const renderCustomerItem = (customer, isPrimary = false) =>
    _jsxs('div', {
      className: 'flex items-center space-x-3 p-2 bg-gray-50 rounded border',
      children: [
        _jsx(AuthenticatedAvatar, {
          src: customer.avatar_url,
          size: 32,
          icon: _jsx(UserOutlined, {}),
          alt: customer.name || `Customer ${customer.customer_id}`,
        }),
        _jsxs('div', {
          className: 'flex-1',
          children: [
            _jsxs('div', {
              className: 'font-medium',
              children: [
                '#',
                customer.customer_id,
                customer.name &&
                  _jsx('span', {
                    className: 'ml-2 text-gray-600',
                    children: customer.name,
                  }),
                isPrimary &&
                  _jsx(Tag, {
                    color: 'blue',
                    className: 'ml-2',
                    children: 'PRIMARY',
                  }),
              ],
            }),
            _jsxs('div', {
              className: 'text-sm text-gray-500',
              children: [
                customer.visit_count,
                ' visits \u2022 Last seen: ',
                dayjs(customer.last_seen).format('MMM D, YYYY'),
              ],
            }),
          ],
        }),
      ],
    });
  return _jsx(Modal, {
    title: _jsxs('div', {
      className: 'flex items-center space-x-2',
      children: [
        _jsx(TeamOutlined, {}),
        _jsx('span', { children: 'Bulk Customer Merge' }),
      ],
    }),
    open: visible,
    onCancel: onClose,
    width: 800,
    footer: [
      _jsx(Button, { onClick: onClose, children: 'Cancel' }, 'cancel'),
      _jsxs(
        Button,
        {
          type: 'primary',
          icon: _jsx(SwapOutlined, {}),
          loading: loading,
          onClick: handleMerge,
          disabled: mergeGroups.length === 0,
          className: 'bg-blue-600',
          children: [
            'Start Bulk Merge (',
            getTotalMergeTargets(),
            ' customers)',
          ],
        },
        'merge'
      ),
    ],
    children: _jsxs('div', {
      className: 'space-y-4',
      children: [
        _jsx(Alert, {
          message: 'Bulk Customer Merge',
          description: _jsxs('div', {
            children: [
              _jsxs('p', {
                children: [
                  'You have selected ',
                  _jsx('strong', { children: getTotalCustomers() }),
                  ' customers for bulk merging.',
                ],
              }),
              _jsx('p', {
                children:
                  'Configure merge groups below. Each group will merge secondary customers into a primary customer.',
              }),
              _jsx('p', {
                className: 'text-orange-600 font-medium',
                children:
                  '\u26A0\uFE0F This operation cannot be undone. All visits, face images, and data from secondary customers will be moved to the primary customer.',
              }),
            ],
          }),
          type: 'warning',
          showIcon: true,
          className: 'mb-4',
        }),
        _jsxs('div', {
          className: 'bg-blue-50 p-3 rounded border',
          children: [
            _jsx('div', {
              className: 'text-sm font-medium text-blue-800 mb-1',
              children: 'Merge Summary',
            }),
            _jsxs('div', {
              className: 'text-sm text-blue-700',
              children: [
                _jsxs('span', {
                  className: 'mr-4',
                  children: ['Total Customers: ', getTotalCustomers()],
                }),
                _jsxs('span', {
                  className: 'mr-4',
                  children: ['Will be merged: ', getTotalMergeTargets()],
                }),
                _jsxs('span', {
                  children: [
                    'Remaining after merge: ',
                    getRemainingCustomers(),
                  ],
                }),
              ],
            }),
          ],
        }),
        _jsx('div', {
          className: 'space-y-4 max-h-96 overflow-y-auto',
          children: mergeGroups.map((group, groupIndex) =>
            _jsxs(
              'div',
              {
                className: 'border rounded p-4 bg-white',
                children: [
                  _jsxs('div', {
                    className: 'flex items-center justify-between mb-3',
                    children: [
                      _jsxs('h4', {
                        className: 'font-medium text-gray-800',
                        children: ['Merge Group ', groupIndex + 1],
                      }),
                      _jsx(Button, {
                        size: 'small',
                        danger: true,
                        onClick: () =>
                          setMergeGroups((groups) =>
                            groups.filter((_, i) => i !== groupIndex)
                          ),
                        children: 'Remove Group',
                      }),
                    ],
                  }),
                  _jsxs('div', {
                    className: 'space-y-3',
                    children: [
                      _jsxs('div', {
                        children: [
                          _jsxs('div', {
                            className:
                              'text-sm font-medium text-gray-700 mb-2 flex items-center justify-between',
                            children: [
                              'Primary Customer (will keep all data)',
                              _jsx(Select, {
                                value: group.primary.customer_id,
                                onChange: (value) =>
                                  handleChangePrimary(groupIndex, value),
                                style: { width: 200 },
                                size: 'small',
                                children: [
                                  group.primary,
                                  ...group.secondaries,
                                ].map((customer) =>
                                  _jsxs(
                                    Select.Option,
                                    {
                                      value: customer.customer_id,
                                      children: [
                                        '#',
                                        customer.customer_id,
                                        ' ',
                                        customer.name
                                          ? `- ${customer.name}`
                                          : '',
                                      ],
                                    },
                                    customer.customer_id
                                  )
                                ),
                              }),
                            ],
                          }),
                          renderCustomerItem(group.primary, true),
                        ],
                      }),
                      _jsxs('div', {
                        children: [
                          _jsxs('div', {
                            className: 'text-sm font-medium text-gray-700 mb-2',
                            children: [
                              'Secondary Customers (',
                              group.secondaries.length,
                              ') - will be merged into primary',
                            ],
                          }),
                          _jsx('div', {
                            className: 'space-y-2',
                            children: group.secondaries.map((customer) =>
                              _jsxs(
                                'div',
                                {
                                  className: 'flex items-center space-x-2',
                                  children: [
                                    _jsx('div', {
                                      className: 'flex-1',
                                      children: renderCustomerItem(customer),
                                    }),
                                    _jsx(Button, {
                                      size: 'small',
                                      danger: true,
                                      onClick: () =>
                                        handleRemoveFromGroup(
                                          groupIndex,
                                          customer.customer_id
                                        ),
                                      children: 'Remove',
                                    }),
                                  ],
                                },
                                customer.customer_id
                              )
                            ),
                          }),
                        ],
                      }),
                    ],
                  }),
                ],
              },
              groupIndex
            )
          ),
        }),
        mergeGroups.length === 0 &&
          _jsx('div', {
            className: 'text-center py-8 text-gray-500',
            children:
              'No merge groups configured. Click "Create New Group" to start.',
          }),
        _jsx('div', {
          className: 'flex justify-center',
          children: _jsx(Button, {
            onClick: handleCreateNewGroup,
            disabled:
              mergeGroups.reduce(
                (used, g) => used + 1 + g.secondaries.length,
                0
              ) >= selectedCustomers.length,
            children: 'Create New Group',
          }),
        }),
      ],
    }),
  });
};
