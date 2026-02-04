import { jsx as _jsx } from 'react/jsx-runtime';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Users } from '../../pages/Users';
import { apiClient } from '../../services/api';
import { UserRole } from '../../types/api';
// Mock the API client
vi.mock('../../services/api', () => ({
  apiClient: {
    getUsers: vi.fn(),
    getTenants: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    changeUserPassword: vi.fn(),
    toggleUserStatus: vi.fn(),
    deleteUser: vi.fn(),
  },
}));
// Mock antd message
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
    },
  };
});
const mockUsers = [
  {
    user_id: '1',
    username: 'admin',
    email: 'admin@test.com',
    first_name: 'Admin',
    last_name: 'User',
    full_name: 'Admin User',
    role: UserRole.SYSTEM_ADMIN,
    is_active: true,
    is_email_verified: true,
    last_login: '2023-01-01T00:00:00Z',
    password_changed_at: '2023-01-01T00:00:00Z',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
  },
  {
    user_id: '2',
    username: 'manager',
    email: 'manager@test.com',
    first_name: 'Site',
    last_name: 'Manager',
    full_name: 'Site Manager',
    role: UserRole.SITE_MANAGER,
    tenant_id: 'test-tenant',
    is_active: true,
    is_email_verified: false,
    last_login: null,
    password_changed_at: '2023-01-01T00:00:00Z',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
  },
];
const mockTenants = [
  {
    tenant_id: 'test-tenant',
    name: 'Test Tenant',
    description: 'Test tenant description',
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
  },
];
describe('Users Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.getUsers.mockResolvedValue(mockUsers);
    apiClient.getTenants.mockResolvedValue(mockTenants);
  });
  it('renders users list correctly', async () => {
    render(_jsx(Users, {}));
    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('User Management')).toBeInTheDocument();
      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByText('manager')).toBeInTheDocument();
    });
    // Check that API was called
    expect(apiClient.getUsers).toHaveBeenCalledTimes(1);
    expect(apiClient.getTenants).toHaveBeenCalledTimes(1);
  });
  it('displays user information correctly', async () => {
    render(_jsx(Users, {}));
    await waitFor(() => {
      // Check system admin user
      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByText('Admin User')).toBeInTheDocument();
      expect(screen.getByText('admin@test.com')).toBeInTheDocument();
      expect(screen.getByText('System Admin')).toBeInTheDocument();
      // Check site manager user
      expect(screen.getByText('manager')).toBeInTheDocument();
      expect(screen.getByText('Site Manager')).toBeInTheDocument();
      expect(screen.getByText('manager@test.com')).toBeInTheDocument();
      expect(screen.getByText('Site Manager')).toBeInTheDocument();
    });
  });
  it('shows create user modal when Create User button is clicked', async () => {
    render(_jsx(Users, {}));
    await waitFor(() => {
      expect(screen.getByText('Create User')).toBeInTheDocument();
    });
    // Click create user button
    fireEvent.click(screen.getByText('Create User'));
    // Check modal is visible
    await waitFor(() => {
      expect(screen.getByText('Create New User')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter username')).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText('Enter email address')
      ).toBeInTheDocument();
    });
  });
  it('displays active/disabled status correctly', async () => {
    const usersWithInactive = [
      ...mockUsers,
      {
        user_id: '3',
        username: 'inactive',
        email: 'inactive@test.com',
        first_name: 'Inactive',
        last_name: 'User',
        full_name: 'Inactive User',
        role: UserRole.WORKER,
        tenant_id: 'test-tenant',
        is_active: false,
        is_email_verified: true,
        last_login: null,
        password_changed_at: '2023-01-01T00:00:00Z',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
      },
    ];
    apiClient.getUsers.mockResolvedValue(usersWithInactive);
    render(_jsx(Users, {}));
    await waitFor(() => {
      // Check active users show "Active" status
      const activeStatuses = screen.getAllByText('Active');
      expect(activeStatuses.length).toBe(2);
      // Check inactive user shows "Disabled" status
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });
  });
  it('shows tenant names correctly', async () => {
    render(_jsx(Users, {}));
    await waitFor(() => {
      // System admin should show "N/A" for tenant
      expect(screen.getByText('N/A')).toBeInTheDocument();
      // Site manager should show tenant name
      expect(screen.getByText('Test Tenant')).toBeInTheDocument();
    });
  });
  it('handles loading state', () => {
    // Mock slow API response
    apiClient.getUsers.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockUsers), 1000))
    );
    render(_jsx(Users, {}));
    // Should show loading spinner
    expect(document.querySelector('.ant-spin')).toBeInTheDocument();
  });
  it('handles API error gracefully', async () => {
    const consoleErrorSpy = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    apiClient.getUsers.mockRejectedValue(new Error('API Error'));
    render(_jsx(Users, {}));
    // Wait for error handling
    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalled();
    });
    consoleErrorSpy.mockRestore();
  });
  it('filters roles correctly in create user form', async () => {
    render(_jsx(Users, {}));
    // Open create modal
    await waitFor(() => {
      fireEvent.click(screen.getByText('Create User'));
    });
    // Check that all role options are available
    await waitFor(() => {
      const roleSelect = screen.getByText('Select user role');
      fireEvent.click(roleSelect);
    });
    await waitFor(() => {
      expect(screen.getByText('System Admin')).toBeInTheDocument();
      expect(screen.getByText('Tenant Admin')).toBeInTheDocument();
      expect(screen.getByText('Site Manager')).toBeInTheDocument();
      expect(screen.getByText('Worker')).toBeInTheDocument();
    });
  });
  it('shows last login correctly', async () => {
    render(_jsx(Users, {}));
    await waitFor(() => {
      // User with last login should show formatted date
      expect(screen.getByText(/1\/1\/2023/)).toBeInTheDocument();
      // User without last login should show "Never"
      expect(screen.getByText('Never')).toBeInTheDocument();
    });
  });
});
describe('Users Component - User Actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.getUsers.mockResolvedValue(mockUsers);
    apiClient.getTenants.mockResolvedValue(mockTenants);
  });
  it('handles user creation successfully', async () => {
    const newUser = {
      user_id: '3',
      username: 'newuser',
      email: 'newuser@test.com',
      first_name: 'New',
      last_name: 'User',
      full_name: 'New User',
      role: UserRole.WORKER,
      tenant_id: 'test-tenant',
      is_active: true,
      is_email_verified: false,
      last_login: null,
      password_changed_at: '2023-01-01T00:00:00Z',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:00:00Z',
    };
    apiClient.createUser.mockResolvedValue(newUser);
    apiClient.getUsers
      .mockResolvedValueOnce(mockUsers)
      .mockResolvedValueOnce([...mockUsers, newUser]);
    render(_jsx(Users, {}));
    // Open create modal
    await waitFor(() => {
      fireEvent.click(screen.getByText('Create User'));
    });
    // Fill out form
    await waitFor(() => {
      fireEvent.change(screen.getByPlaceholderText('Enter username'), {
        target: { value: 'newuser' },
      });
      fireEvent.change(screen.getByPlaceholderText('Enter email address'), {
        target: { value: 'newuser@test.com' },
      });
      fireEvent.change(screen.getByPlaceholderText('Enter first name'), {
        target: { value: 'New' },
      });
      fireEvent.change(screen.getByPlaceholderText('Enter last name'), {
        target: { value: 'User' },
      });
      fireEvent.change(screen.getByPlaceholderText('Enter password'), {
        target: { value: 'password123' },
      });
    });
    // Submit form
    const submitButton = screen.getByRole('button', { name: 'Create User' });
    fireEvent.click(submitButton);
    // Verify API was called
    await waitFor(() => {
      expect(apiClient.createUser).toHaveBeenCalledWith({
        username: 'newuser',
        email: 'newuser@test.com',
        first_name: 'New',
        last_name: 'User',
        password: 'password123',
        role: undefined, // Not selected in this test
        tenant_id: undefined, // Not selected in this test
        is_active: true,
      });
    });
  });
  it('handles user status toggle', async () => {
    const updatedUser = { ...mockUsers[1], is_active: false };
    apiClient.toggleUserStatus.mockResolvedValue(updatedUser);
    render(_jsx(Users, {}));
    await waitFor(() => {
      // Find the toggle button for the second user (site manager)
      const actionButtons = screen.getAllByRole('button');
      const toggleButton = actionButtons.find((button) =>
        button.getAttribute('aria-label')?.includes('Disable')
      );
      if (toggleButton) {
        fireEvent.click(toggleButton);
      }
    });
    // Confirm the action
    await waitFor(() => {
      const confirmButton = screen.getByText('Yes');
      fireEvent.click(confirmButton);
    });
    // Verify API was called
    await waitFor(() => {
      expect(apiClient.toggleUserStatus).toHaveBeenCalledWith('2');
    });
  });
});
