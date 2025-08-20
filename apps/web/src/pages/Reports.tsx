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
  Statistic,
  Divider,
  Spin,
  Table,
  Tag,
  Tooltip,
  Progress
} from 'antd';
import {
  CalendarOutlined,
  DownloadOutlined,
  FilterOutlined,
  ReloadOutlined,
  UserOutlined,
  TeamOutlined,
  ClockCircleOutlined,
  RiseOutlined,
  FallOutlined
} from '@ant-design/icons';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  Heatmap
} from 'recharts';
import type { RangePickerProps } from 'antd/es/date-picker';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const { Option } = Select;

// Color palette for charts
const COLORS = {
  primary: '#2563eb',
  secondary: '#059669',
  accent: '#dc2626',
  warning: '#d97706',
  info: '#7c3aed',
  success: '#16a34a'
};

const PIE_COLORS = ['#2563eb', '#059669', '#dc2626', '#d97706', '#7c3aed', '#16a34a'];

// Generate seed data for the last 30 days
const generateVisitorTrendsData = () => {
  const data = [];
  for (let i = 29; i >= 0; i--) {
    const date = dayjs().subtract(i, 'days');
    const baseVisits = Math.floor(Math.random() * 50) + 30;
    const uniqueVisitors = Math.floor(baseVisits * (0.6 + Math.random() * 0.3));
    const staffVisits = Math.floor(Math.random() * 15) + 5;
    
    data.push({
      date: date.format('MM/DD'),
      fullDate: date.format('YYYY-MM-DD'),
      totalVisits: baseVisits + staffVisits,
      customerVisits: baseVisits,
      staffVisits: staffVisits,
      uniqueVisitors: uniqueVisitors,
      repeatVisitors: baseVisits - uniqueVisitors
    });
  }
  return data;
};

// Generate hourly heatmap data
const generateHourlyData = () => {
  const hours = [];
  for (let h = 0; h < 24; h++) {
    const baseActivity = h >= 8 && h <= 18 ? Math.random() * 80 + 20 : Math.random() * 30;
    hours.push({
      hour: h,
      label: `${h.toString().padStart(2, '0')}:00`,
      visits: Math.floor(baseActivity),
      density: baseActivity
    });
  }
  return hours;
};

// Generate day of week data
const generateDayOfWeekData = () => {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  return days.map((day, index) => {
    const isWeekend = index >= 5;
    const baseVisits = isWeekend ? Math.random() * 30 + 10 : Math.random() * 60 + 40;
    return {
      day: day.slice(0, 3),
      fullDay: day,
      visits: Math.floor(baseVisits),
      customers: Math.floor(baseVisits * 0.8),
      staff: Math.floor(baseVisits * 0.2)
    };
  });
};

// Generate demographics data
const generateDemographicsData = () => ({
  visitorType: [
    { name: 'New Customers', value: 156, color: COLORS.primary },
    { name: 'Returning Customers', value: 324, color: COLORS.secondary },
    { name: 'Staff', value: 89, color: COLORS.warning }
  ],
  gender: [
    { name: 'Male', value: 298, color: COLORS.primary },
    { name: 'Female', value: 271, color: COLORS.secondary }
  ],
  ageGroups: [
    { group: '18-25', count: 89, percentage: 15.6 },
    { group: '26-35', count: 167, percentage: 29.3 },
    { group: '36-45', count: 145, percentage: 25.5 },
    { group: '46-55', count: 98, percentage: 17.2 },
    { group: '55+', count: 70, percentage: 12.3 }
  ]
});

// Generate site comparison data
const generateSiteData = () => [
  { site: 'Main Branch', visits: 1240, customers: 892, staff: 348, growth: 12.5 },
  { site: 'North Branch', visits: 986, customers: 723, staff: 263, growth: -3.2 },
  { site: 'South Branch', visits: 847, customers: 634, staff: 213, growth: 8.7 },
  { site: 'East Branch', visits: 712, customers: 521, staff: 191, growth: 15.3 },
  { site: 'West Branch', visits: 623, customers: 445, staff: 178, growth: -1.8 }
];

// Generate peak hours data
const generatePeakHoursData = () => [
  { timeRange: '09:00-10:00', visits: 45, percentage: 8.2 },
  { timeRange: '12:00-13:00', visits: 78, percentage: 14.1 },
  { timeRange: '15:00-16:00', visits: 62, percentage: 11.2 },
  { timeRange: '17:00-18:00', visits: 89, percentage: 16.1 },
  { timeRange: '19:00-20:00', visits: 56, percentage: 10.1 }
];

export const Reports: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([
    dayjs().subtract(30, 'days').format('YYYY-MM-DD'),
    dayjs().format('YYYY-MM-DD')
  ]);
  const [granularity, setGranularity] = useState<'hour' | 'day' | 'week' | 'month'>('day');
  
  // Seed data
  const [visitorTrends] = useState(generateVisitorTrendsData());
  const [hourlyData] = useState(generateHourlyData());
  const [dayOfWeekData] = useState(generateDayOfWeekData());
  const [demographics] = useState(generateDemographicsData());
  const [siteData] = useState(generateSiteData());
  const [peakHours] = useState(generatePeakHoursData());

  // Summary statistics
  const totalVisits = visitorTrends.reduce((sum, day) => sum + day.totalVisits, 0);
  const totalCustomers = visitorTrends.reduce((sum, day) => sum + day.customerVisits, 0);
  const totalStaff = visitorTrends.reduce((sum, day) => sum + day.staffVisits, 0);
  const avgDailyVisits = Math.round(totalVisits / visitorTrends.length);

  const handleExport = (type: 'visitor-trends' | 'demographics' | 'site-comparison') => {
    // Mock CSV export - in real implementation, this would call API
    const timestamp = dayjs().format('YYYY-MM-DD_HH-mm-ss');
    console.log(`Exporting ${type} report as CSV...`, { timestamp, dateRange, selectedSites });
    
    // Simulate download
    const link = document.createElement('a');
    link.download = `${type}-report-${timestamp}.csv`;
    link.click();
  };

  const handleRefresh = () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      setLoading(false);
    }, 1000);
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <Title level={3}>Analytics & Reports</Title>
        <Text type="secondary">Comprehensive visitor analytics and site performance metrics</Text>
      </div>

      {/* Filters & Controls */}
      <Card className="mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <Space wrap size="middle">
            <Space>
              <FilterOutlined />
              <Text strong>Filters:</Text>
            </Space>
            
            <Select
              mode="multiple"
              allowClear
              style={{ minWidth: 200 }}
              placeholder="All sites"
              value={selectedSites}
              onChange={setSelectedSites}
            >
              <Option value="main">Main Branch</Option>
              <Option value="north">North Branch</Option>
              <Option value="south">South Branch</Option>
              <Option value="east">East Branch</Option>
              <Option value="west">West Branch</Option>
            </Select>
            
            <RangePicker
              value={[
                dateRange[0] ? dayjs(dateRange[0]) : null,
                dateRange[1] ? dayjs(dateRange[1]) : null
              ]}
              onChange={(dates, dateStrings) => setDateRange(dateStrings as [string, string])}
            />
            
            <Select value={granularity} onChange={setGranularity} style={{ width: 120 }}>
              <Option value="hour">Hourly</Option>
              <Option value="day">Daily</Option>
              <Option value="week">Weekly</Option>
              <Option value="month">Monthly</Option>
            </Select>
          </Space>
          
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
              Refresh
            </Button>
            <Button 
              type="primary" 
              icon={<DownloadOutlined />}
              onClick={() => handleExport('visitor-trends')}
            >
              Export CSV
            </Button>
          </Space>
        </div>
      </Card>

      {/* Summary Statistics */}
      <Row gutter={16} className="mb-6">
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Visits"
              value={totalVisits}
              prefix={<UserOutlined className="text-blue-600" />}
              suffix={
                <Tooltip title="12.5% increase from last period">
                  <RiseOutlined className="text-green-500 ml-2" />
                </Tooltip>
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Customer Visits"
              value={totalCustomers}
              prefix={<UserOutlined className="text-green-600" />}
              suffix={
                <Text type="secondary" className="text-sm">
                  ({Math.round((totalCustomers / totalVisits) * 100)}%)
                </Text>
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Staff Visits"
              value={totalStaff}
              prefix={<TeamOutlined className="text-orange-600" />}
              suffix={
                <Text type="secondary" className="text-sm">
                  ({Math.round((totalStaff / totalVisits) * 100)}%)
                </Text>
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Daily Average"
              value={avgDailyVisits}
              prefix={<ClockCircleOutlined className="text-purple-600" />}
              suffix={
                <Tooltip title="Based on selected date range">
                  <Text type="secondary" className="text-sm">visits/day</Text>
                </Tooltip>
              }
            />
          </Card>
        </Col>
      </Row>

      {/* Visitor Trends Chart */}
      <Card title="Visitor Trends" className="mb-6" loading={loading}>
        <ResponsiveContainer width="100%" height={400}>
          <AreaChart data={visitorTrends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <RechartsTooltip 
              labelFormatter={(label) => `Date: ${label}`}
              formatter={(value, name) => [value, name.replace(/([A-Z])/g, ' $1').trim()]}
            />
            <Area
              type="monotone"
              dataKey="staffVisits"
              stackId="1"
              stroke={COLORS.warning}
              fill={COLORS.warning}
              fillOpacity={0.6}
              name="Staff Visits"
            />
            <Area
              type="monotone"
              dataKey="customerVisits"
              stackId="1"
              stroke={COLORS.primary}
              fill={COLORS.primary}
              fillOpacity={0.6}
              name="Customer Visits"
            />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <Row gutter={16} className="mb-6">
        {/* Demographics Analysis */}
        <Col xs={24} lg={12}>
          <Card title="Visitor Demographics" className="h-full">
            <Row gutter={16}>
              <Col span={12}>
                <div className="mb-4">
                  <Text strong>Visitor Type</Text>
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={demographics.visitorType}
                        cx="50%"
                        cy="50%"
                        outerRadius={60}
                        dataKey="value"
                      >
                        {demographics.visitorType.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </Col>
              <Col span={12}>
                <div className="mb-4">
                  <Text strong>Gender Distribution</Text>
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={demographics.gender}
                        cx="50%"
                        cy="50%"
                        outerRadius={60}
                        dataKey="value"
                      >
                        {demographics.gender.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </Col>
            </Row>
            
            <Divider />
            
            <div>
              <Text strong>Age Groups</Text>
              <div className="mt-3 space-y-3">
                {demographics.ageGroups.map((group) => (
                  <div key={group.group} className="flex items-center justify-between">
                    <div className="flex items-center space-x-3 flex-1">
                      <Text className="w-12">{group.group}</Text>
                      <Progress 
                        percent={group.percentage} 
                        size="small" 
                        className="flex-1"
                        showInfo={false}
                      />
                    </div>
                    <Text type="secondary" className="w-20 text-right">
                      {group.count} ({group.percentage}%)
                    </Text>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        {/* Day of Week Analysis */}
        <Col xs={24} lg={12}>
          <Card title="Day of Week Analysis" className="h-full">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={dayOfWeekData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis />
                <RechartsTooltip />
                <Bar dataKey="staff" stackId="a" fill={COLORS.warning} name="Staff" />
                <Bar dataKey="customers" stackId="a" fill={COLORS.primary} name="Customers" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} className="mb-6">
        {/* Hourly Activity Heatmap */}
        <Col xs={24} lg={16}>
          <Card title="Hourly Activity Pattern">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <RechartsTooltip 
                  labelFormatter={(label) => `Time: ${label}`}
                  formatter={(value) => [value, 'Visits']}
                />
                <Bar 
                  dataKey="visits" 
                  fill={COLORS.primary}
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* Peak Hours */}
        <Col xs={24} lg={8}>
          <Card title="Peak Hours" className="h-full">
            <div className="space-y-4">
              {peakHours.map((hour, index) => (
                <div key={hour.timeRange} className="flex items-center justify-between">
                  <div>
                    <Text strong>{hour.timeRange}</Text>
                    <br />
                    <Text type="secondary" className="text-sm">
                      {hour.percentage}% of daily traffic
                    </Text>
                  </div>
                  <div className="text-right">
                    <Text className="text-lg font-semibold">{hour.visits}</Text>
                    <br />
                    <Text type="secondary" className="text-sm">visits</Text>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Site Comparison */}
      <Card title="Site Performance Comparison" className="mb-6">
        <Table
          dataSource={siteData}
          pagination={false}
          size="middle"
          columns={[
            {
              title: 'Site',
              dataIndex: 'site',
              key: 'site',
              render: (text) => <Text strong>{text}</Text>
            },
            {
              title: 'Total Visits',
              dataIndex: 'visits',
              key: 'visits',
              sorter: (a, b) => a.visits - b.visits,
              render: (value) => value.toLocaleString()
            },
            {
              title: 'Customer Visits',
              dataIndex: 'customers',
              key: 'customers',
              sorter: (a, b) => a.customers - b.customers,
              render: (value) => value.toLocaleString()
            },
            {
              title: 'Staff Visits',
              dataIndex: 'staff',
              key: 'staff',
              sorter: (a, b) => a.staff - b.staff,
              render: (value) => value.toLocaleString()
            },
            {
              title: 'Growth Rate',
              dataIndex: 'growth',
              key: 'growth',
              sorter: (a, b) => a.growth - b.growth,
              render: (value) => (
                <Space>
                  {value > 0 ? (
                    <RiseOutlined className="text-green-500" />
                  ) : (
                    <FallOutlined className="text-red-500" />
                  )}
                  <Text className={value > 0 ? 'text-green-600' : 'text-red-600'}>
                    {value > 0 ? '+' : ''}{value}%
                  </Text>
                </Space>
              )
            }
          ]}
        />
      </Card>
    </div>
  );
};