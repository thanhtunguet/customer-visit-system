import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import { AppLayout } from '../components/Layout';
import { LoginForm } from '../components/LoginForm';
import { TenantProvider } from '../contexts/TenantContext';
import { SystemAdminRoute } from '../components/RoleBasedRoute';
import { Dashboard } from '../pages/Dashboard';
import { Sites } from '../pages/Sites';
import { Cameras } from '../pages/Cameras';
import { StaffPage } from '../pages/Staff';
import { Customers } from '../pages/Customers';
import { VisitsPage } from '../pages/Visits';
import { Reports } from '../pages/Reports';
import { TenantsPage } from '../pages/Tenants';
import { Users } from '../pages/Users';
import Workers from '../pages/Workers';
import ApiKeys from '../pages/ApiKeys';
import '../styles.css';

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('access_token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
};

// Public Route component (redirect if already logged in)
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('access_token');
  return token ? <Navigate to="/dashboard" replace /> : <>{children}</>;
};

export function App() {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#2563eb',
        },
      }}
    >
      <AntApp>
        <TenantProvider>
          <Router>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            {/* Public Routes */}
            <Route
              path="/login"
              element={
                <PublicRoute>
                  <LoginForm />
                </PublicRoute>
              }
            />

            {/* Protected Routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="sites" element={<Sites />} />
              
              {/* Implemented pages */}
              <Route path="cameras" element={<Cameras />} />
              <Route path="workers" element={<Workers />} />
              <Route path="staff" element={<StaffPage />} />
              <Route path="customers" element={<Customers />} />
              <Route path="visits" element={<VisitsPage />} />
              
              {/* Placeholder routes for other pages */}
              <Route path="reports" element={<Reports />} />
              <Route 
                path="tenants" 
                element={
                  <SystemAdminRoute>
                    <TenantsPage />
                  </SystemAdminRoute>
                } 
              />
              <Route 
                path="users" 
                element={
                  <SystemAdminRoute>
                    <Users />
                  </SystemAdminRoute>
                } 
              />
              <Route path="api-keys" element={<ApiKeys />} />
            </Route>

            {/* Catch all route */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
          </Router>
        </TenantProvider>
      </AntApp>
    </ConfigProvider>
  );
}

