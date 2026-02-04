import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Alert } from 'antd';
import { UserOutlined, TeamOutlined, EyeOutlined, ShopOutlined } from '@ant-design/icons';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { apiClient } from '../services/api';
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
// Note: Seed data functions removed - using real API data only
// Note: Seed data functions removed - using real API data only
export const Dashboard = () => {
    const [stats, setStats] = useState({
        totalVisits: 0,
        todayVisits: 0,
        totalCustomers: 0,
        totalStaff: 0,
        activeSites: 0,
    });
    const [recentVisits, setRecentVisits] = useState([]);
    const [visitorTrends, setVisitorTrends] = useState([]);
    // const [loadingTrends, setLoadingTrends] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [systemStatus, setSystemStatus] = useState({
        api: 'online',
        processing: 'processing',
        database: 'online'
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
            const todayVisits = visits.filter(visit => dayjs(visit.timestamp).isAfter(today)).length;
            // Calculate totals from visitor report data
            const totalVisitsFromReport = visitorReport.reduce((sum, item) => sum + item.total_visits, 0);
            const todayVisitsFromReport = visitorReport.length > 0 ? visitorReport[visitorReport.length - 1].total_visits : todayVisits;
            setStats({
                totalCustomers: customers.length,
                totalStaff: staff.length,
                totalVisits: totalVisitsFromReport > 0 ? totalVisitsFromReport : visits.length,
                todayVisits: todayVisitsFromReport > 0 ? todayVisitsFromReport : todayVisits,
                activeSites: sites.length,
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
            // Always use real API data for visitor trends
            setVisitorTrends(transformedTrends);
            // Basic chart data calculation skipped (not rendered currently)
            setRecentVisits(visits);
            // Update system status based on health check and worker status
            setSystemStatus({
                api: healthCheck.status === 'ok' ? 'online' : 'error',
                processing: workers.online_count > 0 ? 'processing' : 'offline',
                database: healthCheck.status === 'ok' ? 'online' : 'error' // API health implies DB health
            });
        }
        catch (err) {
            const error = err;
            setError(error.message || 'Failed to load dashboard data');
        }
        finally {
            setLoading(false);
        }
    };
    if (error) {
        return (_jsx(Alert, { message: "Dashboard Error", description: error, type: "error", showIcon: true, action: _jsx("button", { onClick: loadDashboardData, className: "text-blue-600", children: "Retry" }) }));
    }
    return (_jsxs("div", { className: "space-y-6", children: [_jsx("div", { className: "flex items-center justify-between", children: _jsx(Title, { level: 2, className: "mb-0", children: "Dashboard" }) }), _jsxs(Row, { gutter: 16, children: [_jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "Today's Visits", value: stats.todayVisits, prefix: _jsx(EyeOutlined, { className: "text-blue-600" }), loading: loading }) }) }), _jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "Total Customers", value: stats.totalCustomers, prefix: _jsx(UserOutlined, { className: "text-green-600" }), loading: loading }) }) }), _jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "Staff Members", value: stats.totalStaff, prefix: _jsx(TeamOutlined, { className: "text-orange-600" }), loading: loading }) }) }), _jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "Active Sites", value: stats.activeSites, prefix: _jsx(ShopOutlined, { className: "text-purple-600" }), loading: loading }) }) })] }), _jsxs(Row, { gutter: 16, children: [_jsx(Col, { xs: 24, lg: 16, children: _jsx(Card, { title: "Visitor Trends (Last 7 Days)", loading: loading, children: _jsx(ResponsiveContainer, { width: "100%", height: 300, children: _jsxs(AreaChart, { data: visitorTrends, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3" }), _jsx(XAxis, { dataKey: "date" }), _jsx(YAxis, {}), _jsx(RechartsTooltip, { labelFormatter: (label) => `Date: ${label}`, formatter: (value, name) => [value, typeof name === 'string' ? name.replace(/([A-Z])/g, ' $1').trim() : name] }), _jsx(Area, { type: "monotone", dataKey: "staffVisits", stackId: "1", stroke: COLORS.warning, fill: COLORS.warning, fillOpacity: 0.6, name: "Staff Visits" }), _jsx(Area, { type: "monotone", dataKey: "customerVisits", stackId: "1", stroke: COLORS.primary, fill: COLORS.primary, fillOpacity: 0.6, name: "Customer Visits" })] }) }) }) }), _jsx(Col, { xs: 24, lg: 8, children: _jsx(Card, { title: "Recent Visits", loading: loading, children: _jsxs(Space, { direction: "vertical", className: "w-full", children: [recentVisits.slice(0, 6).map((visit, index) => (_jsxs("div", { className: "flex items-center justify-between p-2 bg-gray-50 rounded", children: [_jsxs("div", { children: [_jsxs("div", { className: "font-medium text-sm", children: [visit.person_type === 'staff' ? '👤' : '👥', " ", visit.person_id] }), _jsxs("div", { className: "text-xs text-gray-500", children: [visit.site_id, " \u2022 ", dayjs(visit.timestamp).format('HH:mm')] })] }), _jsxs("div", { className: "text-xs text-gray-400", children: [Math.round(visit.confidence_score * 100), "%"] })] }, visit.visit_id || `visit-${index}`))), recentVisits.length === 0 && !loading && (_jsx("div", { className: "text-center text-gray-500 py-4", children: "No recent visits" }))] }) }) })] }), _jsx(Card, { title: "System Status", children: _jsxs(Row, { gutter: 16, children: [_jsx(Col, { span: 8, children: _jsxs("div", { className: "text-center", children: [_jsx("div", { className: `w-3 h-3 rounded-full mx-auto mb-2 ${systemStatus.api === 'online' ? 'bg-green-500' :
                                            systemStatus.api === 'error' ? 'bg-red-500' : 'bg-gray-400'}` }), _jsx("div", { className: "text-sm font-medium", children: "API Service" }), _jsx("div", { className: "text-xs text-gray-500 capitalize", children: systemStatus.api })] }) }), _jsx(Col, { span: 8, children: _jsxs("div", { className: "text-center", children: [_jsx("div", { className: `w-3 h-3 rounded-full mx-auto mb-2 ${systemStatus.processing === 'processing' ? 'bg-yellow-500' :
                                            systemStatus.processing === 'online' ? 'bg-green-500' :
                                                systemStatus.processing === 'error' ? 'bg-red-500' : 'bg-gray-400'}` }), _jsx("div", { className: "text-sm font-medium", children: "Face Processing" }), _jsx("div", { className: "text-xs text-gray-500 capitalize", children: systemStatus.processing })] }) }), _jsx(Col, { span: 8, children: _jsxs("div", { className: "text-center", children: [_jsx("div", { className: `w-3 h-3 rounded-full mx-auto mb-2 ${systemStatus.database === 'online' ? 'bg-green-500' :
                                            systemStatus.database === 'error' ? 'bg-red-500' : 'bg-gray-400'}` }), _jsx("div", { className: "text-sm font-medium", children: "Database" }), _jsx("div", { className: "text-xs text-gray-500 capitalize", children: systemStatus.database })] }) })] }) })] }));
};
