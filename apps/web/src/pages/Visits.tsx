import React, { useState, useEffect } from 'react';
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
  Modal
} from 'antd';
import { 
  UserOutlined, 
  CalendarOutlined, 
  ClockCircleOutlined,
  FilterOutlined,
  ReloadOutlined,
  CloseOutlined
} from '@ant-design/icons';
import type { RangePickerProps } from 'antd/es/date-picker';
import type { Visit, Site } from '../types/api';
import { apiClient } from '../services/api';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const { Option } = Select;

// Seed data for visits with image paths
const SEED_VISITS: Visit[] = [
  {
    tenant_id: 't-dev',
    visit_id: 'v-001',
    person_id: 101,
    person_type: 'customer',
    site_id: 's-main',
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
    site_id: 's-north',
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
    site_id: 's-main',
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
    site_id: 's-south',
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
    site_id: 's-main',
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
    site_id: 's-north',
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
    site_id: 's-south',
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
    site_id: 's-main',
    camera_id: 1,
    timestamp: new Date(Date.now() - 1000 * 60 * 300).toISOString(),
    confidence_score: 0.85,
    image_path: 'https://images.unsplash.com/photo-1552058544-f2b08422138a?w=150&h=150&fit=crop'
  }
];

// Seed data for sites
const SEED_SITES: Site[] = [
  { tenant_id: 't-dev', site_id: 's-main', name: 'Main Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 's-north', name: 'North Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 's-south', name: 'South Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 's-east', name: 'East Branch', created_at: new Date().toISOString() },
  { tenant_id: 't-dev', site_id: 's-west', name: 'West Branch', created_at: new Date().toISOString() }
];

export const VisitsPage: React.FC = () => {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [filteredVisits, setFilteredVisits] = useState<Visit[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([null, null]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedVisit, setSelectedVisit] = useState<Visit | null>(null);
  const [isModalVisible, setIsModalVisible] = useState<boolean>(false);

  // Initialize with seed data
  useEffect(() => {
    const initializeData = async () => {
      setLoading(true);
      try {
        // In a real implementation, we would fetch from the API:
        // const fetchedSites = await apiClient.getSites();
        // const fetchedVisits = await apiClient.getVisits();
        
        // For demo purposes, use seed data
        setSites(SEED_SITES);
        setVisits(SEED_VISITS);
        setFilteredVisits(SEED_VISITS);
      } catch (error) {
        console.error('Failed to load data:', error);
        // Fallback to seed data on error
        setSites(SEED_SITES);
        setVisits(SEED_VISITS);
        setFilteredVisits(SEED_VISITS);
      } finally {
        setLoading(false);
      }
    };

    initializeData();
  }, []);

  // Apply filters
  useEffect(() => {
    let result = [...visits];
    
    // Apply site filter
    if (selectedSites.length > 0) {
      result = result.filter(visit => selectedSites.includes(visit.site_id));
    }
    
    // Apply date filter
    if (dateRange[0] && dateRange[1]) {
      const startDate = new Date(dateRange[0]);
      const endDate = new Date(dateRange[1]);
      endDate.setHours(23, 59, 59, 999); // End of day
      
      result = result.filter(visit => {
        const visitDate = new Date(visit.timestamp);
        return visitDate >= startDate && visitDate <= endDate;
      });
    }
    
    setFilteredVisits(result);
  }, [selectedSites, dateRange, visits]);

  const handleSiteChange = (value: string[]) => {
    setSelectedSites(value);
  };

  const handleDateChange: RangePickerProps['onChange'] = (dates, dateStrings) => {
    setDateRange([dateStrings[0] || null, dateStrings[1] || null]);
  };

  const handleRefresh = () => {
    // In a real implementation, this would fetch fresh data
    // For demo, we'll just reset to seed data
    setVisits(SEED_VISITS);
    setFilteredVisits(SEED_VISITS);
  };

  const handleClearFilters = () => {
    setSelectedSites([]);
    setDateRange([null, null]);
  };

  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const visitTime = new Date(timestamp);
    const diffInMinutes = Math.floor((now.getTime() - visitTime.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes} min ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hr ago`;
    return `${Math.floor(diffInMinutes / 1440)} day ago`;
  };

  const getSiteName = (siteId: string) => {
    const site = sites.find(s => s.site_id === siteId);
    return site ? site.name : siteId;
  };

  const getPersonTypeColor = (personType: string) => {
    return personType === 'staff' ? 'blue' : 'green';
  };

  const handleVisitClick = (visit: Visit) => {
    setSelectedVisit(visit);
    setIsModalVisible(true);
  };

  const handleCloseModal = () => {
    setIsModalVisible(false);
    setSelectedVisit(null);
  };

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
              options={sites.map(site => ({ label: site.name, value: site.site_id }))}
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
            >
              Refresh
            </Button>
            <Button onClick={handleClearFilters}>
              Clear Filters
            </Button>
          </Space>
        </div>
      </Card>

      {/* Stats */}
      <Card className="mb-6">
        <Row gutter={16}>
          <Col span={8}>
            <Text strong>Total Visits: </Text>
            <Text>{filteredVisits.length}</Text>
          </Col>
          <Col span={8}>
            <Text strong>Customers: </Text>
            <Text>
              {filteredVisits.filter(v => v.person_type === 'customer').length}
            </Text>
          </Col>
          <Col span={8}>
            <Text strong>Staff: </Text>
            <Text>
              {filteredVisits.filter(v => v.person_type === 'staff').length}
            </Text>
          </Col>
        </Row>
      </Card>

      {/* Visits Gallery */}
      <div>
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <Spin size="large" />
          </div>
        ) : filteredVisits.length === 0 ? (
          <Empty 
            description="No visits found" 
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" onClick={handleClearFilters}>
              Clear Filters
            </Button>
          </Empty>
        ) : (
          <Row gutter={[16, 16]}>
            {filteredVisits.map(visit => (
              <Col xs={24} sm={12} md={8} lg={6} key={visit.visit_id}>
                <Card 
                  size="small" 
                  hoverable
                  className="h-full flex flex-col shadow-sm hover:shadow-md transition-shadow"
                  onClick={() => handleVisitClick(visit)}
                >
                  <div className="flex items-center justify-between mb-2">
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
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </div>

      {/* Image Preview Modal */}
      <Modal
        open={isModalVisible}
        onCancel={handleCloseModal}
        footer={null}
        width={400}
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
                  className="w-64 h-64 rounded-full object-cover border-2 border-gray-200"
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
                
                <div className="flex items-center">
                  <Text>
                    <strong>Confidence:</strong> {(selectedVisit.confidence_score * 100).toFixed(1)}%
                  </Text>
                </div>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};