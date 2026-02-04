import React, { useState, useEffect } from 'react';
import { Modal, Button, Tag, Alert, Select, message } from 'antd';
import { TeamOutlined, UserOutlined, SwapOutlined } from '@ant-design/icons';
import { Customer } from '../types/api';
import { AuthenticatedAvatar } from './AuthenticatedAvatar';
import dayjs from 'dayjs';

interface BulkCustomerMergeModalProps {
  visible: boolean;
  selectedCustomers: Customer[];
  onClose: () => void;
  onMerge: (mergeOperations: MergeOperation[]) => Promise<void>;
}

interface MergeOperation {
  primary_customer_id: number;
  secondary_customer_ids: number[];
}

interface CustomerGroup {
  primary: Customer;
  secondaries: Customer[];
}

export const BulkCustomerMergeModal: React.FC<BulkCustomerMergeModalProps> = ({
  visible,
  selectedCustomers,
  onClose,
  onMerge,
}) => {
  const [mergeGroups, setMergeGroups] = useState<CustomerGroup[]>([]);
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

  const handleChangePrimary = (groupIndex: number, newPrimaryId: number) => {
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

  const handleRemoveFromGroup = (groupIndex: number, customerId: number) => {
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
      const newGroup: CustomerGroup = {
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
      const mergeOperations: MergeOperation[] = mergeGroups.map((group) => ({
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

  const renderCustomerItem = (
    customer: Customer,
    isPrimary: boolean = false
  ) => (
    <div className="flex items-center space-x-3 p-2 bg-gray-50 rounded border">
      <AuthenticatedAvatar
        src={customer.avatar_url}
        size={32}
        icon={<UserOutlined />}
        alt={customer.name || `Customer ${customer.customer_id}`}
      />
      <div className="flex-1">
        <div className="font-medium">
          #{customer.customer_id}
          {customer.name && (
            <span className="ml-2 text-gray-600">{customer.name}</span>
          )}
          {isPrimary && (
            <Tag color="blue" className="ml-2">
              PRIMARY
            </Tag>
          )}
        </div>
        <div className="text-sm text-gray-500">
          {customer.visit_count} visits • Last seen:{' '}
          {dayjs(customer.last_seen).format('MMM D, YYYY')}
        </div>
      </div>
    </div>
  );

  return (
    <Modal
      title={
        <div className="flex items-center space-x-2">
          <TeamOutlined />
          <span>Bulk Customer Merge</span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="merge"
          type="primary"
          icon={<SwapOutlined />}
          loading={loading}
          onClick={handleMerge}
          disabled={mergeGroups.length === 0}
          className="bg-blue-600"
        >
          Start Bulk Merge ({getTotalMergeTargets()} customers)
        </Button>,
      ]}
    >
      <div className="space-y-4">
        <Alert
          message="Bulk Customer Merge"
          description={
            <div>
              <p>
                You have selected <strong>{getTotalCustomers()}</strong>{' '}
                customers for bulk merging.
              </p>
              <p>
                Configure merge groups below. Each group will merge secondary
                customers into a primary customer.
              </p>
              <p className="text-orange-600 font-medium">
                ⚠️ This operation cannot be undone. All visits, face images, and
                data from secondary customers will be moved to the primary
                customer.
              </p>
            </div>
          }
          type="warning"
          showIcon
          className="mb-4"
        />

        <div className="bg-blue-50 p-3 rounded border">
          <div className="text-sm font-medium text-blue-800 mb-1">
            Merge Summary
          </div>
          <div className="text-sm text-blue-700">
            <span className="mr-4">Total Customers: {getTotalCustomers()}</span>
            <span className="mr-4">
              Will be merged: {getTotalMergeTargets()}
            </span>
            <span>Remaining after merge: {getRemainingCustomers()}</span>
          </div>
        </div>

        <div className="space-y-4 max-h-96 overflow-y-auto">
          {mergeGroups.map((group, groupIndex) => (
            <div key={groupIndex} className="border rounded p-4 bg-white">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-gray-800">
                  Merge Group {groupIndex + 1}
                </h4>
                <Button
                  size="small"
                  danger
                  onClick={() =>
                    setMergeGroups((groups) =>
                      groups.filter((_, i) => i !== groupIndex)
                    )
                  }
                >
                  Remove Group
                </Button>
              </div>

              <div className="space-y-3">
                {/* Primary Customer */}
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-2 flex items-center justify-between">
                    Primary Customer (will keep all data)
                    <Select
                      value={group.primary.customer_id}
                      onChange={(value) =>
                        handleChangePrimary(groupIndex, value)
                      }
                      style={{ width: 200 }}
                      size="small"
                    >
                      {[group.primary, ...group.secondaries].map((customer) => (
                        <Select.Option
                          key={customer.customer_id}
                          value={customer.customer_id}
                        >
                          #{customer.customer_id}{' '}
                          {customer.name ? `- ${customer.name}` : ''}
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                  {renderCustomerItem(group.primary, true)}
                </div>

                {/* Secondary Customers */}
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-2">
                    Secondary Customers ({group.secondaries.length}) - will be
                    merged into primary
                  </div>
                  <div className="space-y-2">
                    {group.secondaries.map((customer) => (
                      <div
                        key={customer.customer_id}
                        className="flex items-center space-x-2"
                      >
                        <div className="flex-1">
                          {renderCustomerItem(customer)}
                        </div>
                        <Button
                          size="small"
                          danger
                          onClick={() =>
                            handleRemoveFromGroup(
                              groupIndex,
                              customer.customer_id
                            )
                          }
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {mergeGroups.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No merge groups configured. Click "Create New Group" to start.
          </div>
        )}

        <div className="flex justify-center">
          <Button
            onClick={handleCreateNewGroup}
            disabled={
              mergeGroups.reduce(
                (used, g) => used + 1 + g.secondaries.length,
                0
              ) >= selectedCustomers.length
            }
          >
            Create New Group
          </Button>
        </div>
      </div>
    </Modal>
  );
};
