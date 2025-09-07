import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Alert } from 'antd';
import { 
  UserOutlined, 
  TeamOutlined, 
  EyeOutlined, 
  ShopOutlined,
  TrendingUpOutlined 
} from '@ant-design/icons';
import { 
  LineChart, 
  Line, 
  AreaChart,
  Area,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as RechartsTooltip, 
  ResponsiveContainer 
} from 'recharts';
import { apiClient } from '../services/api';
import { VisitorReport, Visit } from '../types/api';
import dayjs from 'dayjs';

const { Title } = Typography;

// Color palette for charts
const COLORS = {
  primary: '#2563eb',
  secondary: '#059669',
  accent: '#dc2626',
  warning: '#d97706',
  info: '#7c3aed',
  success: '#16a34a'
};

// Generate seed data for the last 7 days
const generateVisitorTrendsData = () => {
  const data = [];
  for (let i = 6; i >= 0; i--) {
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

// Generate seed data for recent visits
const generateRecentVisitsData = () => {
  const visits = [];
  const customerNames = ['John D.', 'Sarah M.', 'Mike R.', 'Emily S.', 'David L.', 'Anna K.', 'Tom B.', 'Lisa W.'];
  const staffNames = ['Alice Johnson', 'Bob Smith', 'Carol Davis', 'Dan Wilson'];
  const sites = ['Main Branch', 'North Branch', 'South Branch'];
  
  for (let i = 0; i < 15; i++) {
    const isStaff = Math.random() < 0.3;
    const timestamp = dayjs().subtract(Math.floor(Math.random() * 180), 'minutes');
    
    visits.push({
      visit_id: `visit_${i + 1}`,
      person_id: isStaff 
        ? staffNames[Math.floor(Math.random() * staffNames.length)]
        : customerNames[Math.floor(Math.random() * customerNames.length)],
      person_type: isStaff ? 'staff' : 'customer',
      site_id: sites[Math.floor(Math.random() * sites.length)],
      timestamp: timestamp.toISOString(),
      confidence_score: 0.85 + Math.random() * 0.14,
      is_staff_local: isStaff
    });
  }
  
  return visits.sort((a, b) => dayjs(b.timestamp).valueOf() - dayjs(a.timestamp).valueOf());
};

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState({
    totalVisits: 0,
    todayVisits: 0,
    totalCustomers: 0,
    totalStaff: 0,
    activeSites: 0,
  });
  const [chartData, setChartData] = useState<any[]>([]);
  const [recentVisits, setRecentVisits] = useState<Visit[]>([]);
  const [visitorTrends, setVisitorTrends] = useState(generateVisitorTrendsData());
  const [seedRecentVisits] = useState(generateRecentVisitsData());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [systemStatus, setSystemStatus] = useState({
    api: 'online' as 'online' | 'offline' | 'error',
    processing: 'processing' as 'online' | 'processing' | 'offline' | 'error', 
    database: 'online' as 'online' | 'offline' | 'error'
  });

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load basic stats and system health
      const [customers, staff, visitsResponse, sites, visitorReport, healthCheck, workers] = await Promise.all([
        apiClient.getCustomers({ limit: 1000 }),
        apiClient.getStaff(),
        apiClient.getVisits({ limit: 10 }),
        apiClient.getSites(),
        apiClient.getVisitorReport({ 
          granularity: 'day',
          start_date: dayjs().subtract(7, 'days').toISOString(),
          end_date: dayjs().toISOString()
        }),
        // Health check for system status
        apiClient.getHealth().catch(() => ({ status: 'error', env: 'unknown', timestamp: new Date().toISOString() })),
        // Worker status for processing indicator
        apiClient.getWorkers().catch(() => ({ workers: [], total_count: 0, online_count: 0, offline_count: 0, error_count: 0 }))
      ]);

      // Extract visits array from response
      const visits = visitsResponse.visits;

      // Calculate today's visits
      const today = dayjs().startOf('day');
      const todayVisits = visits.filter(visit => 
        dayjs(visit.timestamp).isAfter(today)
      ).length;

      // Fallback to seed data for demonstration
      const fallbackTodayVisits = visitorTrends[visitorTrends.length - 1]?.totalVisits || 0;
      const fallbackTotalVisits = visitorTrends.reduce((sum, day) => sum + day.totalVisits, 0);

      setStats({
        totalCustomers: customers.length || 324, // Fallback for demo
        totalStaff: staff.length || 12, // Fallback for demo
        totalVisits: visits.length || fallbackTotalVisits, 
        todayVisits: todayVisits || fallbackTodayVisits,
        activeSites: sites.length || 5, // Fallback for demo
      });

      // Transform visitor report data for Dashboard trends chart
      const transformedTrends = visitorReport.slice(-7).map(item => ({
        date: dayjs(item.period).format('MM/DD'),
        fullDate: dayjs(item.period).format('YYYY-MM-DD'),
        totalVisits: item.total_visits,
        customerVisits: Math.round(item.total_visits * 0.8), // Approximate customer visits (80%)
        staffVisits: Math.round(item.total_visits * 0.2), // Approximate staff visits (20%)
        uniqueVisitors: item.unique_visitors || Math.round(item.total_visits * 0.7),
        repeatVisitors: Math.max(0, item.total_visits - (item.unique_visitors || Math.round(item.total_visits * 0.7)))
      }));

      // Update visitor trends with real data if available, otherwise keep seed data
      if (transformedTrends.length > 0) {
        setVisitorTrends(transformedTrends);
      }

      // Prepare basic chart data (keeping for compatibility)
      const chartData = visitorReport.slice(-7).map(item => ({
        date: dayjs(item.period).format('MM/DD'),
        visits: item.total_visits,
        unique: item.unique_visitors,
      }));
      setChartData(chartData);
      setRecentVisits(visits);

      // Update system status based on health check and worker status
      setSystemStatus({
        api: healthCheck.status === 'ok' ? 'online' : 'error',
        processing: workers.online_count > 0 ? 'processing' : 'offline',
        database: healthCheck.status === 'ok' ? 'online' : 'error' // API health implies DB health
      });

    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  if (error) {
    return (
      <Alert
        message="Dashboard Error"
        description={error}
        type="error"
        showIcon
        action={
          <button onClick={loadDashboardData} className="text-blue-600">
            Retry
          </button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title level={2} className="mb-0">Dashboard</Title>
      </div>

      {/* Stats Cards */}
      <Row gutter={16}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Today's Visits"
              value={stats.todayVisits}
              prefix={<EyeOutlined className="text-blue-600" />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Customers"
              value={stats.totalCustomers}
              prefix={<UserOutlined className="text-green-600" />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Staff Members"
              value={stats.totalStaff}
              prefix={<TeamOutlined className="text-orange-600" />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Active Sites"
              value={stats.activeSites}
              prefix={<ShopOutlined className="text-purple-600" />}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts Row */}
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card title="Visitor Trends (Last 7 Days)" loading={loading}>
            <ResponsiveContainer width="100%" height={300}>
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
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Recent Visits" loading={loading}>
            <Space direction="vertical" className="w-full">
              {(recentVisits.length > 0 ? recentVisits : seedRecentVisits).slice(0, 6).map((visit, index) => (
                <div key={visit.visit_id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <div>
                    <div className="font-medium text-sm">
                      {visit.person_type === 'staff' ? '👤' : '👥'} {visit.person_id}
                    </div>
                    <div className="text-xs text-gray-500">
                      {visit.site_id} • {dayjs(visit.timestamp).format('HH:mm')}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400">
                    {Math.round(visit.confidence_score * 100)}%
                  </div>
                </div>
              ))}
              
              {recentVisits.length === 0 && seedRecentVisits.length === 0 && !loading && (
                <div className="text-center text-gray-500 py-4">
                  No recent visits
                </div>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* System Status */}
      <Card title="System Status">
        <Row gutter={16}>
          <Col span={8}>
            <div className="text-center">
              <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${
                systemStatus.api === 'online' ? 'bg-green-500' : 
                systemStatus.api === 'error' ? 'bg-red-500' : 'bg-gray-400'
              }`}></div>
              <div className="text-sm font-medium">API Service</div>
              <div className="text-xs text-gray-500 capitalize">{systemStatus.api}</div>
            </div>
          </Col>
          <Col span={8}>
            <div className="text-center">
              <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${
                systemStatus.processing === 'processing' ? 'bg-yellow-500' :
                systemStatus.processing === 'online' ? 'bg-green-500' :
                systemStatus.processing === 'error' ? 'bg-red-500' : 'bg-gray-400'
              }`}></div>
              <div className="text-sm font-medium">Face Processing</div>
              <div className="text-xs text-gray-500 capitalize">{systemStatus.processing}</div>
            </div>
          </Col>
          <Col span={8}>
            <div className="text-center">
              <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${
                systemStatus.database === 'online' ? 'bg-green-500' : 
                systemStatus.database === 'error' ? 'bg-red-500' : 'bg-gray-400'
              }`}></div>
              <div className="text-sm font-medium">Database</div>
              <div className="text-xs text-gray-500 capitalize">{systemStatus.database}</div>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
};