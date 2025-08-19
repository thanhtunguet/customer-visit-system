import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import { AppLayout } from '../components/Layout';
import { LoginForm } from '../components/LoginForm';
import { Dashboard } from '../pages/Dashboard';
import { Sites } from '../pages/Sites';
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
              
              {/* Placeholder routes for other pages */}
              <Route 
                path="cameras" 
                element={<div className="p-6"><h2>Cameras - Coming Soon</h2></div>} 
              />
              <Route 
                path="staff" 
                element={<div className="p-6"><h2>Staff - Coming Soon</h2></div>} 
              />
              <Route 
                path="customers" 
                element={<div className="p-6"><h2>Customers - Coming Soon</h2></div>} 
              />
              <Route 
                path="visits" 
                element={<div className="p-6"><h2>Visits - Coming Soon</h2></div>} 
              />
              <Route 
                path="reports" 
                element={<div className="p-6"><h2>Reports - Coming Soon</h2></div>} 
              />
              <Route 
                path="tenants" 
                element={<div className="p-6"><h2>Tenants - Coming Soon</h2></div>} 
              />
            </Route>

            {/* Catch all route */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
      </Router>
    </ConfigProvider>
  );
}

