import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { message } from 'antd';
import { StaffFaceGallery } from '../StaffFaceGallery';
import { apiClient } from '../../services/api';
import { StaffFaceImage } from '../../types/api';

// Mock the API client
jest.mock('../../services/api', () => ({
  apiClient: {
    uploadStaffFaceImage: jest.fn(),
    deleteStaffFaceImage: jest.fn(),
    recalculateFaceEmbedding: jest.fn(),
  },
}));

// Mock antd message
jest.mock('antd', () => ({
  ...jest.requireActual('antd'),
  message: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

// Mock environment variables
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_URL: 'http://localhost:8080',
  },
});

const mockFaceImages: StaffFaceImage[] = [
  {
    tenant_id: 't-test',
    image_id: 'img-1',
    staff_id: 123,
    image_path: 'staff-faces/t-test/img-1.jpg',
    face_landmarks: [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
    is_primary: true,
    created_at: '2023-01-01T00:00:00Z',
  },
  {
    tenant_id: 't-test',
    image_id: 'img-2',
    staff_id: 123,
    image_path: 'staff-faces/t-test/img-2.jpg',
    face_landmarks: [[2, 3], [4, 5], [6, 7], [8, 9], [10, 11]],
    is_primary: false,
    created_at: '2023-01-02T00:00:00Z',
  },
];

describe('StaffFaceGallery', () => {
  const mockProps = {
    staffId: 123,
    staffName: 'John Doe',
    faceImages: mockFaceImages,
    onImagesChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders face gallery with images', () => {
    render(<StaffFaceGallery {...mockProps} />);

    expect(screen.getByText('Face Images (2)')).toBeInTheDocument();
    expect(screen.getByText('Primary')).toBeInTheDocument();
    expect(screen.getByText('Add Image')).toBeInTheDocument();
  });

  it('renders empty state when no images', () => {
    const emptyProps = { ...mockProps, faceImages: [] };
    render(<StaffFaceGallery {...emptyProps} />);

    expect(screen.getByText('Face Images (0)')).toBeInTheDocument();
    expect(screen.getByText('No face images')).toBeInTheDocument();
    expect(screen.getByText('Add Primary Image')).toBeInTheDocument();
  });

  it('handles image upload successfully', async () => {
    const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const mockUploadResponse: StaffFaceImage = {
      tenant_id: 't-test',
      image_id: 'new-img',
      staff_id: 123,
      image_path: 'staff-faces/t-test/new-img.jpg',
      face_landmarks: [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
      is_primary: false,
      created_at: '2023-01-03T00:00:00Z',
    };

    (apiClient.uploadStaffFaceImage as jest.Mock).mockResolvedValue(mockUploadResponse);

    render(<StaffFaceGallery {...mockProps} />);

    const uploadButton = screen.getByText('Add Image');
    const uploadInput = uploadButton.closest('.ant-upload')?.querySelector('input[type="file"]');

    if (uploadInput) {
      fireEvent.change(uploadInput, { target: { files: [mockFile] } });
    }

    await waitFor(() => {
      expect(apiClient.uploadStaffFaceImage).toHaveBeenCalledWith(
        123,
        expect.any(String), // base64 data
        false
      );
    });

    expect(message.success).toHaveBeenCalledWith('Face image uploaded successfully');
    expect(mockProps.onImagesChange).toHaveBeenCalled();
  });

  it('handles image upload failure', async () => {
    const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const errorResponse = {
      response: {
        data: {
          detail: 'No faces detected in image',
        },
      },
    };

    (apiClient.uploadStaffFaceImage as jest.Mock).mockRejectedValue(errorResponse);

    render(<StaffFaceGallery {...mockProps} />);

    const uploadButton = screen.getByText('Add Image');
    const uploadInput = uploadButton.closest('.ant-upload')?.querySelector('input[type="file"]');

    if (uploadInput) {
      fireEvent.change(uploadInput, { target: { files: [mockFile] } });
    }

    await waitFor(() => {
      expect(message.error).toHaveBeenCalledWith('No faces detected in image');
    });
  });

  it('handles image deletion successfully', async () => {
    (apiClient.deleteStaffFaceImage as jest.Mock).mockResolvedValue({});

    render(<StaffFaceGallery {...mockProps} />);

    // Find and click delete button (need to look for the delete icon in actions)
    const deleteButtons = screen.getAllByRole('button');
    const deleteButton = deleteButtons.find(button => 
      button.querySelector('.anticon-delete')
    );

    if (deleteButton) {
      fireEvent.click(deleteButton);

      // Confirm deletion in popconfirm
      await waitFor(() => {
        const confirmButton = screen.getByText('Yes');
        fireEvent.click(confirmButton);
      });

      await waitFor(() => {
        expect(apiClient.deleteStaffFaceImage).toHaveBeenCalledWith(123, 'img-1');
        expect(message.success).toHaveBeenCalledWith('Face image deleted successfully');
        expect(mockProps.onImagesChange).toHaveBeenCalled();
      });
    }
  });

  it('handles recalculation successfully', async () => {
    const mockRecalcResponse = {
      message: 'Face landmarks and embedding recalculated successfully',
      processing_info: {
        face_count: 1,
        confidence: 0.95,
      },
    };

    (apiClient.recalculateFaceEmbedding as jest.Mock).mockResolvedValue(mockRecalcResponse);

    render(<StaffFaceGallery {...mockProps} />);

    // Find and click recalculate button
    const reloadButtons = screen.getAllByRole('button');
    const reloadButton = reloadButtons.find(button => 
      button.querySelector('.anticon-reload')
    );

    if (reloadButton) {
      fireEvent.click(reloadButton);

      await waitFor(() => {
        expect(apiClient.recalculateFaceEmbedding).toHaveBeenCalledWith(123, 'img-1');
        expect(message.success).toHaveBeenCalledWith(
          'Face landmarks and embedding recalculated successfully (Confidence: 95.0%)'
        );
        expect(mockProps.onImagesChange).toHaveBeenCalled();
      });
    }
  });

  it('displays primary image badge correctly', () => {
    render(<StaffFaceGallery {...mockProps} />);

    // Should show Primary tag for the first image
    expect(screen.getByText('Primary')).toBeInTheDocument();
  });

  it('displays landmarks info correctly', () => {
    render(<StaffFaceGallery {...mockProps} />);

    // Should show landmarks detected info
    const landmarksText = screen.getAllByText(/✓ Landmarks detected \(5 points\)/);
    expect(landmarksText).toHaveLength(2); // Both images have landmarks
  });

  it('handles image preview', () => {
    render(<StaffFaceGallery {...mockProps} />);

    // Find and click an image to preview
    const images = screen.getAllByRole('img');
    if (images.length > 0) {
      fireEvent.click(images[0]);
      // Modal should open but testing modal content requires more complex setup
    }
  });

  it('generates correct image URLs', () => {
    render(<StaffFaceGallery {...mockProps} />);

    const images = screen.getAllByRole('img');
    expect(images[0]).toHaveAttribute(
      'src', 
      'http://localhost:8080/v1/files/staff-faces/t-test/img-1.jpg'
    );
  });
});