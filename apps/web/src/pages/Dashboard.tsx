import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Alert } from 'antd';
import { 
  UserOutlined, 
  TeamOutlined, 
  EyeOutlined, 
  ShopOutlined,
  TrendingUpOutlined 
} from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { apiClient } from '../services/api';
import { VisitorReport, Visit } from '../types/api';
import dayjs from 'dayjs';

const { Title } = Typography;

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load basic stats
      const [customers, staff, visits, sites, visitorReport] = await Promise.all([
        apiClient.getCustomers({ limit: 1000 }),
        apiClient.getStaff(),
        apiClient.getVisits({ limit: 10 }),
        apiClient.getSites(),
        apiClient.getVisitorReport({ 
          granularity: 'day',
          start_date: dayjs().subtract(7, 'days').toISOString(),
          end_date: dayjs().toISOString()
        }),
      ]);

      // Calculate today's visits
      const today = dayjs().startOf('day');
      const todayVisits = visits.filter(visit => 
        dayjs(visit.timestamp).isAfter(today)
      ).length;

      setStats({
        totalCustomers: customers.length,
        totalStaff: staff.length,
        totalVisits: visits.length, // This would be better from a separate aggregate endpoint
        todayVisits,
        activeSites: sites.length,
      });

      // Prepare chart data
      const chartData = visitorReport.slice(-7).map(item => ({
        date: dayjs(item.period).format('MM/DD'),
        visits: item.total_visits,
        unique: item.unique_visitors,
      }));
      setChartData(chartData);
      setRecentVisits(visits);

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
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line 
                  type="monotone" 
                  dataKey="visits" 
                  stroke="#2563eb" 
                  strokeWidth={2}
                  name="Total Visits"
                />
                <Line 
                  type="monotone" 
                  dataKey="unique" 
                  stroke="#059669" 
                  strokeWidth={2}
                  name="Unique Visitors"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Recent Visits" loading={loading}>
            <Space direction="vertical" className="w-full">
              {recentVisits.slice(0, 6).map((visit, index) => (
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
              
              {recentVisits.length === 0 && !loading && (
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
              <div className="w-3 h-3 bg-green-500 rounded-full mx-auto mb-2"></div>
              <div className="text-sm font-medium">API Service</div>
              <div className="text-xs text-gray-500">Online</div>
            </div>
          </Col>
          <Col span={8}>
            <div className="text-center">
              <div className="w-3 h-3 bg-yellow-500 rounded-full mx-auto mb-2"></div>
              <div className="text-sm font-medium">Face Recognition</div>
              <div className="text-xs text-gray-500">Processing</div>
            </div>
          </Col>
          <Col span={8}>
            <div className="text-center">
              <div className="w-3 h-3 bg-green-500 rounded-full mx-auto mb-2"></div>
              <div className="text-sm font-medium">Database</div>
              <div className="text-xs text-gray-500">Connected</div>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
};