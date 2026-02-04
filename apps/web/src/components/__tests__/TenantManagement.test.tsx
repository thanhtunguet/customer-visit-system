import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach, MockedFunction } from 'vitest';
import { message } from 'antd';
import { TenantsPage } from '../../pages/Tenants';
import { apiClient } from '../../services/api';
import { Tenant } from '../../types/api';

// Mock the API client
vi.mock('../../services/api');
const mockedApiClient = apiClient as { [K in keyof typeof apiClient]: MockedFunction<typeof apiClient[K]> };

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

const mockTenants: Tenant[] = [
  {
    tenant_id: 'test-tenant-1',
    name: 'Test Tenant 1',
    description: 'Test description',
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
  },
  {
    tenant_id: 'test-tenant-2',
    name: 'Test Tenant 2',
    is_active: false,
    created_at: '2023-01-02T00:00:00Z',
  },
];

const mockSystemAdminUser = {
  sub: 'admin',
  role: 'system_admin',
  tenant_id: 'system',
};

const mockTenantAdminUser = {
  sub: 'tenant_admin',
  role: 'tenant_admin',
  tenant_id: 'test-tenant-1',
};

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('TenantManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('System Admin Access', () => {
    beforeEach(() => {
      mockedApiClient.getCurrentUser.mockResolvedValue(mockSystemAdminUser);
      mockedApiClient.getTenants.mockResolvedValue(mockTenants);
    });

    it('should render tenant management page for system admin', async () => {
      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('Tenant Management')).toBeInTheDocument();
      });

      expect(screen.getByText('Create Tenant')).toBeInTheDocument();
      expect(screen.getByText('test-tenant-1')).toBeInTheDocument();
      expect(screen.getByText('Test Tenant 1')).toBeInTheDocument();
    });

    it('should open create tenant modal when create button is clicked', async () => {
      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create Tenant')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Create Tenant'));

      await waitFor(() => {
        expect(screen.getByText('Create New Tenant')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('e.g., acme-corp')).toBeInTheDocument();
      });
    });

    it('should create a new tenant successfully', async () => {
      const newTenant = {
        tenant_id: 'new-tenant',
        name: 'New Tenant',
        description: 'New tenant description',
        is_active: true,
        created_at: '2023-01-03T00:00:00Z',
      };

      mockedApiClient.createTenant.mockResolvedValue(newTenant);

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create Tenant')).toBeInTheDocument();
      });

      // Open modal
      fireEvent.click(screen.getByText('Create Tenant'));

      await waitFor(() => {
        expect(screen.getByText('Create New Tenant')).toBeInTheDocument();
      });

      // Fill form
      fireEvent.change(screen.getByPlaceholderText('e.g., acme-corp'), {
        target: { value: 'new-tenant' },
      });
      fireEvent.change(screen.getByPlaceholderText('e.g., Acme Corporation'), {
        target: { value: 'New Tenant' },
      });
      fireEvent.change(screen.getByPlaceholderText('Brief description of the tenant organization...'), {
        target: { value: 'New tenant description' },
      });

      // Submit form
      fireEvent.click(screen.getByRole('button', { name: 'Create Tenant' }));

      await waitFor(() => {
        expect(mockedApiClient.createTenant).toHaveBeenCalledWith({
          tenant_id: 'new-tenant',
          name: 'New Tenant',
          description: 'New tenant description',
        });
      });
    });

    it('should edit an existing tenant', async () => {
      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('test-tenant-1')).toBeInTheDocument();
      });

      // Click edit button (first edit icon)
      const editButtons = screen.getAllByTitle('Edit Tenant');
      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Edit Tenant')).toBeInTheDocument();
        expect(screen.getByDisplayValue('test-tenant-1')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Test Tenant 1')).toBeInTheDocument();
      });
    });

    it('should delete a tenant successfully', async () => {
      mockedApiClient.deleteTenant.mockResolvedValue();

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('test-tenant-1')).toBeInTheDocument();
      });

      // Click delete button (first delete icon)
      const deleteButtons = screen.getAllByTitle('Delete Tenant');
      fireEvent.click(deleteButtons[0]);

      // Confirm deletion
      await waitFor(() => {
        expect(screen.getByText('Are you sure you want to delete tenant "Test Tenant 1"?')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: 'Yes, Delete' }));

      await waitFor(() => {
        expect(mockedApiClient.deleteTenant).toHaveBeenCalledWith('test-tenant-1');
      });
    });

    it('should toggle tenant status successfully', async () => {
      const updatedTenant = { ...mockTenants[1], is_active: true };
      mockedApiClient.toggleTenantStatus.mockResolvedValue(updatedTenant);

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('test-tenant-2')).toBeInTheDocument();
      });

      // Find and click the status switch for inactive tenant (test-tenant-2)
      const switches = screen.getAllByRole('switch');
      const inactiveSwitch = switches.find(s => !s.getAttribute('aria-checked') || s.getAttribute('aria-checked') === 'false');
      
      if (inactiveSwitch) {
        fireEvent.click(inactiveSwitch);

        // Confirm the action
        await waitFor(() => {
          expect(screen.getByText('Activate Tenant')).toBeInTheDocument();
        });

        fireEvent.click(screen.getByRole('button', { name: 'Yes, Activate' }));

        await waitFor(() => {
          expect(mockedApiClient.toggleTenantStatus).toHaveBeenCalledWith('test-tenant-2', true);
        });
      }
    });

    it('should show confirmation dialog when deactivating tenant', async () => {
      const updatedTenant = { ...mockTenants[0], is_active: false };
      mockedApiClient.toggleTenantStatus.mockResolvedValue(updatedTenant);

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('test-tenant-1')).toBeInTheDocument();
      });

      // Find and click the status switch for active tenant (test-tenant-1)
      const switches = screen.getAllByRole('switch');
      const activeSwitch = switches.find(s => s.getAttribute('aria-checked') === 'true');
      
      if (activeSwitch) {
        fireEvent.click(activeSwitch);

        // Check confirmation dialog content
        await waitFor(() => {
          expect(screen.getByText('Deactivate Tenant')).toBeInTheDocument();
          expect(screen.getByText(/disable all operations for this tenant organization/)).toBeInTheDocument();
        });

        fireEvent.click(screen.getByRole('button', { name: 'Yes, Deactivate' }));

        await waitFor(() => {
          expect(mockedApiClient.toggleTenantStatus).toHaveBeenCalledWith('test-tenant-1', false);
        });
      }
    });
  });

  describe('Non-System Admin Access', () => {
    beforeEach(() => {
      mockedApiClient.getCurrentUser.mockResolvedValue(mockTenantAdminUser);
    });

    it('should show access denied for non-system admin users', async () => {
      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('Access Denied')).toBeInTheDocument();
        expect(screen.getByText(/Only system administrators can manage tenants/)).toBeInTheDocument();
        expect(screen.getByText('tenant_admin')).toBeInTheDocument();
      });

      expect(screen.queryByText('Create Tenant')).not.toBeInTheDocument();
      expect(mockedApiClient.getTenants).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      mockedApiClient.getCurrentUser.mockResolvedValue(mockSystemAdminUser);
    });

    it('should handle fetch tenants error gracefully', async () => {
      mockedApiClient.getTenants.mockRejectedValue(new Error('Network error'));

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(message.error).toHaveBeenCalledWith('Network error');
      });
    });

    it('should handle create tenant error gracefully', async () => {
      mockedApiClient.getTenants.mockResolvedValue(mockTenants);
      mockedApiClient.createTenant.mockRejectedValue({
        response: { data: { detail: 'Tenant already exists' } },
      });

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create Tenant')).toBeInTheDocument();
      });

      // Open modal and submit form
      fireEvent.click(screen.getByText('Create Tenant'));

      await waitFor(() => {
        expect(screen.getByText('Create New Tenant')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByPlaceholderText('e.g., acme-corp'), {
        target: { value: 'existing-tenant' },
      });
      fireEvent.change(screen.getByPlaceholderText('e.g., Acme Corporation'), {
        target: { value: 'Existing Tenant' },
      });

      fireEvent.click(screen.getByRole('button', { name: 'Create Tenant' }));

      await waitFor(() => {
        expect(message.error).toHaveBeenCalledWith('Tenant already exists');
      });
    });

    it('should handle toggle tenant status error gracefully', async () => {
      mockedApiClient.getTenants.mockResolvedValue(mockTenants);
      mockedApiClient.toggleTenantStatus.mockRejectedValue({
        response: { data: { detail: 'Failed to update tenant status' } },
      });

      renderWithRouter(<TenantsPage />);

      await waitFor(() => {
        expect(screen.getByText('test-tenant-1')).toBeInTheDocument();
      });

      // Find and click the status switch
      const switches = screen.getAllByRole('switch');
      if (switches[0]) {
        fireEvent.click(switches[0]);

        // Confirm the action
        await waitFor(() => {
          expect(screen.getByText(/Deactivate Tenant/)).toBeInTheDocument();
        });

        fireEvent.click(screen.getByRole('button', { name: 'Yes, Deactivate' }));

        await waitFor(() => {
          expect(message.error).toHaveBeenCalledWith('Failed to update tenant status');
        });
      }
    });
  });
});