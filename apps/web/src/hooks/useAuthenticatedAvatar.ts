import { useState, useEffect } from 'react';
import { apiClient } from '../services/api';

export const useAuthenticatedAvatar = (avatarUrl?: string) => {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadImage = async () => {
      if (!avatarUrl) {
        setBlobUrl(null);
        setLoading(false);
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const url = await apiClient.getImageUrl(avatarUrl);
        if (!cancelled) {
          setBlobUrl(url);
        }
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load avatar');
          setBlobUrl(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadImage();

    return () => {
      cancelled = true;
      // Clean up blob URL to prevent memory leaks
      if (blobUrl && blobUrl.startsWith('blob:')) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [avatarUrl]);

  // Clean up blob URL when component unmounts
  useEffect(() => {
    return () => {
      if (blobUrl && blobUrl.startsWith('blob:')) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [blobUrl]);

  return { blobUrl, loading, error };
};