import {
  Fragment as _Fragment,
  jsx as _jsx,
  jsxs as _jsxs,
} from 'react/jsx-runtime';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import { AppLayout } from '../components/Layout';
import { LoginForm } from '../components/LoginForm';
import { TenantProvider } from '../contexts/TenantContext';
import {
  SystemAdminRoute,
  TenantManagementRoute,
  SiteManagementRoute,
  TenantAdminRoute,
} from '../components/RoleBasedRoute';
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
const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('access_token');
  return token
    ? _jsx(_Fragment, { children: children })
    : _jsx(Navigate, { to: '/login', replace: true });
};
// Public Route component (redirect if already logged in)
const PublicRoute = ({ children }) => {
  const token = localStorage.getItem('access_token');
  return token
    ? _jsx(Navigate, { to: '/dashboard', replace: true })
    : _jsx(_Fragment, { children: children });
};
export function App() {
  return _jsx(ConfigProvider, {
    theme: {
      token: {
        colorPrimary: '#2563eb',
      },
    },
    children: _jsx(AntApp, {
      children: _jsx(TenantProvider, {
        children: _jsx(Router, {
          children: _jsx('div', {
            className: 'min-h-screen bg-gray-50',
            children: _jsxs(Routes, {
              children: [
                _jsx(Route, {
                  path: '/login',
                  element: _jsx(PublicRoute, { children: _jsx(LoginForm, {}) }),
                }),
                _jsxs(Route, {
                  path: '/',
                  element: _jsx(ProtectedRoute, {
                    children: _jsx(AppLayout, {}),
                  }),
                  children: [
                    _jsx(Route, {
                      index: true,
                      element: _jsx(Navigate, {
                        to: '/dashboard',
                        replace: true,
                      }),
                    }),
                    _jsx(Route, {
                      path: 'dashboard',
                      element: _jsx(Dashboard, {}),
                    }),
                    _jsx(Route, {
                      path: 'sites',
                      element: _jsx(SiteManagementRoute, {
                        children: _jsx(Sites, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'cameras',
                      element: _jsx(TenantAdminRoute, {
                        children: _jsx(Cameras, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'workers',
                      element: _jsx(TenantAdminRoute, {
                        children: _jsx(Workers, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'staff',
                      element: _jsx(TenantAdminRoute, {
                        children: _jsx(StaffPage, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'customers',
                      element: _jsx(TenantAdminRoute, {
                        children: _jsx(Customers, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'visits',
                      element: _jsx(VisitsPage, {}),
                    }),
                    _jsx(Route, {
                      path: 'reports',
                      element: _jsx(TenantAdminRoute, {
                        children: _jsx(Reports, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'tenants',
                      element: _jsx(TenantManagementRoute, {
                        children: _jsx(TenantsPage, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'users',
                      element: _jsx(SystemAdminRoute, {
                        children: _jsx(Users, {}),
                      }),
                    }),
                    _jsx(Route, {
                      path: 'api-keys',
                      element: _jsx(TenantAdminRoute, {
                        children: _jsx(ApiKeys, {}),
                      }),
                    }),
                  ],
                }),
                _jsx(Route, {
                  path: '*',
                  element: _jsx(Navigate, { to: '/dashboard', replace: true }),
                }),
              ],
            }),
          }),
        }),
      }),
    }),
  });
}
