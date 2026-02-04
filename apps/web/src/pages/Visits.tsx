import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Card, 
  Row, 
  Col, 
  Select, 
  DatePicker, 
  Button, 
  Typography, 
  Space, 
  Tag, 
  Avatar,
  Empty,
  Spin,
  Modal,
  Checkbox,
  Popconfirm,
  App
} from 'antd';
import { 
  UserOutlined, 
  CalendarOutlined, 
  ClockCircleOutlined,
  FilterOutlined,
  ReloadOutlined,
  CloseOutlined,
  DeleteOutlined
} from '@ant-design/icons';
import type { RangePickerProps } from 'antd/es/date-picker';

interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}
import type { Visit, Site } from '../types/api';
import { apiClient } from '../services/api';
import { CustomerFaceGallery } from '../components/CustomerFaceGallery';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

// Seed data for visits with image paths
const SEED_VISITS: Partial<Visit>[] = [
  {
    tenant_id: 't-dev',
    visit_id: 'v-001',
    person_id: 101,
    person_type: 'customer',
    site_id: 1,
    camera_id: 1,
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    confidence_score: 0.95,
    image_path: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-002',
    person_id: 102,
    person_type: 'customer',
    site_id: 2,
    camera_id: 2,
    timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    confidence_score: 0.87,
    image_path: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-003',
    person_id: 201,
    person_type: 'staff',
    site_id: 1,
    camera_id: 1,
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    confidence_score: 0.99,
    image_path: 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-004',
    person_id: 103,
    person_type: 'customer',
    site_id: 3,
    camera_id: 3,
    timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    confidence_score: 0.92,
    image_path: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-005',
    person_id: 104,
    person_type: 'customer',
    site_id: 1,
    camera_id: 1,
    timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    confidence_score: 0.88,
    image_path: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-006',
    person_id: 105,
    person_type: 'customer',
    site_id: 2,
    camera_id: 2,
    timestamp: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
    confidence_score: 0.91,
    image_path: 'https://images.unsplash.com/photo-1504593811423-6dd665756598?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-007',
    person_id: 202,
    person_type: 'staff',
    site_id: 3,
    camera_id: 3,
    timestamp: new Date(Date.now() - 1000 * 60 * 240).toISOString(),
    confidence_score: 0.97,
    image_path: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop'
  },
  {
    tenant_id: 't-dev',
    visit_id: 'v-008',
    person_id: 106,
    person_type: 'customer',
    site_id: 1,
    camera_id: 1,
    timestamp: new Date(Date.now() - 1000 * 60 * 300).toISOString(),
    confidence_score: 0.85,
    image_path: 'https://images.unsplash.com/photo-1552058544-f2b08422138a?w=150&h=150&fit=crop'
  }
];

// Seed data for sites
const SEED_SITES: Site[] = [
  { tenant_id: 't-dev', site_id: 1, name: 'Main Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 2, name: 'North Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 3, name: 'South Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 4, name: 'East Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 5, name: 'West Branch', created_at: new Date().toISOString() }
];

export const VisitsPage: React.FC = () => {
  const { message } = App.useApp();
  const [visits, setVisits] = useState<Visit[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([null, null]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [nextCursor, setNextCursor] = useState<string | undefined>();
  const [selectedVisit, setSelectedVisit] = useState<Visit | null>(null);
  const [isModalVisible, setIsModalVisible] = useState<boolean>(false);
  const [reassignOpen, setReassignOpen] = useState<boolean>(false);
  const [reassignTarget, setReassignTarget] = useState<string>('');
  const [reassigning, setReassigning] = useState<boolean>(false);
  const [selectedVisitIds, setSelectedVisitIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number>(-1);
  const [mergeOpen, setMergeOpen] = useState<boolean>(false);
  const [merging, setMerging] = useState<boolean>(false);
  const [primaryVisitId, setPrimaryVisitId] = useState<string | undefined>(undefined);


  // Load initial data from API
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setVisits([]);
    setNextCursor(undefined);
    setHasMore(true);
    
    try {
      // Load sites and initial visits
      const [fetchedSites, visitsResponse] = await Promise.all([
        apiClient.getSites(),
        apiClient.getVisits({
          limit: 50,
          site_id: selectedSites.length > 0 ? selectedSites.join(',') : undefined,
          start_time: dateRange[0] || undefined,
          end_time: dateRange[1] || undefined,
        })
      ]);
      
      setSites(fetchedSites);
      setVisits(visitsResponse.visits);
      setHasMore(visitsResponse.has_more);
      setNextCursor(visitsResponse.next_cursor);
    } catch (error) {
      console.error('Failed to load data:', error);
      
      // Fallback to seed data on error for development
      setSites(SEED_SITES);
      setVisits(SEED_VISITS);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [selectedSites, dateRange]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Load more visits for infinite scroll
  const loadMoreVisits = useCallback(async () => {
    if (!hasMore || loadingMore || !nextCursor) return;
    
    setLoadingMore(true);
    try {
      const response = await apiClient.getVisits({
        limit: 50,
        cursor: nextCursor,
        site_id: selectedSites.length > 0 ? selectedSites.join(',') : undefined,
        start_time: dateRange[0] || undefined,
        end_time: dateRange[1] || undefined,
      });
      
      setVisits(prev => [...prev, ...response.visits]);
      setHasMore(response.has_more);
      setNextCursor(response.next_cursor);
    } catch (error) {
      console.error('Failed to load more visits:', error);
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, loadingMore, nextCursor, selectedSites, dateRange]);

  const handleSiteChange = (value: string[]) => {
    setSelectedSites(value);
  };

  const handleDateChange: RangePickerProps['onChange'] = (dates, dateStrings) => {
    setDateRange([dateStrings[0] || null, dateStrings[1] || null]);
  };

  const handleRefresh = async () => {
    await loadInitialData();
  };

  const handleClearFilters = () => {
    setSelectedSites([]);
    setDateRange([null, null]);
  };

  // Handle scroll for infinite loading
  const handleScroll = useCallback(() => {
    if (loading || loadingMore || !hasMore) return;
    
    const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
    const clientHeight = document.documentElement.clientHeight || window.innerHeight;
    
    // Load more when user scrolls to within 200px of bottom
    if (scrollTop + clientHeight >= scrollHeight - 200) {
      loadMoreVisits();
    }
  }, [loading, loadingMore, hasMore, loadMoreVisits]);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);



  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const visitTime = new Date(timestamp);
    const diffInMinutes = Math.floor((now.getTime() - visitTime.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes} min ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hr ago`;
    return `${Math.floor(diffInMinutes / 1440)} day ago`;
  };

  const getSiteName = (siteId: number) => {
    const site = sites.find(s => s.site_id === siteId);
    return site ? site.name : `Site ${siteId}`;
  };

  const getPersonTypeColor = (personType: string) => {
    return personType === 'staff' ? 'blue' : 'green';
  };

  const handleVisitClick = async (visit: Visit) => {
    setSelectedVisit(visit);
    setIsModalVisible(true);
  };

  const handleCloseModal = () => {
    setIsModalVisible(false);
    setSelectedVisit(null);
  };

  const handleSelectVisit = (visitId: string, checked: boolean, event?: React.MouseEvent) => {
    const visitIndex = visits.findIndex(v => v.visit_id === visitId);
    
    if (event && (event.shiftKey || event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      
      if (event.shiftKey) {
        // Range selection with Shift key
        let startIndex, endIndex;
        
        if (lastSelectedIndex >= 0) {
          // Range from last selected to current
          startIndex = Math.min(lastSelectedIndex, visitIndex);
          endIndex = Math.max(lastSelectedIndex, visitIndex);
        } else {
          // No previous selection, select from beginning to current
          startIndex = 0;
          endIndex = visitIndex;
        }

        
        setSelectedVisitIds(prev => {
          const newSet = new Set(prev);
          for (let i = startIndex; i <= endIndex; i++) {
            if (i < visits.length) {
              newSet.add(visits[i].visit_id);
            }
          }
          return newSet;
        });
        setLastSelectedIndex(visitIndex); // Update to current item
      } else if (event.ctrlKey || event.metaKey) {
        // Multi-selection with Ctrl/Cmd key
        setSelectedVisitIds(prev => {
          const newSet = new Set(prev);
          if (newSet.has(visitId)) {
            newSet.delete(visitId);
          } else {
            newSet.add(visitId);
          }
          return newSet;
        });
        setLastSelectedIndex(visitIndex);
      }
    } else {
      // Regular selection (checkbox or single click)
      setSelectedVisitIds(prev => {
        const newSet = new Set(prev);
        if (checked) {
          newSet.add(visitId);
        } else {
          newSet.delete(visitId);
        }
        return newSet;
      });
      setLastSelectedIndex(visitIndex);
    }
  };

  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked) {
      setSelectedVisitIds(new Set(visits.map(v => v.visit_id)));
      setLastSelectedIndex(visits.length - 1);
    } else {
      setSelectedVisitIds(new Set());
      setLastSelectedIndex(-1);
    }
  }, [visits]);

  const handleCardClick = (visit: Visit, event: React.MouseEvent) => {
    // Don't trigger selection if clicking on checkbox
    if ((event.target as HTMLElement).closest('.visit-checkbox')) {
      return;
    }

    // determine index if needed
    const isCurrentlySelected = selectedVisitIds.has(visit.visit_id);
    const isInSelectionMode = selectedVisitIds.size > 0;
    
    if (event.shiftKey) {
      // Shift+click: Always do range selection
      event.preventDefault();
      handleSelectVisit(visit.visit_id, true, event);
    } else if (event.ctrlKey || event.metaKey) {
      // Ctrl/Cmd+click: Always toggle selection
      event.preventDefault();
      handleSelectVisit(visit.visit_id, !isCurrentlySelected, event);
    } else if (isInSelectionMode) {
      // In selection mode: Regular click toggles selection
      handleSelectVisit(visit.visit_id, !isCurrentlySelected);
    } else {
      // Not in selection mode: Regular click opens modal
      handleVisitClick(visit);
    }
  };

  const handleDeleteSelected = useCallback(async () => {
    if (selectedVisitIds.size === 0) return;

    setIsDeleting(true);
    try {
      const visitIdsArray = Array.from(selectedVisitIds);
      await apiClient.deleteVisits(visitIdsArray);
      
      message.success(`Successfully deleted ${visitIdsArray.length} visit(s)`);
      
      // Clear selections
      setSelectedVisitIds(new Set());
      
      // Refresh the data to recalculate pagination
      await loadInitialData();
      
    } catch (error) {
      console.error('Failed to delete visits:', error);
      message.error('Failed to delete visits. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  }, [selectedVisitIds, loadInitialData, message]);

  const selectedVisits = useMemo(() => {
    const set = selectedVisitIds;
    return visits.filter(v => set.has(v.visit_id));
  }, [selectedVisitIds, visits]);

  const bestPrimaryCandidateId = useMemo(() => {
    if (selectedVisits.length === 0) return undefined;
    const sorted = [...selectedVisits].sort((a, b) => {
      const ah = (a.highest_confidence ?? a.confidence_score) || 0;
      const bh = (b.highest_confidence ?? b.confidence_score) || 0;
      if (bh !== ah) return bh - ah;
      // tie-breaker: earliest first_seen
      return new Date(a.first_seen).getTime() - new Date(b.first_seen).getTime();
    });
    return sorted[0]?.visit_id;
  }, [selectedVisits]);

  const openMergeModal = () => {
    if (selectedVisitIds.size < 2) {
      message.info('Select at least two visits to merge');
      return;
    }
    setPrimaryVisitId(bestPrimaryCandidateId);
    setMergeOpen(true);
  };

  const handleMerge = async () => {
    if (selectedVisitIds.size < 2) return;
    setMerging(true);
    try {
      const ids = Array.from(selectedVisitIds);
      const res = await apiClient.mergeVisits(ids, primaryVisitId);
      message.success(res.message || 'Merged visits');
      setMergeOpen(false);
      setSelectedVisitIds(new Set([res.primary_visit_id]));
      await loadInitialData();
    } catch (e: unknown) {
      const error = e as ApiError;
      message.error(error?.response?.data?.detail || 'Failed to merge visits');
    } finally {
      setMerging(false);
    }
  };

  // Keyboard shortcuts - moved after handleDeleteSelected is defined
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (visits.length === 0) return;
      
      // Ctrl/Cmd + A - Select all
      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault();
        handleSelectAll(true);
      }
      
      // Escape - Clear selection
      if (e.key === 'Escape') {
        setSelectedVisitIds(new Set());
        setLastSelectedIndex(-1);
      }
      
      // Delete key - Delete selected items with confirmation
      if (e.key === 'Delete' && selectedVisitIds.size > 0) {
        e.preventDefault();
        
        Modal.confirm({
          title: `Delete ${selectedVisitIds.size} visit(s)?`,
          content: 'This action cannot be undone.',
          okText: 'Delete',
          cancelText: 'Cancel',
          okButtonProps: { danger: true },
          onOk: handleDeleteSelected,
        });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visits, selectedVisitIds, handleDeleteSelected, handleSelectAll]);

  return (
    <div className="p-6">
      <div className="mb-6">
        <Title level={3}>Visit Gallery</Title>
        <Text type="secondary">Browse and filter customer/staff visits across all sites</Text>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <Space wrap>
            <Space>
              <FilterOutlined />
              <Text strong>Filters:</Text>
            </Space>
            
            <Select
              mode="multiple"
              allowClear
              style={{ minWidth: 200 }}
              placeholder="Select sites"
              value={selectedSites}
              onChange={handleSiteChange}
              options={sites.map(site => ({ label: site.name, value: site.site_id.toString() }))}
            />
            
            <RangePicker
              onChange={handleDateChange}
              placeholder={['Start date', 'End date']}
            />
          </Space>
          
          <Space>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={handleRefresh}
              loading={loading}
            >
              Refresh
            </Button>
            <Button onClick={handleClearFilters}>
              Clear Filters
            </Button>
          </Space>
        </div>
      </Card>

      {/* Stats & Selection Controls */}
      <Card className="mb-6">
        <Row gutter={16} className="mb-4">
          <Col span={6}>
            <Text strong>Loaded Visits: </Text>
            <Text>{visits.length}</Text>
          </Col>
          <Col span={6}>
            <Text strong>Customers: </Text>
            <Text>
              {visits.filter(v => v.person_type === 'customer').length}
            </Text>
          </Col>
          <Col span={6}>
            <Text strong>Staff: </Text>
            <Text>
              {visits.filter(v => v.person_type === 'staff').length}
            </Text>
          </Col>
          <Col span={6}>
            <Text type="secondary" className="text-sm">
              {hasMore ? 'Scroll for more...' : 'All visits loaded'}
            </Text>
          </Col>
        </Row>
        
        {visits.length > 0 && (
          <Row gutter={16} align="middle">
            <Col>
              <Checkbox
                indeterminate={selectedVisitIds.size > 0 && selectedVisitIds.size < visits.length}
                checked={visits.length > 0 && selectedVisitIds.size === visits.length}
                onChange={(e) => handleSelectAll(e.target.checked)}
              >
                Select All ({selectedVisitIds.size} selected)
              </Checkbox>
            </Col>
            <Col>
              {selectedVisitIds.size > 0 && (
                <Popconfirm
                  title={`Delete ${selectedVisitIds.size} visit(s)?`}
                  description="This action cannot be undone."
                  onConfirm={handleDeleteSelected}
                  okText="Delete"
                  cancelText="Cancel"
                  okButtonProps={{ danger: true, loading: isDeleting }}
                >
                  <Button 
                    danger 
                    icon={<DeleteOutlined />}
                    loading={isDeleting}
                    disabled={isDeleting}
                  >
                    Delete Selected ({selectedVisitIds.size})
                  </Button>
                </Popconfirm>
              )}
            </Col>
            <Col>
              <Button 
                type="primary"
                disabled={selectedVisitIds.size < 2}
                onClick={openMergeModal}
              >
                Merge Selected ({selectedVisitIds.size || 0})
              </Button>
            </Col>
          </Row>
        )}
      </Card>

      {/* Visits Gallery */}
      <div>
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <Spin size="large" />
          </div>
        ) : visits.length === 0 ? (
          <Empty 
            description="No visits found" 
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" onClick={handleClearFilters}>
              Clear Filters
            </Button>
          </Empty>
        ) : (
          <>
            <Row gutter={[16, 16]}>
              {visits.map(visit => (
              <Col xs={24} sm={12} md={8} lg={6} key={visit.visit_id}>
                <Card 
                  size="small" 
                  hoverable
                  className={`h-full flex flex-col shadow-sm hover:shadow-md transition-shadow relative ${
                    selectedVisitIds.size > 0 ? 'cursor-crosshair' : 'cursor-pointer'
                  } ${
                    selectedVisitIds.has(visit.visit_id) 
                      ? 'ring-2 ring-blue-500 bg-blue-50' 
                      : ''
                  }`}
                  onClick={(e) => handleCardClick(visit, e)}
                >
                  {/* Selection Checkbox */}
                  <div 
                    className="visit-checkbox absolute top-2 right-2 z-10"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={selectedVisitIds.has(visit.visit_id)}
                      onChange={(e) => handleSelectVisit(visit.visit_id, e.target.checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between mb-2 pr-8">
                    <Tag color={getPersonTypeColor(visit.person_type)}>
                      {visit.person_type.charAt(0).toUpperCase() + visit.person_type.slice(1)}
                    </Tag>
                    <Text type="secondary" className="text-xs">
                      {formatTimeAgo(visit.timestamp)}
                    </Text>
                  </div>
                  
                  <div className="flex flex-col items-center mb-3">
                    {visit.image_path ? (
                      <img 
                        src={visit.image_path} 
                        alt="Captured face" 
                        className="w-20 h-20 rounded-full object-cover border-2 border-gray-200 mb-2 cursor-pointer"
                        onError={(e) => {
                          // Fallback to avatar if image fails to load
                          const target = e.target as HTMLImageElement;
                          target.onerror = null;
                          target.style.display = 'none';
                          target.nextElementSibling?.removeAttribute('style');
                        }}
                      />
                    ) : null}
                    <Avatar 
                      size={64} 
                      icon={<UserOutlined />} 
                      className="mb-2"
                      style={visit.image_path ? { display: 'none' } : {}}
                    />
                    <div className="text-center">
                      <Text strong>
                        {visit.person_type === 'staff' ? 'Staff' : 'Customer'} #{visit.person_id}
                      </Text>
                    </div>
                  </div>
                  
                  <div className="mt-auto">
                    <div className="flex items-center mb-1">
                      <CalendarOutlined className="mr-2 text-gray-500" />
                      <Text type="secondary" className="text-xs">
                        {new Date(visit.timestamp).toLocaleDateString()}
                      </Text>
                    </div>
                    
                    <div className="flex items-center mb-1">
                      <ClockCircleOutlined className="mr-2 text-gray-500" />
                      <Text type="secondary" className="text-xs">
                        {new Date(visit.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </Text>
                    </div>
                    
                    <div className="flex items-center mb-1">
                      <Text type="secondary" className="text-xs truncate">
                        {getSiteName(visit.site_id)}
                      </Text>
                    </div>
                    
                    <div className="mt-1">
                      <Text type="secondary" className="text-xs">
                        Confidence: {(visit.confidence_score * 100).toFixed(1)}%
                      </Text>
                    </div>
                    
                    {visit.detection_count > 1 && (
                      <div className="mt-1">
                        <Text type="secondary" className="text-xs">
                          {visit.detection_count} detections
                        </Text>
                      </div>
                    )}
                    
                    {visit.visit_duration_seconds && visit.visit_duration_seconds > 0 && (
                      <div className="mt-1">
                        <Text type="secondary" className="text-xs">
                          Duration: {Math.floor(visit.visit_duration_seconds / 60)}m {visit.visit_duration_seconds % 60}s
                        </Text>
                      </div>
                    )}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
          
          {/* Loading more indicator */}
          {loadingMore && (
            <div className="flex justify-center items-center mt-8">
              <Spin size="large" />
              <Text className="ml-3">Loading more visits...</Text>
            </div>
          )}
          
          {/* Load more button as fallback */}
          {hasMore && !loadingMore && (
            <div className="flex justify-center mt-8">
              <Button 
                type="default" 
                size="large"
                onClick={loadMoreVisits}
                icon={<ReloadOutlined />}
              >
                Load More Visits
              </Button>
            </div>
          )}
          </>
        )}
      </div>

      {/* Visit Details Modal */}
      <Modal
        open={isModalVisible}
        onCancel={handleCloseModal}
        footer={null}
        width={selectedVisit?.person_type === 'customer' ? 600 : 400}
        closeIcon={<CloseOutlined />}
        centered
      >
        {selectedVisit && (
          <div className="flex flex-col items-center">
            <div className="mb-4">
              {selectedVisit.image_path ? (
                <img 
                  src={selectedVisit.image_path} 
                  alt="Captured face" 
                  className="w-32 h-32 rounded-full object-cover border-2 border-gray-200"
                />
              ) : (
                <Avatar 
                  size={128} 
                  icon={<UserOutlined />} 
                />
              )}
            </div>
            
            <div className="w-full">
              <div className="flex justify-between items-center mb-2">
                <Tag color={getPersonTypeColor(selectedVisit.person_type)}>
                  {selectedVisit.person_type.charAt(0).toUpperCase() + selectedVisit.person_type.slice(1)}
                </Tag>
                <Text type="secondary">
                  {formatTimeAgo(selectedVisit.timestamp)}
                </Text>
              </div>
              
              <div className="mb-3 text-center">
                <Text strong className="text-lg">
                  {selectedVisit.person_type === 'staff' ? 'Staff' : 'Customer'} #{selectedVisit.person_id}
                </Text>
                <br />
                <Text type="secondary">
                  Visit ID: {selectedVisit.visit_id}
                </Text>
              </div>
              
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="flex items-center mb-2">
                  <CalendarOutlined className="mr-2 text-gray-500" />
                  <Text>
                    <strong>Date:</strong> {new Date(selectedVisit.timestamp).toLocaleDateString()}
                  </Text>
                </div>
                
                <div className="flex items-center mb-2">
                  <ClockCircleOutlined className="mr-2 text-gray-500" />
                  <Text>
                    <strong>Time:</strong> {new Date(selectedVisit.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </Text>
                </div>
                
                <div className="flex items-center mb-2">
                  <Text>
                    <strong>Site:</strong> {getSiteName(selectedVisit.site_id)}
                  </Text>
                </div>
                
                <div className="flex items-center mb-2">
                  <Text>
                    <strong>Confidence:</strong> {(selectedVisit.confidence_score * 100).toFixed(1)}%
                  </Text>
                </div>
                
                {selectedVisit.detection_count > 1 && (
                  <div className="flex items-center mb-2">
                    <Text>
                      <strong>Detections:</strong> {selectedVisit.detection_count}
                    </Text>
                  </div>
                )}
                
                {selectedVisit.visit_duration_seconds && selectedVisit.visit_duration_seconds > 0 && (
                  <div className="flex items-center mb-2">
                    <Text>
                      <strong>Duration:</strong> {Math.floor(selectedVisit.visit_duration_seconds / 60)}m {selectedVisit.visit_duration_seconds % 60}s
                    </Text>
                  </div>
                )}
                
                {selectedVisit.highest_confidence && selectedVisit.highest_confidence !== selectedVisit.confidence_score && (
                  <div className="flex items-center">
                    <Text>
                      <strong>Peak Confidence:</strong> {(selectedVisit.highest_confidence * 100).toFixed(1)}%
                    </Text>
                  </div>
                )}
              </div>
            </div>            {/* Customer Face Gallery */}
            {selectedVisit.person_type === 'customer' && selectedVisit.person_id && (
              <div className="w-full mt-6">
                <div className="flex items-center justify-between mb-3">
                  <Space>
                    <Button size="small" onClick={() => setReassignOpen(true)}>Reassign Visit…</Button>
                    <Popconfirm
                      title="Remove this visit?"
                      description="Deletes the visit and associated images."
                      okText="Remove"
                      okButtonProps={{ danger: true }}
                      onConfirm={async () => {
                        try {
                          await apiClient.removeVisitFaceDetection(selectedVisit.visit_id);
                          message.success('Visit removed');
                          setIsModalVisible(false);
                          await loadInitialData();
                        } catch (e: unknown) {
                          const error = e as ApiError;
                          message.error(error.response?.data?.detail || 'Failed to remove');
                        }
                      }}
                    >
                      <Button size="small" danger>Remove Visit</Button>
                    </Popconfirm>
                  </Space>
                </div>
                <CustomerFaceGallery
                  customerId={selectedVisit.person_id}
                  customerName={`Customer #${selectedVisit.person_id}`}
                />
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={reassignOpen}
        onCancel={() => setReassignOpen(false)}
        title="Reassign Visit"
        okText={reassigning ? 'Reassigning…' : 'Reassign'}
        onOk={async () => {
          const cid = parseInt(reassignTarget, 10);
          if (!selectedVisit || !cid) return;
          try {
            setReassigning(true);
            await apiClient.reassignVisit(selectedVisit.visit_id, cid, true);
            message.success('Visit reassigned');
            setReassignOpen(false);
            setIsModalVisible(false);
            setReassignTarget('');
            await loadInitialData();
          } catch (e: unknown) {
            const error = e as ApiError;
            message.error(error.response?.data?.detail || 'Failed to reassign visit');
          } finally {
            setReassigning(false);
          }
        }}
      >
        <div className="space-y-2">
          <div>New customer ID</div>
          <input
            value={reassignTarget}
            onChange={(e) => setReassignTarget(e.target.value)}
            className="w-full border rounded px-2 py-1"
            placeholder="Enter customer id"
          />
        </div>
      </Modal>

      {/* Merge Visits Modal */}
      <Modal
        open={mergeOpen}
        onCancel={() => setMergeOpen(false)}
        title={`Merge ${selectedVisitIds.size} visits`}
        okText={merging ? 'Merging…' : 'Merge'}
        onOk={handleMerge}
        confirmLoading={merging}
      >
        <div className="space-y-3">
          <div>
            Choose primary visit (keeps best image/fields):
          </div>
          <Select
            className="w-full"
            value={primaryVisitId}
            onChange={(v) => setPrimaryVisitId(v)}
          >
            {selectedVisits.map(v => (
              <Select.Option key={v.visit_id} value={v.visit_id}>
                {v.visit_id} • {new Date(v.first_seen).toLocaleString()} • conf {(100 * (v.highest_confidence ?? v.confidence_score)).toFixed(1)}%
              </Select.Option>
            ))}
          </Select>
          <div className="text-xs text-gray-500">
            All visits must belong to the same person and site. The primary visit will absorb the others.
          </div>
        </div>
      </Modal>
    </div>
  );
};
